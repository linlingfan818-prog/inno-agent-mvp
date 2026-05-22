from typing import Annotated, TypedDict, Dict, Any, Optional
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    current_phase: str  # "COACH", "PM", "EXPERT", or "DONE"
    why: Optional[str]
    what: Optional[str]
    how: Optional[Dict[str, Any]]