import os
from langchain_core.messages import SystemMessage, ToolMessage
from agent.state import AgentState
from schemas import ProposalData
from agent.config import llm

# 使用标准的 .bind 方法覆盖温度
llm_for_proposal = llm.bind(temperature=0.2)
generator = llm_for_proposal.with_structured_output(ProposalData)

def get_sys_prompt():
    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "proposal_rules.md")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()

# 🌟 核心：确保这里的名字和 workflow.py 导入的名字一模一样，且完全暴露
async def proposal_skill_node(state: AgentState):
    last_msg = state["messages"][-1]
    tool_call_id = last_msg.tool_calls[0]["id"]

    sys_content = get_sys_prompt() + f"\n\n当前上下文 -> Why: {state.get('why')}, What: {state.get('what')}"
    sys_msg = SystemMessage(content=sys_content)
    
    proposal_result = await generator.ainvoke([sys_msg] + state["messages"])

    tool_msg = ToolMessage(
        tool_call_id=tool_call_id, 
        name="trigger_proposal_skill", 
        content="[系统回复] 立项专家已生成技术方案，数据已推送到侧边栏。请用一句话通知用户查看。"
    )

    return {
        "how": {
            "cost": proposal_result.cost,
            "milestones": {"M1": proposal_result.m1, "M2": proposal_result.m2}
        },
        "messages": [tool_msg]
    }