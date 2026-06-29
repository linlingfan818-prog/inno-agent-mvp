import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessageChunk
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from agent.workflow import workflow
from schemas import ChatPayload, CheckKeyPayload
from agent.config import initialize_llm

router = APIRouter()

def _normalize_how_data(how_data):
    if not isinstance(how_data, dict):
        return how_data
    # 如果发现 m1 在顶层，说明是旧版本保存的脏数据，将其平移到 milestones 中
    if "m1" in how_data and "milestones" not in how_data:
        how_data["milestones"] = {
            "M1": how_data.pop("m1", ""),
            "M2": how_data.pop("m2", ""),
            "M3": how_data.pop("m3", ""),
            "M4": how_data.pop("m4", "")
        }
    return how_data

async def dual_channel_stream(user_message: str, session_id: str, api_key: str = None, username: str = None, language: str = "zh"):
    config = {"configurable": {"thread_id": session_id, "api_key": api_key, "username": username or "anonymous", "language": language}}
    inputs = {"messages": [("user", user_message)]}

    try:
        async with AsyncSqliteSaver.from_conn_string("checkpoints.sqlite") as checkpointer:
            await checkpointer.setup()
            compiled_graph = workflow.compile(checkpointer=checkpointer)
            
            # 初始化当前状态，避免 checkpointer 延迟导致读不到最新状态
            current_state_data = {
                "current_phase": "COACH",
                "why": None,
                "what": None,
                "market_value": None,
                "how": None
            }
            initial_state = await compiled_graph.aget_state(config)
            is_first_message = True
            if initial_state and initial_state.values:
                current_state_data["current_phase"] = initial_state.values.get("current_phase", "COACH")
                current_state_data["why"] = initial_state.values.get("why")
                current_state_data["what"] = initial_state.values.get("what")
                current_state_data["market_value"] = initial_state.values.get("market_value")
                current_state_data["value_amount"] = initial_state.values.get("value_amount")
                current_state_data["how"] = initial_state.values.get("how")
                if len(initial_state.values.get("messages", [])) > 0:
                    is_first_message = False

            # 首轮对话生成标题
            if is_first_message:
                try:
                    llm_title = initialize_llm(custom_api_key=api_key)
                    if language == "en":
                        prompt = f"Please summarize the following sentence into a very short English title of 3-6 words, without any punctuation. The title MUST be in English:\n{user_message}"
                        default_title = "New Chat"
                    else:
                        prompt = f"请将下面这句话总结为一个5-10个字的极短标题，不要包含任何标点符号：\n{user_message}"
                        default_title = "新对话"
                        
                    title_res = await llm_title.ainvoke(prompt)
                    title_text = title_res.content.strip(' "”\'\n。，')
                    if not title_text:
                        title_text = default_title
                    yield f"event: title_update\ndata: {json.dumps({'title': title_text}, ensure_ascii=False)}\n\n"
                except Exception as e:
                    print(f"⚠️ [Title Gen Error]: {e}", flush=True)
                    err_title = "New Business Discussion" if language == "en" else "新业务探讨"
                    yield f"event: title_update\ndata: {json.dumps({'title': err_title}, ensure_ascii=False)}\n\n"
            
            current_running_node = None
            hide_stream_buffer = ""
            
            async for event in compiled_graph.astream_events(inputs, config=config, version="v2"):
                kind = event["event"]
                node_name = event.get("name", "")

                # 跟踪当前正在运行的 LangGraph 节点
                if kind == "on_chain_start" and node_name in ["coach_node", "pm_node", "value_node", "expert_node", "report_node"]:
                    current_running_node = node_name

                # 通道A：文字打字机流
                if kind == "on_chat_model_stream":
                    # 过滤掉带有 hide_stream 标签的后台内部大模型调用（如生成报告正文的内部 LLM）
                    tags = event.get("tags", [])
                    if "hide_stream" in tags:
                        chunk = event["data"]["chunk"]
                        if isinstance(chunk, AIMessageChunk) and chunk.content:
                            hide_stream_buffer += chunk.content
                            if '\n' in hide_stream_buffer:
                                lines = hide_stream_buffer.split('\n')
                                for line in lines[:-1]:
                                    clean_line = line.strip()
                                    if clean_line.startswith("#") and len(clean_line) > 1:
                                        title = clean_line.lstrip("#").strip()
                                        if language == "en":
                                            progress_msg = f"\n> ⏳ Deeply expanding and drafting: **{title}**...\n\n"
                                        else:
                                            progress_msg = f"\n> ⏳ 正在深度发散与撰写：**{title}**...\n\n"
                                        yield f"event: message\ndata: {json.dumps({'chunk': progress_msg}, ensure_ascii=False)}\n\n"
                                hide_stream_buffer = lines[-1]
                                
                        # 核心修复：发送 SSE 注释作为心跳保活包
                        # 防止在生成万字长文(40-60秒)时，Nginx 或浏览器因为长时间无数据而悄悄断开连接(导致没有结果没有报错)
                        yield ": keepalive\n\n"
                        continue
                        
                    # 报告节点的内部推理（如果模型没按规范调用Tool而是直接输出JSON）不需要在前端打字机显示
                    if current_running_node != "report_node":
                        chunk = event["data"]["chunk"]
                        if isinstance(chunk, AIMessageChunk) and chunk.content:
                            data = json.dumps({"chunk": chunk.content}, ensure_ascii=False)
                            yield f"event: message\ndata: {data}\n\n"

                # 通道B：推送最新的状态 (包含当前阶段和最后生成的数据)
                # 注意：LangGraph 节点的结束事件是 on_chain_end，不是 on_node_end！
                elif kind == "on_chain_end" and node_name in ["coach_node", "pm_node", "value_node", "expert_node", "report_node"]:
                    # 不要在这里依赖 aget_state()，因为当前 superstep 未结束，checkpoint 还未落盘，会有延迟
                    # 我们直接从当前节点的输出中提取最新的状态进行覆盖
                    output = event.get("data", {}).get("output", {})
                    if isinstance(output, dict):
                        if "current_phase" in output:
                            current_state_data["current_phase"] = output["current_phase"]
                        if "why" in output:
                            current_state_data["why"] = output["why"]
                        if "what" in output:
                            current_state_data["what"] = output["what"]
                        if "market_value" in output:
                            current_state_data["market_value"] = output["market_value"]
                        if "value_amount" in output:
                            current_state_data["value_amount"] = output["value_amount"]
                        if "how" in output:
                            current_state_data["how"] = _normalize_how_data(output["how"])
                            
                    # 推送最新状态到前端
                    # 如果是报告节点完成，因为它是非流式的，我们需要手动把它的结果作为 message 推给前端
                    if node_name == "report_node":
                        messages = output.get("messages", []) if isinstance(output, dict) else []
                        if messages and getattr(messages[-1], "type", "") == "ai":
                            data = json.dumps({"chunk": getattr(messages[-1], "content", "")}, ensure_ascii=False)
                            yield f"event: message\ndata: {data}\n\n"

                    yield f"event: state_update\ndata: {json.dumps(current_state_data, ensure_ascii=False)}\n\n"
    except Exception as e:
        import traceback
        err_str = traceback.format_exc()
        print(f"❌ [Stream Error]:\n{err_str}", flush=True)
        # 把报错直接显示在前端，方便一眼看出死因
        err_data = json.dumps({"chunk": f"\n\n**[后端崩溃了]**: {str(e)}"}, ensure_ascii=False)
        yield f"event: message\ndata: {err_data}\n\n"

    yield "event: done\ndata: {}\n\n"

