from langgraph.graph import StateGraph, START, END
from agent.state import AgentState
from agent.nodes.phases import coach_node, pm_node, expert_node, value_node

# 阶段 → 节点。FINISHED 之后仍由 expert_node 承接，允许继续探讨或重新生成报告
PHASE_TO_NODE = {
    "COACH": "coach_node",
    "PM": "pm_node",
    "VALUE": "value_node",
    "EXPERT": "expert_node",
    "FINISHED": "expert_node",
}


def route_by_phase(state: AgentState) -> str:
    return PHASE_TO_NODE.get(state.get("current_phase", "COACH"), END)


# Optional route after a node finishes to handle tool calls loop
def route_after_node(state: AgentState) -> str:
    last_msg = state["messages"][-1]
    # If the last message is a ToolMessage (meaning we just transitioned phase or executed a universal tool),
    # we should run the current phase node immediately and let LLM reply based on tool output.
    if last_msg.type == "tool":
        return PHASE_TO_NODE.get(state.get("current_phase", "COACH"), END)
    return END


workflow = StateGraph(AgentState)
workflow.add_node("coach_node", coach_node)
workflow.add_node("pm_node", pm_node)
workflow.add_node("value_node", value_node)
workflow.add_node("expert_node", expert_node)

path_map = {name: name for name in set(PHASE_TO_NODE.values())}
path_map[END] = END

# START routes based on the current phase
workflow.add_conditional_edges(START, route_by_phase, path_map)

# Each node checks if a transition happened.
# If a transition tool was executed, it goes to the new phase directly.
# Otherwise, it goes to END, waiting for the next user input.
for node in ("coach_node", "pm_node", "value_node", "expert_node"):
    workflow.add_conditional_edges(node, route_after_node, path_map)
