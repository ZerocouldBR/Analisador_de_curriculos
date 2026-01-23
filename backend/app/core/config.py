from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_version: str = Field(default="0.1.0")
    log_level: str = Field(default="INFO")

    database_url: str = Field(
        default="postgresql+psycopg://analisador:analisador@localhost:5432/analisador_curriculos"
    )
    redis_url: str = Field(default="redis://localhost:6379/0")


settings = Settings()
