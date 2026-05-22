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
            
            async for event in compiled_graph.astream_events(inputs, config=config, version="v2"):
            kind = event["event"]
            node_name = event.get("name", "")

            # 通道A：文字打字机流
            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if isinstance(chunk, AIMessageChunk) and chunk.content:
                    data = json.dumps({"chunk": chunk.content}, ensure_ascii=False)
                    yield f"event: message\ndata: {data}\n\n"

            # 通道B：推送最新的状态 (包含当前阶段和最后生成的数据)
            elif kind == "on_node_end" and node_name in ["coach_node", "pm_node", "expert_node", "report_node"]:
                state = compiled_graph.get_state(config).values
                state_data = {
                    "current_phase": state.get("current_phase", "COACH"),
                    "why": state.get("why"),
                    "what": state.get("what"),
                    "how": state.get("how")
                }
                yield f"event: state_update\ndata: {json.dumps(state_data, ensure_ascii=False)}\n\n"
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
            messages.append({
                "role": getattr(msg, "type", "unknown"),
                "content": getattr(msg, "content", ""),
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