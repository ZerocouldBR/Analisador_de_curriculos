from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from app.db.database import get_db
from app.core.config import settings as app_settings, VectorDBProvider, EmbeddingMode
from app.schemas.settings import (
    SettingResponse,
    SettingCreate,
    SettingUpdate,
    PromptConfigBase,
    PromptConfigUpdate,
    SystemConfigResponse,
    SystemConfigUpdateRequest,
)
from app.services.settings_service import SettingsService
from app.core.dependencies import require_permission, get_current_superuser
from app.db.models import User

router = APIRouter(prefix="/settings", tags=["settings"])


# ============================================
# System Config - Configuracoes completas
# ============================================

@router.get("/system/config", response_model=SystemConfigResponse)
def get_system_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.read"))
):
    """
    Retorna TODAS as configuracoes do sistema organizadas por categoria.

    Cada campo inclui: valor atual, tipo, descricao, se requer restart.
    O frontend renderiza formularios dinamicamente a partir desta resposta.

    **Requer permissao:** settings.read
    """
    return SettingsService.get_system_config(db)


@router.put("/system/config")
def update_system_config(
    payload: SystemConfigUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """
    Atualiza configuracoes do sistema.

    Aceita um dicionario chave:valor. Valores sao salvos como overrides
    no banco de dados. Algumas mudancas requerem restart dos servicos.

    **Requer:** Superuser
    """
    if not payload.values:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhum valor fornecido para atualizar"
        )

    result = SettingsService.update_system_config(
        db, payload.values, user_id=current_user.id
    )
    return result


@router.post("/system/config/reset")
def reset_system_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """
    Remove todos os overrides de configuracao, voltando aos valores padrao
    do arquivo .env / config.py.

    **Requer:** Superuser
    """
    deleted = SettingsService.reset_system_config(db, user_id=current_user.id)
    return {
        "reset": deleted,
        "message": "Configuracoes restauradas aos valores padrao. Reinicie os servicos."
    }


# ============================================
# Settings CRUD (server_settings generico)
# ============================================

@router.get("/", response_model=List[SettingResponse])
def list_settings(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.read"))
):
    """
    Lista todas as configurações do servidor

    **Requer permissão:** settings.read
    """
    settings = SettingsService.get_all_settings(db, skip=skip, limit=limit)
    return settings


@router.get("/{key}", response_model=SettingResponse)
def get_setting(
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.read"))
):
    """
    Obtém uma configuração específica por chave

    **Requer permissão:** settings.read
    """
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
    current_user: User = Depends(require_permission("settings.create"))
):
    """
    Cria uma nova configuração

    **Requer permissão:** settings.create
    """
    # Verificar se já existe
    existing = SettingsService.get_setting(db, setting.key)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Configuração '{setting.key}' já existe"
        )

    return SettingsService.create_setting(db, setting, user_id=current_user.id)


@router.put("/{key}", response_model=SettingResponse)
def update_setting(
    key: str,
    setting_update: SettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.update"))
):
    """
    Atualiza uma configuração existente

    **Requer permissão:** settings.update
    """
    updated = SettingsService.update_setting(db, key, setting_update, user_id=current_user.id)
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
    current_user: User = Depends(require_permission("settings.delete"))
):
    """
    Remove uma configuração

    **Requer permissão:** settings.delete
    """
    deleted = SettingsService.delete_setting(db, key, user_id=current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuração '{key}' não encontrada"
        )


# Endpoints específicos para prompts do chat LLM

@router.get("/prompts/chat", response_model=PromptConfigBase)
def get_chat_prompts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.read"))
):
    """
    Obtém a configuração de prompts do chat LLM

    **Requer permissão:** settings.read
    """
    setting = SettingsService.get_or_create_prompt_config(db)
    return PromptConfigBase(**setting.value_json)


@router.put("/prompts/chat", response_model=PromptConfigBase)
def update_chat_prompts(
    prompt_config: PromptConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.update"))
):
    """
    Atualiza a configuração de prompts do chat LLM

    **Requer permissão:** settings.update
    """
    # Obter configuração atual
    setting = SettingsService.get_or_create_prompt_config(db)

    # Atualizar apenas os campos fornecidos
    current_config = setting.value_json
    update_data = prompt_config.model_dump(exclude_unset=True)
    current_config.update(update_data)

    # Salvar atualização
    setting_update = SettingUpdate(value_json=current_config)
    updated = SettingsService.update_setting(db, "chat_llm_prompts", setting_update, user_id=current_user.id)

    return PromptConfigBase(**updated.value_json)


