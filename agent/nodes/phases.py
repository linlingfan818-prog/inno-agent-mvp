import os
from langchain_core.messages import SystemMessage, ToolMessage
from pydantic import BaseModel, Field
from langchain_core.runnables.config import RunnableConfig
from agent.state import AgentState
from agent.config import initialize_llm

# --- Phase Transition Tools ---
# These are the tools the LLM can call to trigger a state transition after user confirmation.

class TransitionToPM(BaseModel):
    """当用户确认了核心痛点(Why)，并且同意进入具体产品形态(What)讨论时调用此工具。"""
    why: str = Field(description="总结提炼出的核心痛点(Why)")

class TransitionToExpert(BaseModel):
    """当用户确认了产品边界和需求(What)，并且同意进入技术路线和成本(How)探讨时调用此工具。"""
    what: str = Field(description="总结提炼出的具体创新产品形态(What)")

class TransitionToDone(BaseModel):
    """当用户确认了最终的技术路线和落地方案(How)，并且同意结题生成最终报告时调用此工具。"""
    project_name: str = Field(description="项目名称")
    how_overview: str = Field(description="技术方案概览")
    scope: str = Field(description="项目范围")
    okrs: str = Field(description="核心目标 OKRs")
    cost: str = Field(description="预算(数字或区间，例如 '130-155')")
    m1: str = Field(description="里程碑1的核心任务")
    m2: str = Field(description="里程碑2的核心任务")
    m3: str = Field(description="里程碑3的核心任务")
    m4: str = Field(description="里程碑4的核心任务")

# Helper to read prompts
def get_sys_prompt(filename: str) -> str:
    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", filename)
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    return f"【缺少提示词文件: {filename}】"

# --- Phase Nodes ---

async def coach_node(state: AgentState, config: RunnableConfig):
    sys_content = get_sys_prompt("coach.md")
    sys_msg = SystemMessage(content=sys_content)
    
    api_key = config.get("configurable", {}).get("api_key")
    llm = initialize_llm(custom_api_key=api_key)
    
    llm_with_tools = llm.bind_tools([TransitionToPM])
    response = await llm_with_tools.ainvoke([sys_msg] + state["messages"])
    
    # Check if the LLM decided to transition
    if response.tool_calls and response.tool_calls[0]["name"] == "TransitionToPM":
        # Handle the transition
        tool_call_id = response.tool_calls[0]["id"]
        why_text = response.tool_calls[0].get("args", {}).get("why", "")
        tool_msg = ToolMessage(
            tool_call_id=tool_call_id,
            name="TransitionToPM",
            content="[系统回复] 已成功切换至 PM 阶段。请向用户打招呼并开始探讨产品细节 (What)。"
        )
        return {
            "messages": [response, tool_msg],
            "current_phase": "PM",
            "why": why_text
        }
        
    return {"messages": [response]}

async def pm_node(state: AgentState, config: RunnableConfig):
    sys_content = get_sys_prompt("pm.md")
    sys_msg = SystemMessage(content=sys_content)
    
    api_key = config.get("configurable", {}).get("api_key")
    llm = initialize_llm(custom_api_key=api_key)
    
    llm_with_tools = llm.bind_tools([TransitionToExpert])
    response = await llm_with_tools.ainvoke([sys_msg] + state["messages"])
    
    if response.tool_calls and response.tool_calls[0]["name"] == "TransitionToExpert":
        tool_call_id = response.tool_calls[0]["id"]
        what_text = response.tool_calls[0].get("args", {}).get("what", "")
        tool_msg = ToolMessage(
            tool_call_id=tool_call_id,
            name="TransitionToExpert",
            content="[系统回复] 已成功切换至 EXPERT 阶段。请向用户打招呼并开始探讨技术和成本 (How)。"
        )
        return {
            "messages": [response, tool_msg],
            "current_phase": "EXPERT",
            "what": what_text
        }
        
    return {"messages": [response]}

