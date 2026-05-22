import os
from langchain_core.messages import SystemMessage, ToolMessage
from pydantic import BaseModel, Field
from agent.state import AgentState
from agent.config import llm

# --- Phase Transition Tools ---
# These are the tools the LLM can call to trigger a state transition after user confirmation.

class TransitionToPM(BaseModel):
    """当用户确认了核心痛点(Why)，并且同意进入具体产品形态(What)讨论时调用此工具。"""
    pass

class TransitionToExpert(BaseModel):
    """当用户确认了产品边界和需求(What)，并且同意进入技术路线和成本(How)探讨时调用此工具。"""
    pass

class TransitionToDone(BaseModel):
    """当用户确认了最终的技术路线和落地方案(How)，并且同意结题生成最终报告时调用此工具。"""
    pass

# Helper to read prompts
def get_sys_prompt(filename: str) -> str:
    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", filename)
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    return f"【缺少提示词文件: {filename}】"

# --- Phase Nodes ---

async def coach_node(state: AgentState):
    sys_content = get_sys_prompt("coach.md")
    sys_msg = SystemMessage(content=sys_content)
    
    llm_with_tools = llm.bind_tools([TransitionToPM])
    response = await llm_with_tools.ainvoke([sys_msg] + state["messages"])
    
    # Check if the LLM decided to transition
    if response.tool_calls and response.tool_calls[0]["name"] == "TransitionToPM":
        # Handle the transition
        tool_call_id = response.tool_calls[0]["id"]
        tool_msg = ToolMessage(
            tool_call_id=tool_call_id,
            name="TransitionToPM",
            content="[系统回复] 已成功切换至 PM 阶段。请向用户打招呼并开始探讨产品细节 (What)。"
        )
        return {
            "messages": [response, tool_msg],
            "current_phase": "PM"
        }
        
    return {"messages": [response]}

async def pm_node(state: AgentState):
    sys_content = get_sys_prompt("pm.md")
    sys_msg = SystemMessage(content=sys_content)
    
    llm_with_tools = llm.bind_tools([TransitionToExpert])
    response = await llm_with_tools.ainvoke([sys_msg] + state["messages"])
    
    if response.tool_calls and response.tool_calls[0]["name"] == "TransitionToExpert":
        tool_call_id = response.tool_calls[0]["id"]
        tool_msg = ToolMessage(
            tool_call_id=tool_call_id,
            name="TransitionToExpert",
            content="[系统回复] 已成功切换至 EXPERT 阶段。请向用户打招呼并开始探讨技术和成本 (How)。"
        )
        return {
            "messages": [response, tool_msg],
            "current_phase": "EXPERT"
        }
        
    return {"messages": [response]}

async def expert_node(state: AgentState):
    sys_content = get_sys_prompt("expert.md")
    sys_msg = SystemMessage(content=sys_content)
    
    llm_with_tools = llm.bind_tools([TransitionToDone])
    response = await llm_with_tools.ainvoke([sys_msg] + state["messages"])
    
    if response.tool_calls and response.tool_calls[0]["name"] == "TransitionToDone":
        tool_call_id = response.tool_calls[0]["id"]
        tool_msg = ToolMessage(
            tool_call_id=tool_call_id,
            name="TransitionToDone",
            content="[系统回复] 已成功结题。报告生成节点将被触发。"
        )
        return {
            "messages": [response, tool_msg],
            "current_phase": "DONE"
        }
        
    return {"messages": [response]}

# --- Report Node ---
from schemas import CanvasData, ProposalData

class FinalReport(BaseModel):
    canvas: CanvasData
    proposal: ProposalData

async def report_node(state: AgentState):
    # Use structured output to summarize the entire conversation into the final data
    llm_for_report = llm.bind(temperature=0.0)
    extractor = llm_for_report.with_structured_output(FinalReport)
    
    prompt = "分析以上的完整对话历史，提取并生成最终的业务画布和技术立项报告。"
    sys_msg = SystemMessage(content=prompt)
    
    result = await extractor.ainvoke([sys_msg] + state["messages"])
    
    return {
        "why": result.canvas.why,
        "what": result.canvas.what,
        "how": {
            "cost": result.proposal.cost,
            "milestones": {
                "M1": result.proposal.m1, 
                "M2": result.proposal.m2,
                "M3": result.proposal.m3,
                "M4": result.proposal.m4
            }
        },
        "current_phase": "FINISHED"
    }
