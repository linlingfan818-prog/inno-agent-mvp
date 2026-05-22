from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from agent.state import AgentState
from agent.nodes.router import router_node
from agent.nodes.extract import extract_skill_node
from agent.nodes.proposal import proposal_skill_node

def route_after_router(state: AgentState) -> str:
    last_msg = state["messages"][-1]
    if not last_msg.tool_calls:
        return END
    
    tool_name = last_msg.tool_calls[0]["name"]
    if tool_name == "trigger_extract_skill":
        return "extract_skill"
    elif tool_name == "trigger_proposal_skill":
        return "proposal_skill"
    return END

workflow = StateGraph(AgentState)
workflow.add_node("router", router_node)
workflow.add_node("extract_skill", extract_skill_node)
workflow.add_node("proposal_skill", proposal_skill_node)

workflow.add_edge(START, "router")
workflow.add_conditional_edges("router", route_after_router, {
    "extract_skill": "extract_skill",
    "proposal_skill": "proposal_skill",
    END: END
})
workflow.add_edge("extract_skill", "router")
workflow.add_edge("proposal_skill", "router")

compiled_graph = workflow.compile(checkpointer=MemorySaver())