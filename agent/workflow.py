from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from agent.state import AgentState
from agent.nodes.phases import coach_node, pm_node, expert_node, report_node

def route_by_phase(state: AgentState) -> str:
    phase = state.get("current_phase", "COACH")
    if phase == "COACH":
        return "coach_node"
    elif phase == "PM":
        return "pm_node"
    elif phase == "EXPERT":
        return "expert_node"
    elif phase == "DONE":
        return "report_node"
    return END

# Optional route after a node finishes to handle tool calls loop
def route_after_node(state: AgentState) -> str:
    last_msg = state["messages"][-1]
    # If the last message is a ToolMessage (meaning we just transitioned phase),
    # we should loop back to START so the new phase node can run immediately and greet the user.
    if last_msg.type == "tool":
        return START
    return END

workflow = StateGraph(AgentState)
workflow.add_node("coach_node", coach_node)
workflow.add_node("pm_node", pm_node)
workflow.add_node("expert_node", expert_node)
workflow.add_node("report_node", report_node)

# START routes based on the current phase
workflow.add_conditional_edges(START, route_by_phase, {
    "coach_node": "coach_node",
    "pm_node": "pm_node",
    "expert_node": "expert_node",
    "report_node": "report_node",
    END: END
})

# Each node checks if a transition happened. 
# If a transition tool was executed, it loops back to START to run the new phase immediately.
# Otherwise, it goes to END, waiting for the next user input.
workflow.add_conditional_edges("coach_node", route_after_node, {START: START, END: END})
workflow.add_conditional_edges("pm_node", route_after_node, {START: START, END: END})
workflow.add_conditional_edges("expert_node", route_after_node, {START: START, END: END})
workflow.add_edge("report_node", END) # After report, just END.

compiled_graph = workflow.compile(checkpointer=MemorySaver())