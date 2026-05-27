from langgraph.graph import StateGraph, START, END
from agent.state import AgentState
from agent.nodes.phases import coach_node, pm_node, expert_node, report_node, value_node, value_report_node

def route_by_phase(state: AgentState) -> str:
    phase = state.get("current_phase", "COACH")
    if phase == "COACH":
        return "coach_node"
    elif phase == "PM":
        return "pm_node"
    elif phase == "VALUE":
        return "value_node"
    elif phase == "VALUE_REPORT":
        return "value_report_node"
    elif phase == "EXPERT":
        return "expert_node"
    elif phase == "DONE":
        return "report_node"
    return END

# Optional route after a node finishes to handle tool calls loop
def route_after_node(state: AgentState) -> str:
    last_msg = state["messages"][-1]
    # If the last message is a ToolMessage (meaning we just transitioned phase),
    # we should run the new phase node immediately and greet the user.
    if last_msg.type == "tool":
        phase = state.get("current_phase", "COACH")
        if phase == "COACH":
            return "coach_node"
        elif phase == "PM":
            return "pm_node"
        elif phase == "VALUE":
            return "value_node"
        elif phase == "VALUE_REPORT":
            return "value_report_node"
        elif phase == "EXPERT":
            return "expert_node"
        elif phase == "DONE":
            return "report_node"
    return END

workflow = StateGraph(AgentState)
workflow.add_node("coach_node", coach_node)
workflow.add_node("pm_node", pm_node)
workflow.add_node("value_node", value_node)
workflow.add_node("value_report_node", value_report_node)
workflow.add_node("expert_node", expert_node)
workflow.add_node("report_node", report_node)

# START routes based on the current phase
workflow.add_conditional_edges(START, route_by_phase, {
    "coach_node": "coach_node",
    "pm_node": "pm_node",
    "value_node": "value_node",
    "value_report_node": "value_report_node",
    "expert_node": "expert_node",
    "report_node": "report_node",
    END: END
})

# Each node checks if a transition happened. 
# If a transition tool was executed, it goes to the new phase directly.
# Otherwise, it goes to END, waiting for the next user input.
path_map = {
    "coach_node": "coach_node",
    "pm_node": "pm_node",
    "value_node": "value_node",
    "value_report_node": "value_report_node",
    "expert_node": "expert_node",
    "report_node": "report_node",
    END: END
}
workflow.add_conditional_edges("coach_node", route_after_node, path_map)
workflow.add_conditional_edges("pm_node", route_after_node, path_map)
workflow.add_conditional_edges("value_node", route_after_node, path_map)
workflow.add_edge("value_report_node", "expert_node")
workflow.add_conditional_edges("expert_node", route_after_node, path_map)
workflow.add_edge("report_node", END)