@router.post("/prompts/chat/reset", response_model=PromptConfigBase)
def reset_chat_prompts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.update"))
):
    """
    Restaura os prompts do chat LLM para os valores padrão

    **Requer permissão:** settings.update
    """
    key = "chat_llm_prompts"

    # Deletar configuração atual se existir
    SettingsService.delete_setting(db, key, user_id=current_user.id)

    # Recriar com valores padrão
    setting = SettingsService.get_or_create_prompt_config(db)

    return PromptConfigBase(**setting.value_json)


# ============================================
# Painel Administrativo - Visao Geral
# ============================================

@router.get("/admin/overview")
def admin_overview(
    current_user: User = Depends(get_current_superuser),
):
    """
    Visao geral do sistema para administradores

    Retorna todas as configuracoes ativas do sistema incluindo:
    - Modo de vetorizacao (API ou code/local)
    - Provedor de vector DB
    - Configuracoes de IA e precos
    - Multi-tenant
    - Branding

    **Requer:** Superuser
    """
    return {
        "system": {
            "app_name": app_settings.app_name,
            "app_version": app_settings.app_version,
            "debug": app_settings.debug,
        },
        "multi_tenant": {
            "enabled": app_settings.multi_tenant_enabled,
            "default_company_name": app_settings.default_company_name,
        },
        "branding": {
            "logo_max_size_kb": app_settings.company_logo_max_size_kb,
            "logo_allowed_formats": app_settings.company_logo_allowed_formats,
            "logo_path": app_settings.company_logo_path,
        },
        "vectorization": {
            "mode": app_settings.embedding_mode.value,
            "mode_description": "API externa (OpenAI, etc.)" if app_settings.embedding_mode == EmbeddingMode.API else "Local (sentence-transformers, custo zero)",
            "api_model": app_settings.embedding_model,
            "local_model": app_settings.embedding_local_model,
            "local_device": app_settings.embedding_local_device,
            "active_dimensions": app_settings.active_embedding_dimensions,
            "batch_size": app_settings.embedding_batch_size,
            "max_chars": app_settings.embedding_max_chars,
        },
        "vector_db": {
            "provider": app_settings.vector_db_provider.value,
            "available_providers": [p.value for p in VectorDBProvider],
            "distance_metric": app_settings.pgvector_distance_metric,
            "hnsw_enabled": app_settings.enable_hnsw_index,
        },
        "ai_pricing": {
            "enabled": app_settings.ai_pricing_enabled,
            "currency": app_settings.ai_currency,
            "exchange_rate": app_settings.ai_currency_exchange_rate,
            "monthly_token_limit": app_settings.ai_monthly_token_limit,
            "monthly_cost_limit": app_settings.ai_monthly_cost_limit,
            "prices_per_1k_tokens": {
                "embedding_input": app_settings.ai_price_embedding_input,
                "llm_input": app_settings.ai_price_llm_input,
                "llm_output": app_settings.ai_price_llm_output,
                "chat_input": app_settings.ai_price_chat_input,
                "chat_output": app_settings.ai_price_chat_output,
            },
        },
        "llm": {
            "chat_model": app_settings.chat_model,
            "temperature": app_settings.llm_temperature,
            "max_tokens": app_settings.llm_max_tokens,
            "max_retries": app_settings.llm_max_retries,
        },
        "search": {
            "vector_threshold": app_settings.vector_search_threshold,
            "vector_limit": app_settings.vector_search_limit,
            "hybrid_weights": {
                "vector": app_settings.hybrid_vector_weight,
                "text": app_settings.hybrid_text_weight,
                "filter": app_settings.hybrid_filter_weight,
                "domain": app_settings.hybrid_domain_weight,
            },
        },
        "security": {
            "pii_encryption": app_settings.enable_pii_encryption,
            "rate_limit_per_minute": app_settings.rate_limit_per_minute,
            "access_token_expire_minutes": app_settings.access_token_expire_minutes,
        },
    }
