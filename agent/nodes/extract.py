from langchain_core.messages import ToolMessage
from agent.state import AgentState
from schemas import CanvasData
# 🌟 统一引入全局唯一的 llm 单例，彻底消灭 get_llm
from agent.config import llm

# 🌟 优雅重构：利用 .with_options 动态将单例的温度调整为 0.0，
# 既保证了网络通道和 Header 依旧有效，又确保了结构化抽取的精确度
llm_for_extract = llm.bind(temperature=0.0)
extractor = llm_for_extract.with_structured_output(CanvasData)

async def extract_skill_node(state: AgentState):
    last_msg = state["messages"][-1]
    tool_call_id = last_msg.tool_calls[0]["id"]

    prompt = f"分析以下对话历史，提取核心痛点和创新方案。对话历史：\n{state['messages']}"
    canvas_result = await extractor.ainvoke(prompt)
    
    tool_msg = ToolMessage(
        tool_call_id=tool_call_id, 
        name="trigger_extract_skill", 
        content="[系统回复] 画布已由抽取专家更新完毕。请根据这个进展，继续和用户自然地对话。"
    )
    
    return {
        "why": canvas_result.why,
        "what": canvas_result.what,
        "messages": [tool_msg]
    }