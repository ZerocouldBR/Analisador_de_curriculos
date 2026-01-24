from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.schemas.settings import (
    SettingResponse,
    SettingCreate,
    SettingUpdate,
    PromptConfigBase,
    PromptConfigUpdate
)
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/", response_model=List[SettingResponse])
def list_settings(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Lista todas as configurações do servidor"""
    settings = SettingsService.get_all_settings(db, skip=skip, limit=limit)
    return settings


@router.get("/{key}", response_model=SettingResponse)
def get_setting(key: str, db: Session = Depends(get_db)):
    """Obtém uma configuração específica por chave"""
    setting = SettingsService.get_setting(db, key)
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuração '{key}' não encontrada"
        )
    return setting


@router.post("/", response_model=SettingResponse, status_code=status.HTTP_201_CREATED)
def create_setting(
    setting: SettingCreate,
    db: Session = Depends(get_db),
    # TODO: Adicionar autenticação e obter user_id do token
):
    """Cria uma nova configuração"""
    # Verificar se já existe
    existing = SettingsService.get_setting(db, setting.key)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Configuração '{setting.key}' já existe"
        )

    return SettingsService.create_setting(db, setting)


@router.put("/{key}", response_model=SettingResponse)
def update_setting(
    key: str,
    setting_update: SettingUpdate,
    db: Session = Depends(get_db),
    # TODO: Adicionar autenticação e obter user_id do token
):
    """Atualiza uma configuração existente"""
    updated = SettingsService.update_setting(db, key, setting_update)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuração '{key}' não encontrada"
        )
    return updated


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_setting(
    key: str,
    db: Session = Depends(get_db),
    # TODO: Adicionar autenticação e obter user_id do token
):
    """Remove uma configuração"""
    deleted = SettingsService.delete_setting(db, key)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuração '{key}' não encontrada"
        )


# Endpoints específicos para prompts do chat LLM

@router.get("/prompts/chat", response_model=PromptConfigBase)
def get_chat_prompts(db: Session = Depends(get_db)):
    """Obtém a configuração de prompts do chat LLM"""
    setting = SettingsService.get_or_create_prompt_config(db)
    return PromptConfigBase(**setting.value_json)


@router.put("/prompts/chat", response_model=PromptConfigBase)
def update_chat_prompts(
    prompt_config: PromptConfigUpdate,
    db: Session = Depends(get_db),
    # TODO: Adicionar autenticação e obter user_id do token
):
    """Atualiza a configuração de prompts do chat LLM"""
    # Obter configuração atual
    setting = SettingsService.get_or_create_prompt_config(db)

    # Atualizar apenas os campos fornecidos
    current_config = setting.value_json
    update_data = prompt_config.model_dump(exclude_unset=True)
    current_config.update(update_data)

    # Salvar atualização
    setting_update = SettingUpdate(value_json=current_config)
    updated = SettingsService.update_setting(db, "chat_llm_prompts", setting_update)

    return PromptConfigBase(**updated.value_json)


@router.post("/prompts/chat/reset", response_model=PromptConfigBase)
def reset_chat_prompts(
    db: Session = Depends(get_db),
    # TODO: Adicionar autenticação e obter user_id do token
):
    """Restaura os prompts do chat LLM para os valores padrão"""
    key = "chat_llm_prompts"

    # Deletar configuração atual se existir
    SettingsService.delete_setting(db, key)

    # Recriar com valores padrão
    setting = SettingsService.get_or_create_prompt_config(db)

    return PromptConfigBase(**setting.value_json)
