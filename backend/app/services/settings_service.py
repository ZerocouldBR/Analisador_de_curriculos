import copy
import json
import logging
from typing import Optional, Any

from sqlalchemy.orm import Session

from app.db.models import ServerSettings, AuditLog
from app.schemas.settings import SettingCreate, SettingUpdate
from app.core.config import settings as app_settings
from app.core.config_manifest import CONFIG_MANIFEST, get_all_field_keys, get_field_metadata

logger = logging.getLogger(__name__)

# Chave no banco para guardar overrides de configuracao do sistema
SYSTEM_CONFIG_KEY = "system_config_overrides"


class SettingsService:
    @staticmethod
    def get_setting(db: Session, key: str) -> Optional[ServerSettings]:
        """Obtem uma configuracao por chave"""
        return db.query(ServerSettings).filter(ServerSettings.key == key).first()

    @staticmethod
    def get_all_settings(db: Session, skip: int = 0, limit: int = 100) -> list[ServerSettings]:
        """Lista todas as configuracoes"""
        return db.query(ServerSettings).offset(skip).limit(limit).all()

    @staticmethod
    def create_setting(
        db: Session,
        setting: SettingCreate,
        user_id: Optional[int] = None
    ) -> ServerSettings:
        """Cria uma nova configuracao"""
        db_setting = ServerSettings(
            key=setting.key,
            value_json=setting.value_json,
            description=setting.description,
            updated_by=user_id
        )
        db.add(db_setting)
        db.commit()
        db.refresh(db_setting)

        # Registrar no audit log
        audit = AuditLog(
            user_id=user_id,
            action="create",
            entity="server_settings",
            entity_id=db_setting.id,
            metadata_json={"key": setting.key}
        )
        db.add(audit)
        db.commit()

        return db_setting

    @staticmethod
    def update_setting(
        db: Session,
        key: str,
        setting_update: SettingUpdate,
        user_id: Optional[int] = None
    ) -> Optional[ServerSettings]:
        """Atualiza uma configuracao existente"""
        db_setting = SettingsService.get_setting(db, key)
        if not db_setting:
            return None

        update_data = setting_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_setting, field, value)

        db_setting.version += 1
        db_setting.updated_by = user_id

        db.commit()
        db.refresh(db_setting)

        # Registrar no audit log
        audit = AuditLog(
            user_id=user_id,
            action="update",
            entity="server_settings",
            entity_id=db_setting.id,
            metadata_json={"key": key, "updated_fields": list(update_data.keys())}
        )
        db.add(audit)
        db.commit()

        return db_setting

    @staticmethod
    def delete_setting(
        db: Session,
        key: str,
        user_id: Optional[int] = None
    ) -> bool:
        """Remove uma configuracao"""
        db_setting = SettingsService.get_setting(db, key)
        if not db_setting:
            return False

        setting_id = db_setting.id

        # Registrar no audit log antes de deletar
        audit = AuditLog(
            user_id=user_id,
            action="delete",
            entity="server_settings",
            entity_id=setting_id,
            metadata_json={"key": key}
        )
        db.add(audit)

        db.delete(db_setting)
        db.commit()

        return True

    @staticmethod
    def get_or_create_prompt_config(db: Session) -> ServerSettings:
        """Obtem ou cria a configuracao de prompts do chat LLM"""
        key = "chat_llm_prompts"
        setting = SettingsService.get_setting(db, key)

        if not setting:
            default_config = {
                "system_prompt": (
                    "Você é um assistente de RH especializado em análise de currículos. "
                    "Sua função é ajudar a encontrar os melhores candidatos com base nos requisitos fornecidos. "
                    "Sempre forneça respostas baseadas em evidências dos currículos analisados."
                ),
                "user_prompt_template": (
                    "Com base nos currículos disponíveis, {query}\n\n"
                    "Por favor, liste os candidatos mais relevantes com suas qualificações e experiências específicas."
                ),
                "temperature": 0.7,
                "max_tokens": 1000,
                "model": "gpt-4-turbo-preview"
            }

            setting = SettingsService.create_setting(
                db,
                SettingCreate(
                    key=key,
                    value_json=default_config,
                    description="Configuração de prompts para o chat LLM"
                )
            )

        return setting

    # ================================================================
    # System Config - Configuracao completa via frontend
    # ================================================================

    @staticmethod
    def _get_config_value(key: str) -> Any:
        """Obtem o valor atual de uma configuracao do config.py"""
        value = getattr(app_settings, key, None)
        # Converter enums para string
        if hasattr(value, 'value'):
            value = value.value
        return value

    @staticmethod
    def _mask_sensitive(value: Any) -> str:
        """Mascara valor sensivel para exibicao"""
        if value is None or value == "":
            return ""
        s = str(value)
        if len(s) <= 8:
            return "****"
        return s[:4] + "****" + s[-4:]

    @staticmethod
    def get_system_config_overrides(db: Session) -> dict[str, Any]:
        """Obtem overrides salvos no banco de dados"""
        setting = SettingsService.get_setting(db, SYSTEM_CONFIG_KEY)
        if setting and setting.value_json:
            return setting.value_json
        return {}

    @staticmethod
    def get_system_config(db: Session) -> dict:
        """
        Retorna TODA a configuracao do sistema organizada por categoria.

        Merge: config.py defaults <- env vars <- DB overrides
        """
        overrides = SettingsService.get_system_config_overrides(db)
        override_keys = list(overrides.keys())

        categories = []
        for cat_def in CONFIG_MANIFEST:
            fields = []
            for field_def in cat_def["fields"]:
                key = field_def["key"]
                # Valor efetivo: DB override > config.py (que ja inclui env vars)
                if key in overrides:
                    value = overrides[key]
                else:
                    value = SettingsService._get_config_value(key)

                # Mascarar campos sensiveis
                display_value = value
                if field_def.get("sensitive") and value:
                    display_value = SettingsService._mask_sensitive(value)

                field_data = {
                    **field_def,
                    "value": display_value,
                }
                fields.append(field_data)

            cat_data = {
                "category": cat_def["category"],
                "label": cat_def["label"],
                "icon": cat_def["icon"],
                "description": cat_def["description"],
                "fields": fields,
            }
            if "groups" in cat_def:
                cat_data["groups"] = cat_def["groups"]
            categories.append(cat_data)

        return {
            "categories": categories,
            "has_overrides": len(override_keys) > 0,
            "override_keys": override_keys,
        }

    @staticmethod
    def update_system_config(
        db: Session,
        values: dict[str, Any],
        user_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Atualiza configuracoes do sistema.

        Valores sao salvos como overrides no banco de dados.
        Campos sensiveis com valor mascarado (****) sao ignorados.
        """
        valid_keys = set(get_all_field_keys())
        current_overrides = SettingsService.get_system_config_overrides(db)
        updated_keys = []

        for key, value in values.items():
            if key not in valid_keys:
                logger.warning(f"Chave de configuracao desconhecida ignorada: {key}")
                continue

            # Ignorar campos sensiveis que vieram mascarados
            if isinstance(value, str) and "****" in value:
                continue

            # Converter tipos especiais
            metadata = get_field_metadata(key)
            if metadata:
                field_type = metadata.get("type", "text")
                if field_type == "list_int" and isinstance(value, str):
                    value = [int(x.strip()) for x in value.split(",") if x.strip()]
                elif field_type == "list_str" and isinstance(value, str):
                    value = [x.strip() for x in value.split(",") if x.strip()]
                elif field_type == "number":
                    if isinstance(value, str):
                        value = float(value) if "." in value else int(value)
                elif field_type == "boolean":
                    if isinstance(value, str):
                        value = value.lower() in ("true", "1", "yes", "sim")

            current_overrides[key] = value
            updated_keys.append(key)

        # Salvar no banco
        setting = SettingsService.get_setting(db, SYSTEM_CONFIG_KEY)
        if setting:
            setting_update = SettingUpdate(
                value_json=current_overrides,
                description="Overrides de configuracao do sistema (editados via frontend)"
            )
            SettingsService.update_setting(db, SYSTEM_CONFIG_KEY, setting_update, user_id=user_id)
        else:
            SettingsService.create_setting(
                db,
                SettingCreate(
                    key=SYSTEM_CONFIG_KEY,
                    value_json=current_overrides,
                    description="Overrides de configuracao do sistema (editados via frontend)"
                ),
                user_id=user_id,
            )

        # Audit log detalhado
        audit = AuditLog(
            user_id=user_id,
            action="update_system_config",
            entity="server_settings",
            entity_id=0,
            metadata_json={"updated_keys": updated_keys, "total_overrides": len(current_overrides)}
        )
        db.add(audit)
        db.commit()

        # Invalidar cache de prompts se algum prompt foi alterado
        prompt_keys = {
            "prompt_llm_general", "prompt_llm_production", "prompt_llm_logistics",
            "prompt_llm_quality", "prompt_chat_default", "prompt_chat_job_analysis",
            "domain_keywords_production", "domain_keywords_logistics", "domain_keywords_quality",
        }
        if prompt_keys.intersection(updated_keys):
            try:
                from app.services.prompt_service import PromptService
                PromptService.invalidate_cache()
            except ImportError:
                pass

        # Aplicar overrides ao singleton de settings em runtime
        # (apenas campos que NAO requerem restart)
        runtime_applied = []
        restart_needed = False
        for key in updated_keys:
            meta = get_field_metadata(key)
            if meta and meta.get("restart_required"):
                restart_needed = True
            else:
                # Aplicar diretamente ao singleton de settings
                try:
                    if hasattr(app_settings, key):
                        current_val = getattr(app_settings, key)
                        new_val = current_overrides[key]
                        # Converter enums se necessario
                        if hasattr(current_val, 'value') and isinstance(new_val, str):
                            enum_class = type(current_val)
                            try:
                                new_val = enum_class(new_val)
                            except ValueError:
                                pass
                        object.__setattr__(app_settings, key, new_val)
                        runtime_applied.append(key)
                except Exception as e:
                    logger.warning(f"Nao foi possivel aplicar '{key}' em runtime: {e}")

        if runtime_applied:
            logger.info(f"Configuracoes aplicadas em runtime: {runtime_applied}")

        # Reset vector store registry se configuracoes de vector DB mudaram
        vector_keys = {
            "pgvector_enabled", "supabase_enabled", "qdrant_enabled",
            "vector_db_primary", "pgvector_distance_metric",
        }
        if vector_keys.intersection(updated_keys):
            try:
                from app.vectorstore.factory import reset_vector_store
                reset_vector_store()
            except ImportError:
                pass

        return {
            "updated_keys": updated_keys,
            "total_overrides": len(current_overrides),
            "restart_required": restart_needed,
            "runtime_applied": runtime_applied,
        }

    @staticmethod
    def reset_system_config(
        db: Session,
        user_id: Optional[int] = None,
    ) -> bool:
        """Remove todos os overrides, voltando aos valores padrao"""
        return SettingsService.delete_setting(db, SYSTEM_CONFIG_KEY, user_id=user_id)

    @staticmethod
    def get_effective_value(db: Session, key: str) -> Any:
        """
        Retorna o valor efetivo de uma configuracao.
        Prioridade: DB override > config.py (env + default)
        """
        overrides = SettingsService.get_system_config_overrides(db)
        if key in overrides:
            return overrides[key]
        return SettingsService._get_config_value(key)