@router.post("/chat")
async def chat_endpoint(payload: ChatPayload):
    return StreamingResponse(
        dual_channel_stream(payload.message, payload.session_id, payload.api_key, payload.username, payload.language), 
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )

@router.get("/history/{session_id}")
async def get_history(session_id: str):
    config = {"configurable": {"thread_id": session_id}}
    try:
        async with AsyncSqliteSaver.from_conn_string("checkpoints.sqlite") as checkpointer:
            await checkpointer.setup()
            compiled_graph = workflow.compile(checkpointer=checkpointer)
            state = await compiled_graph.aget_state(config)
            
            if not state or not state.values:
                return {"messages": [], "current_phase": "COACH"}
        
        messages = []
        for msg in state.values.get("messages", []):
            msg_type = getattr(msg, "type", "unknown")
            content = getattr(msg, "content", "")
            
            # 过滤掉系统内部的工具执行日志
            if msg_type == "tool":
                continue
            # 过滤掉大模型纯调用工具而不产生可见文本的空消息
            if msg_type == "ai" and not content:
                continue
                
            messages.append({
                "role": msg_type,
                "content": content,
                "name": getattr(msg, "name", None)
            })
            
        return {
            "session_id": session_id,
            "current_phase": state.values.get("current_phase", "COACH"),
            "why": state.values.get("why"),
            "what": state.values.get("what"),
            "market_value": state.values.get("market_value"),
            "value_amount": state.values.get("value_amount"),
            "how": _normalize_how_data(state.values.get("how")),
            "messages": messages
        }
    except Exception as e:
        return {"error": str(e)}

@router.post("/check-key")
async def check_api_key(payload: CheckKeyPayload):
    try:
        llm = initialize_llm(payload.api_key)
        # 用一句话测试大模型连通性
        await llm.ainvoke("ping")
        return {"status": "success", "message": "API Key 验证通过！连接正常。"}
    except Exception as e:
        return {"status": "error", "message": f"连接失败: {str(e)}"}

import aiosqlite

@router.delete("/history/{session_id}")
async def delete_session(session_id: str):
    try:
        async with aiosqlite.connect("checkpoints.sqlite") as db:
            await db.execute("DELETE FROM checkpoints WHERE thread_id = ?", (session_id,))
            await db.execute("DELETE FROM checkpoint_writes WHERE thread_id = ?", (session_id,))
            await db.commit()
        return {"status": "success", "message": "会话已删除"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/billing/token-usage")
async def get_token_usage():
    # Mock data，后续可替换为对接内部平台的真实计费接口
    return {
        "status": "success",
        "data": {
            "total_tokens": 12580,
            "estimated_cost": 0.25,
            "currency": "USD"
        }
    }