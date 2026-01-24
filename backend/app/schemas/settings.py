from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import datetime


class PromptConfigBase(BaseModel):
    system_prompt: str = Field(..., description="System prompt para o chat LLM")
    user_prompt_template: str = Field(..., description="Template de prompt do usuário")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1000, ge=1)
    model: str = Field(default="gpt-4-turbo-preview")


class PromptConfigUpdate(BaseModel):
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1)
    model: Optional[str] = None


class SettingBase(BaseModel):
    key: str
    value_json: Any
    description: Optional[str] = None


class SettingCreate(SettingBase):
    pass


class SettingUpdate(BaseModel):
    value_json: Optional[Any] = None
    description: Optional[str] = None


class SettingResponse(SettingBase):
    id: int
    version: int
    updated_at: datetime

    class Config:
        from_attributes = True
