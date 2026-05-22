from typing import Annotated, TypedDict, Dict, Any
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    why: str
    what: str
    how: Dict[str, Any]