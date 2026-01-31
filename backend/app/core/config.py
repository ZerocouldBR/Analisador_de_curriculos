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


settings = Settings()
