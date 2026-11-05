from pydantic import BaseModel

from typing import Optional

class ChatPayload(BaseModel):
    message: str
    session_id: str
    api_key: Optional[str] = None
    username: Optional[str] = None  # 外部系统传进来的用户账号
    language: Optional[str] = "zh"  # 前端传递的语言选择 (zh/en)
    model_source: str = "default"  # 新增模型来源字段

class CheckKeyPayload(BaseModel):
    api_key: str
    model_source: str = "default"  # 新增模型来源字段