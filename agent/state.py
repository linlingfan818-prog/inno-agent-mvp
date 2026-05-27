from typing import Annotated, TypedDict, Dict, Any, Optional
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    current_phase: str  # "COACH", "PM", "VALUE", "EXPERT", or "DONE"
    why: Optional[str]
    what: Optional[str]
    market_value: Optional[str]
    value_amount: Optional[str]
    generate_value_report: Optional[bool]
    how: Optional[Dict[str, Any]]
    pdf_instructions: Optional[str]
    generate_tech_report: Optional[bool]