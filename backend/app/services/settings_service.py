from sqlalchemy.orm import Session
from typing import Optional, Any
from app.db.models import ServerSettings, AuditLog
from app.schemas.settings import SettingCreate, SettingUpdate


class SettingsService:
    @staticmethod
    def get_setting(db: Session, key: str) -> Optional[ServerSettings]:
        """Obtém uma configuração por chave"""
        return db.query(ServerSettings).filter(ServerSettings.key == key).first()

    @staticmethod
    def get_all_settings(db: Session, skip: int = 0, limit: int = 100) -> list[ServerSettings]:
        """Lista todas as configurações"""
        return db.query(ServerSettings).offset(skip).limit(limit).all()

    @staticmethod
    def create_setting(
        db: Session,
        setting: SettingCreate,
        user_id: Optional[int] = None
    ) -> ServerSettings:
        """Cria uma nova configuração"""
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
        """Atualiza uma configuração existente"""
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
        """Remove uma configuração"""
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
        """Obtém ou cria a configuração de prompts do chat LLM"""
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