async def expert_node(state: AgentState, config: RunnableConfig):
    sys_content = get_sys_prompt("expert.md")
    sys_msg = SystemMessage(content=sys_content)
    
    api_key = config.get("configurable", {}).get("api_key")
    llm = initialize_llm(custom_api_key=api_key)
    
    llm_with_tools = llm.bind_tools([TransitionToDone])
    response = await llm_with_tools.ainvoke([sys_msg] + state["messages"])
    
    if response.tool_calls and response.tool_calls[0]["name"] == "TransitionToDone":
        tool_call_id = response.tool_calls[0]["id"]
        args = response.tool_calls[0].get("args", {})
        tool_msg = ToolMessage(
            tool_call_id=tool_call_id,
            name="TransitionToDone",
            content="[系统回复] 已成功结题。报告生成节点将被触发。"
        )
        return {
            "messages": [response, tool_msg],
            "current_phase": "DONE",
            "how": {
                "project_name": args.get("project_name", ""),
                "how_overview": args.get("how_overview", ""),
                "scope": args.get("scope", ""),
                "okrs": args.get("okrs", ""),
                "cost": args.get("cost", ""),
                "milestones": {
                    "M1": args.get("m1", ""),
                    "M2": args.get("m2", ""),
                    "M3": args.get("m3", ""),
                    "M4": args.get("m4", "")
                }
            }
        }
        
    return {"messages": [response]}

from langchain_core.messages import AIMessage

class FinalReport(BaseModel):
    why: str = Field(description="核心痛点(Why)")
    what: str = Field(description="产品落地方案(What)")
    project_name: str = Field(description="项目名称")
    how_overview: str = Field(description="技术方案概览")
    scope: str = Field(description="项目范围")
    okrs: str = Field(description="核心目标 OKRs")
    cost: str = Field(description="预算(数字或区间，例如 '130-155')")
    m1: str = Field(description="里程碑1的核心任务")
    m2: str = Field(description="里程碑2的核心任务")
    m3: str = Field(description="里程碑3的核心任务")
    m4: str = Field(description="里程碑4的核心任务")

async def report_node(state: AgentState, config: RunnableConfig):
    api_key = config.get("configurable", {}).get("api_key")
    llm = initialize_llm(custom_api_key=api_key)

    try:
        llm_for_report = llm.bind(temperature=0.0)
        extractor = llm_for_report.with_structured_output(FinalReport)
        
        prompt = "分析以上的完整对话历史，提取并生成最终的业务画布和技术立项报告。请严格按照字段要求提取。"
        sys_msg = SystemMessage(content=prompt)
        
        result = await extractor.ainvoke([sys_msg] + state["messages"])
        
        return {
            "messages": [AIMessage(content="🎉 报告已成功生成！请查看右侧的创新画布了解详情。")],
            "why": result.why,
            "what": result.what,
            "how": {
                "project_name": result.project_name,
                "how_overview": result.how_overview,
                "scope": result.scope,
                "okrs": result.okrs,
                "cost": result.cost,
                "milestones": {
                    "M1": result.m1, 
                    "M2": result.m2,
                    "M3": result.m3,
                    "M4": result.m4
                }
            },
            "current_phase": "FINISHED"
        }
    except Exception as e:
        # Fallback: 如果大模型（特别是部分国产模型）不支持 Tool Calling，直接提取它的文本并用正则解析 JSON
        try:
            prompt_fallback = "分析以上的完整对话历史，生成最终的业务画布和技术立项报告。你必须且只能返回一段合法的 JSON 字符串，包含以下字段：why, what, project_name, how_overview, scope, okrs, cost, m1, m2, m3, m4。不要返回任何其他格式或说明文字。"
            sys_msg_fb = SystemMessage(content=prompt_fallback)
            raw_response = await llm.ainvoke([sys_msg_fb] + state["messages"])
            
            import json
            import re
            json_str = raw_response.content
            match = re.search(r'\{.*\}', json_str, re.DOTALL)
            if match:
                data = json.loads(match.group())
                return {
                    "messages": [AIMessage(content="🎉 报告已成功生成！请查看右侧的创新画布了解详情。")],
                    "why": data.get("why", ""),
                    "what": data.get("what", ""),
                    "how": {
                        "project_name": data.get("project_name", ""),
                        "how_overview": data.get("how_overview", ""),
                        "scope": data.get("scope", ""),
                        "okrs": data.get("okrs", ""),
                        "cost": data.get("cost", ""),
                        "milestones": {
                            "M1": data.get("m1", ""), 
                            "M2": data.get("m2", ""),
                            "M3": data.get("m3", ""),
                            "M4": data.get("m4", "")
                        }
                    },
                    "current_phase": "FINISHED"
                }
        except Exception as fallback_e:
            pass

        err_msg = f"生成报告时模型解析失败，错误信息: {str(e)}\n\n由于不同大模型的格式支持度不一，解析结构化数据可能失败。请再回复一次“生成报告”让我重试。"
        return {"messages": [AIMessage(content=err_msg)]}
