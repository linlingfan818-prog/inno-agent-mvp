import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessageChunk
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from agent.workflow import workflow
from schemas import ChatPayload, CheckKeyPayload
from agent.config import initialize_llm

router = APIRouter()

async def dual_channel_stream(user_message: str, session_id: str, api_key: str = None):
    config = {"configurable": {"thread_id": session_id, "api_key": api_key}}
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
                "how": None
            }
            initial_state = await compiled_graph.aget_state(config)
            if initial_state and initial_state.values:
                current_state_data["current_phase"] = initial_state.values.get("current_phase", "COACH")
                current_state_data["why"] = initial_state.values.get("why")
                current_state_data["what"] = initial_state.values.get("what")
                current_state_data["how"] = initial_state.values.get("how")
            
            async for event in compiled_graph.astream_events(inputs, config=config, version="v2"):
                kind = event["event"]
                node_name = event.get("name", "")

                # 通道A：文字打字机流
                if kind == "on_chat_model_stream":
                    # 报告节点的内部推理（如果模型没按规范调用Tool而是直接输出JSON）不需要在前端打字机显示
                    if node_name != "report_node":
                        chunk = event["data"]["chunk"]
                        if isinstance(chunk, AIMessageChunk) and chunk.content:
                            data = json.dumps({"chunk": chunk.content}, ensure_ascii=False)
                            yield f"event: message\ndata: {data}\n\n"

                # 通道B：推送最新的状态 (包含当前阶段和最后生成的数据)
                elif kind == "on_node_end" and node_name in ["coach_node", "pm_node", "expert_node", "report_node"]:
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
                        if "how" in output:
                            current_state_data["how"] = output["how"]
                    
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
        dual_channel_stream(payload.message, payload.session_id, payload.api_key), 
        media_type="text/event-stream"
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
            "how": state.values.get("how"),
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