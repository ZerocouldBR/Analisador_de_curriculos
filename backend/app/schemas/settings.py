from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import datetime


class PromptConfigBase(BaseModel):
    system_prompt: str = Field(..., description="System prompt para o chat LLM")
    user_prompt_template: str = Field(..., description="Template de prompt do usuário")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1000, ge=1)
    model: str = Field(default="gpt-4o")


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


# ============================================================
# System Config - Configuracoes completas do sistema via frontend
# ============================================================

class SystemConfigField(BaseModel):
    """Um campo de configuracao individual"""
    key: str
    label: str
    type: str  # text, number, boolean, select, password, textarea, list_int, list_str
    description: str = ""
    restart_required: bool = False
    sensitive: bool = False
    value: Any = None
    options: Optional[list[str]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None
    placeholder: str = ""
    group: Optional[str] = None


class SystemConfigGroup(BaseModel):
    """Um sub-grupo dentro de uma categoria (ex: provedor de banco vetorial)"""
    key: str
    label: str
    description: str = ""


class SystemConfigCategory(BaseModel):
    """Uma categoria de configuracoes"""
    category: str
    label: str
    icon: str
    description: str
    fields: list[SystemConfigField]
    groups: Optional[list[SystemConfigGroup]] = None


class SystemConfigResponse(BaseModel):
    """Resposta completa com todas as categorias e valores atuais"""
    categories: list[SystemConfigCategory]
    has_overrides: bool = False
    override_keys: list[str] = []


class SystemConfigUpdateRequest(BaseModel):
    """Payload para atualizar configuracoes do sistema"""
    values: dict[str, Any] = Field(
        ...,
        description="Dicionario chave:valor com as configuracoes a serem atualizadas"
    )
