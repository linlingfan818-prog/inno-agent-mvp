import os
from langchain_core.messages import SystemMessage
from agent.state import AgentState
from agent.config import llm

# 1. 定义空壳工具（保持你原有的设计，用于触发 Agent 的路由控制权）
router_tools = [
    {
        "type": "function",
        "function": {
            "name": "trigger_extract_skill",
            "description": "当在对话中明确了用户的'痛点(why)'和'想法(what)'时，调用此工具将任务分发给后台抽取专家。",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "trigger_proposal_skill",
            "description": "当技术细节、人力预算探讨成熟，可以生成立项方案时，调用此工具分发给立项专家。",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]

def get_sys_prompt():
    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "doraoumen_role.md")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()

async def router_node(state: AgentState):
    """
    重构后的标准路由节点：
    利用 LangChain 的 bind_tools 将决策句柄下发给大模型
    """
    sys_msg = SystemMessage(content=get_sys_prompt())
    
    # 🌟 核心修正：利用 LangChain 统一的 bind_tools 动态给 LLM 披上工具外衣
    # 这样大模型在思考时，就会根据 doraoumen_role.md 的指示，在合适的时候返回 tool_calls
    llm_with_tools = llm.bind_tools(router_tools)
    
    # 使用绑定了工具的模型实例发起异步调用
    response = await llm_with_tools.ainvoke([sys_msg] + state["messages"])
    
    return {"messages": [response]}