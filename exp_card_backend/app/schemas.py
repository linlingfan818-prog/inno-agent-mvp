from pydantic import BaseModel, Field
from typing import Any, List, Dict, Optional


class ParsedCharter(BaseModel):
    project_name: str = ""
    project_scope: str = ""
    stakeholders_now: List[str] = Field(default_factory=list)
    stakeholders_future: List[str] = Field(default_factory=list)
    objectives: List[str] = Field(default_factory=list)
    key_results: List[str] = Field(default_factory=list)
    milestones: List[str] = Field(default_factory=list)
    value_points: List[str] = Field(default_factory=list)
    cost_points: List[str] = Field(default_factory=list)
    raw_text: str = ""
    parse_notes: str = ""


class UploadParseResponse(BaseModel):
    session_id: str
    filename: str
    extracted_text: str
    parsed_charter: ParsedCharter
    warnings: List[str] = Field(default_factory=list)


class ConfirmRequest(BaseModel):
    session_id: str
    parsed_charter: ParsedCharter


class GenerateRequest(BaseModel):
    session_id: str
    parsed_charter: ParsedCharter


class CriticalAcceptanceStandard(BaseModel):
    environment_and_prerequisites: str = ""
    must_have_metrics: List[str] = Field(default_factory=list)
    red_lines: List[str] = Field(default_factory=list)


class ExperimentCard(BaseModel):
    project_name: str
    core_hypothesis: str
    hypothesis_mapping: List[Dict[str, str]] = Field(default_factory=list)
    experiment_cycle: str
    experiment_method: str
    target_users: List[str] = Field(default_factory=list)
    why_statement: str = ""
    what_solution: str = ""
    value_statement: str = ""
    experiment_steps: List[str] = Field(default_factory=list)
    success_metrics: List[str] = Field(default_factory=list)
    risks_and_watchouts: List[str] = Field(default_factory=list)
    completion_checklist: List[str] = Field(default_factory=list)
    critical_acceptance_standard: Optional[CriticalAcceptanceStandard] = None
    output_summary: str = ""


class GenerateResponse(BaseModel):
    session_id: str
    experiment_card: ExperimentCard
    docx_download_url: str
    raw_model_output: str


class HealthResponse(BaseModel):
    status: str
    app_name: str
    model: str
    image_input_enabled: bool


class ErrorPayload(BaseModel):
    detail: str
    extra: Optional[Dict[str, Any]] = None