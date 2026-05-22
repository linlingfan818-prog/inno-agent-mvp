from pydantic import BaseModel, Field

from typing import Optional

class ChatPayload(BaseModel):
    message: str
    session_id: str
    api_key: Optional[str] = None

class CanvasData(BaseModel):
    why: str = Field(description="一句话总结业务痛点或矛盾")
    what: str = Field(description="具体的创新产品形态或技术方案")

class ProposalData(BaseModel):
    cost: str = Field(description="预估开发成本(万元)")
    m1: str = Field(description="里程碑1的核心任务")
    m2: str = Field(description="里程碑2的核心任务")
    m3: str = Field(description="里程碑3的核心任务")
    m4: str = Field(description="里程碑4的核心任务")

class CheckKeyPayload(BaseModel):
    api_key: str