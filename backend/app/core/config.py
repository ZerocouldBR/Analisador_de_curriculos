from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_version: str = Field(default="0.1.0")
    log_level: str = Field(default="INFO")


settings = Settings()
