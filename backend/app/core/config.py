from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_version: str = Field(default="0.1.0")
    log_level: str = Field(default="INFO")

    database_url: str = Field(
        default="postgresql+psycopg://analisador:analisador@localhost:5432/analisador_curriculos"
    )
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Security Configuration
    secret_key: str = Field(
        ...,
        description="Secret key for JWT signing. MUST be set via SECRET_KEY env var."
    )
    algorithm: str = Field(default="HS256", description="JWT signing algorithm")
    access_token_expire_minutes: int = Field(default=30, description="Access token TTL in minutes")
    refresh_token_expire_days: int = Field(default=7, description="Refresh token TTL in days")

    # CORS Configuration
    cors_origins: list[str] = Field(
        default=["http://localhost:3000"],
        description="Allowed CORS origins"
    )

    # Upload Configuration
    max_upload_size_mb: int = Field(default=20, description="Max file upload size in MB")

    # OpenAI Configuration
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    embedding_model: str = Field(default="text-embedding-3-small")
    chat_model: str = Field(default="gpt-4-turbo-preview")

    # LLM Query Configuration
    llm_max_retries: int = Field(default=5, description="Max retries for LLM queries")
    llm_max_tokens: int = Field(default=4096, description="Max tokens for LLM response")
    llm_temperature: float = Field(default=0.7, description="LLM temperature")

    # Vector Search Configuration
    vector_search_threshold: float = Field(default=0.3, description="Min similarity threshold")
    vector_search_limit: int = Field(default=50, description="Max chunks to retrieve")

    # Indexing Configuration
    enable_keyword_extraction: bool = Field(default=True, description="Enable keyword extraction")
    enable_hnsw_index: bool = Field(default=True, description="Enable HNSW vector index")

    # PII Encryption
    enable_pii_encryption: bool = Field(default=True, description="Enable PII field-level encryption")

    # Rate Limiting
    rate_limit_per_minute: int = Field(default=60, description="API rate limit per minute per user")

    # Chat Configuration
    chat_max_messages_per_conversation: int = Field(default=200, description="Max messages per conversation")
    chat_max_context_tokens: int = Field(default=8000, description="Max tokens for chat context")


settings = Settings()
