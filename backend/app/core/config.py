"""
Configuracao centralizada do sistema

TODAS as configuracoes do sistema estao aqui. Nenhum valor deve ser
hardcoded nos servicos, modelos ou tasks.

Configuravel via:
- Variaveis de ambiente
- Arquivo .env
- Settings API (server_settings no banco)

Categorias:
- Aplicacao geral
- Banco de dados relacional
- Banco de dados vetorial (pgvector, Supabase, Qdrant)
- APIs externas (OpenAI, LinkedIn)
- LLM e Chat
- Busca vetorial e hibrida
- Chunking e indexacao
- Seguranca e criptografia
- Celery e filas
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
from enum import Enum


class VectorDBProvider(str, Enum):
    """Provedores de banco de dados vetorial suportados"""
    PGVECTOR = "pgvector"
    SUPABASE = "supabase"
    QDRANT = "qdrant"


class EmbeddingProvider(str, Enum):
    """Provedores de embeddings suportados"""
    OPENAI = "openai"
    # Extensivel para: huggingface, cohere, local, etc.


class EmbeddingMode(str, Enum):
    """Modo de vetorizacao"""
    API = "api"        # Vetorizacao via API externa (OpenAI, etc.)
    CODE = "code"      # Vetorizacao local via sentence-transformers


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        case_sensitive=False,
    )

    # ================================================================
    # Aplicacao Geral
    # ================================================================
    app_name: str = Field(default="Analisador de Curriculos")
    app_version: str = Field(default="0.3.0")
    log_level: str = Field(default="INFO")
    debug: bool = Field(default=False, description="Modo debug")

    # ================================================================
    # Banco de Dados Relacional (PostgreSQL)
    # ================================================================
    database_url: str = Field(
        default="postgresql+psycopg://analisador:analisador@localhost:5432/analisador_curriculos",
        description="URL de conexao com o banco relacional principal"
    )
    database_pool_size: int = Field(default=10, description="Tamanho do pool de conexoes")
    database_max_overflow: int = Field(default=20, description="Conexoes extras alem do pool")
    database_pool_timeout: int = Field(default=30, description="Timeout para obter conexao do pool (s)")

    # ================================================================
    # Banco de Dados Vetorial
    # ================================================================
    vector_db_provider: VectorDBProvider = Field(
        default=VectorDBProvider.PGVECTOR,
        description="Provedor do banco vetorial: pgvector, supabase, qdrant"
    )

    # -- pgvector (usa o mesmo PostgreSQL do database_url por padrao) --
    pgvector_database_url: Optional[str] = Field(
        default=None,
        description="URL do PostgreSQL com pgvector. Se None, usa database_url"
    )
    pgvector_hnsw_m: int = Field(default=16, description="HNSW: conexoes por no")
    pgvector_hnsw_ef_construction: int = Field(default=64, description="HNSW: qualidade da construcao")
    pgvector_hnsw_ef_search: int = Field(default=100, description="HNSW: qualidade da busca")
    pgvector_distance_metric: str = Field(
        default="cosine",
        description="Metrica de distancia: cosine, l2, inner_product"
    )

    # -- Supabase --
    supabase_url: Optional[str] = Field(default=None, description="URL do projeto Supabase")
    supabase_key: Optional[str] = Field(default=None, description="Supabase anon/service key")
    supabase_table_name: str = Field(default="embeddings", description="Nome da tabela de embeddings no Supabase")
    supabase_function_name: str = Field(
        default="match_embeddings",
        description="Nome da funcao RPC para busca vetorial no Supabase"
    )

    # -- Qdrant --
    qdrant_url: Optional[str] = Field(default=None, description="URL do servidor Qdrant")
    qdrant_api_key: Optional[str] = Field(default=None, description="API key do Qdrant (se cloud)")
    qdrant_collection_name: str = Field(default="curriculos", description="Nome da colecao no Qdrant")
    qdrant_grpc_port: int = Field(default=6334, description="Porta gRPC do Qdrant")
    qdrant_prefer_grpc: bool = Field(default=True, description="Preferir gRPC ao invés de REST")

    # ================================================================
    # Configuracoes de Embeddings
    # ================================================================
    embedding_mode: EmbeddingMode = Field(
        default=EmbeddingMode.API,
        description="Modo de vetorizacao: api (OpenAI etc.) ou code (local sentence-transformers)"
    )
    embedding_provider: EmbeddingProvider = Field(
        default=EmbeddingProvider.OPENAI,
        description="Provedor de embeddings (modo API)"
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="Modelo de embeddings (API ou local)"
    )
    embedding_local_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Modelo sentence-transformers para vetorizacao local (modo code)"
    )
    embedding_local_device: str = Field(
        default="cpu",
        description="Device para modelo local: cpu, cuda, mps"
    )
    embedding_dimensions: int = Field(
        default=1536,
        description="Dimensoes do vetor de embedding (depende do modelo)"
    )
    embedding_local_dimensions: int = Field(
        default=384,
        description="Dimensoes do vetor para modelo local (all-MiniLM-L6-v2 = 384)"
    )
    embedding_batch_size: int = Field(
        default=20,
        description="Tamanho do lote para geracao de embeddings"
    )
    embedding_max_chars: int = Field(
        default=32000,
        description="Maximo de caracteres por texto para embedding"
    )

    @property
    def active_embedding_dimensions(self) -> int:
        """Retorna dimensoes do embedding ativo baseado no modo"""
        if self.embedding_mode == EmbeddingMode.CODE:
            return self.embedding_local_dimensions
        return self.embedding_dimensions

    # ================================================================
    # APIs Externas
    # ================================================================
    # -- OpenAI --
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: Optional[str] = Field(
        default=None,
        description="URL base da API OpenAI (para proxies ou alternativas compativeis)"
    )
    openai_organization: Optional[str] = Field(default=None, description="Organization ID da OpenAI")

    # -- LinkedIn --
    linkedin_api_enabled: bool = Field(default=False, description="Habilitar integracao LinkedIn API")
    linkedin_client_id: Optional[str] = Field(default=None, description="LinkedIn OAuth Client ID")
    linkedin_client_secret: Optional[str] = Field(default=None, description="LinkedIn OAuth Client Secret")
    linkedin_redirect_uri: Optional[str] = Field(default=None, description="LinkedIn OAuth Redirect URI")

    # ================================================================
    # LLM e Chat
    # ================================================================
    chat_model: str = Field(default="gpt-4-turbo-preview", description="Modelo do chat LLM")
    llm_max_retries: int = Field(default=5, description="Maximo de tentativas para consultas LLM")
    llm_max_tokens: int = Field(default=4096, description="Maximo de tokens na resposta LLM")
    llm_temperature: float = Field(default=0.7, description="Temperatura do LLM (0.0-2.0)")
    llm_min_temperature: float = Field(default=0.3, description="Temperatura minima em retries")
    llm_temperature_decay: float = Field(default=0.1, description="Reducao de temperatura por retry")
    llm_token_decay: int = Field(default=500, description="Reducao de tokens por retry")
    llm_min_tokens: int = Field(default=1000, description="Minimo de tokens por resposta")

    # Limites de caracteres por tentativa (lista JSON via env)
    llm_character_limits: List[int] = Field(
        default=[32000, 24000, 16000, 10000, 6000],
        description="Limites de caracteres por tentativa de retry"
    )
    llm_chunks_per_retry: List[int] = Field(
        default=[15, 12, 8, 5, 3],
        description="Numero de chunks por tentativa de retry"
    )

    # Chat conversacional
    chat_max_messages_per_conversation: int = Field(default=200, description="Max mensagens por conversa")
    chat_max_context_messages: int = Field(default=10, description="Mensagens anteriores no contexto")
    chat_max_context_chars: int = Field(default=24000, description="Max caracteres no contexto do chat")
    chat_max_chunks_per_query: int = Field(default=15, description="Max chunks por consulta do chat")
    chat_temperature: float = Field(default=0.5, description="Temperatura do chat")
    chat_max_tokens: int = Field(default=4096, description="Max tokens na resposta do chat")

    # ================================================================
    # Busca Vetorial e Hibrida
    # ================================================================
    vector_search_threshold: float = Field(default=0.3, description="Similaridade minima para busca vetorial")
    vector_search_limit: int = Field(default=50, description="Max chunks na busca vetorial")
    vector_search_pre_filter_threshold: float = Field(
        default=0.2,
        description="Threshold minimo antes de filtrar (pre-filtro)"
    )

    # Pesos da busca hibrida
    hybrid_vector_weight: float = Field(default=0.4, description="Peso da busca vetorial (0-1)")
    hybrid_text_weight: float = Field(default=0.3, description="Peso da busca full-text (0-1)")
    hybrid_filter_weight: float = Field(default=0.2, description="Peso dos filtros (0-1)")
    hybrid_domain_weight: float = Field(default=0.1, description="Peso do dominio (0-1)")

    # Pesos do LLM query scoring
    llm_semantic_weight: float = Field(default=0.6, description="Peso do score semantico no ranking")
    llm_keyword_weight: float = Field(default=0.4, description="Peso de keywords no ranking")

    # Confidence scoring
    confidence_score_weight: float = Field(default=0.7, description="Peso do score medio na confianca")
    confidence_coverage_weight: float = Field(default=0.3, description="Peso da cobertura na confianca")
    confidence_coverage_divisor: int = Field(default=5, description="Divisor para normalizacao de cobertura (min chunks para 100%)")

    # ================================================================
    # Job Matching
    # ================================================================
    job_matching_strength_threshold: float = Field(
        default=70.0, description="Score minimo para considerar requisito como ponto forte"
    )
    job_matching_gap_threshold: float = Field(
        default=30.0, description="Score abaixo do qual requisito e considerado gap"
    )
    job_matching_cnh_bonus: float = Field(
        default=5.0, description="Bonus de score para candidato com CNH requerida"
    )
    job_matching_experience_bonus: float = Field(
        default=3.0, description="Bonus de score para candidato com experiencia suficiente"
    )
    job_matching_keyword_repeat_threshold: int = Field(
        default=2, description="Repeticoes de keyword para ganhar bonus"
    )
    job_matching_keyword_bonus: float = Field(
        default=5.0, description="Bonus por keyword repetida acima do threshold"
    )
    job_matching_direct_text_weight: float = Field(
        default=0.6, description="Peso do match direto no texto"
    )
    job_matching_indexed_weight: float = Field(
        default=0.4, description="Peso do match no indice de keywords"
    )
    job_matching_suggestion_threshold: float = Field(
        default=20.0, description="Score minimo para sugerir vaga a candidato"
    )

    # ================================================================
    # LLM Internals
    # ================================================================
    llm_section_max_chunks: int = Field(
        default=3, description="Max chunks por secao em uma tentativa de query"
    )
    llm_character_limit_fallback: int = Field(
        default=6000, description="Fallback de limite de caracteres quando fora do range de retries"
    )
    llm_chunks_per_retry_fallback: int = Field(
        default=3, description="Fallback de chunks quando fora do range de retries"
    )
    llm_domain_score_multiplier: float = Field(
        default=0.5, description="Multiplicador do score de dominio na busca hibrida"
    )

    # ================================================================
    # Keyword Extraction
    # ================================================================
    keyword_idf_default: float = Field(
        default=2.5, description="IDF padrao para termos gerais"
    )
    keyword_idf_domain: float = Field(
        default=3.0, description="IDF para termos de dominio (producao, logistica, qualidade)"
    )
    keyword_idf_long_word_multiplier: float = Field(
        default=1.2, description="Multiplicador IDF para palavras longas (>8 chars)"
    )

    # ================================================================
    # LinkedIn
    # ================================================================
    linkedin_enrichment_score_weight: float = Field(
        default=0.3, description="Peso do score LinkedIn ao enriquecer resultados"
    )
    linkedin_request_timeout: float = Field(
        default=30.0, description="Timeout para requisicoes ao LinkedIn (segundos)"
    )
    linkedin_search_results_limit: int = Field(
        default=50, description="Max resultados por busca no LinkedIn"
    )
    linkedin_internal_search_limit: int = Field(
        default=200, description="Max candidatos internos a considerar em busca LinkedIn"
    )

    # ================================================================
    # OCR Avancado
    # ================================================================
    ocr_good_confidence_threshold: float = Field(
        default=70.0, description="Confianca a partir da qual OCR para de tentar outras resolucoes"
    )

    # ================================================================
    # API Defaults (valores padrao para paginacao e truncamento)
    # ================================================================
    search_result_highlight_chars: int = Field(
        default=200, description="Max chars no highlight de resultado de busca"
    )
    keyword_max_results: int = Field(
        default=50, description="Max keywords/ngrams retornados"
    )

    # ================================================================
    # Chunking e Indexacao
    # ================================================================
    chunk_size: int = Field(default=1500, description="Tamanho maximo de cada chunk (chars)")
    chunk_overlap: int = Field(default=200, description="Sobreposicao entre chunks (chars)")
    chunk_min_size: int = Field(default=100, description="Tamanho minimo para gerar embedding")
    chunk_max_content_size: int = Field(default=10000, description="Tamanho max do conteudo por chunk no DB")

    enable_keyword_extraction: bool = Field(default=True, description="Habilitar extracao de keywords")
    enable_hnsw_index: bool = Field(default=True, description="Habilitar indice HNSW")

    # Full-text search
    fts_language: str = Field(default="portuguese", description="Idioma do full-text search")

    # ================================================================
    # Multi-Tenant / Empresas
    # ================================================================
    multi_tenant_enabled: bool = Field(
        default=True,
        description="Habilitar multi-tenant (cada empresa ve apenas seus curriculos)"
    )
    default_company_name: str = Field(
        default="Empresa Padrao",
        description="Nome da empresa padrao para novos usuarios"
    )

    # ================================================================
    # Branding / Logo
    # ================================================================
    company_logo_max_size_kb: int = Field(
        default=500,
        description="Tamanho maximo do logo da empresa (KB)"
    )
    company_logo_allowed_formats: List[str] = Field(
        default=["png", "jpg", "jpeg", "svg", "webp"],
        description="Formatos de imagem permitidos para logo"
    )
    company_logo_path: str = Field(
        default="./uploads/logos",
        description="Diretorio para armazenamento dos logos"
    )

    # ================================================================
    # Precificacao e Uso de IA
    # ================================================================
    ai_pricing_enabled: bool = Field(
        default=True,
        description="Habilitar calculo de custo de uso da IA"
    )

    # Precos por 1000 tokens (USD) - configuraveis via env
    ai_price_embedding_input: float = Field(
        default=0.00002,
        description="Preco por 1K tokens de input para embeddings (USD)"
    )
    ai_price_llm_input: float = Field(
        default=0.01,
        description="Preco por 1K tokens de input para LLM (USD)"
    )
    ai_price_llm_output: float = Field(
        default=0.03,
        description="Preco por 1K tokens de output para LLM (USD)"
    )
    ai_price_chat_input: float = Field(
        default=0.01,
        description="Preco por 1K tokens de input para chat (USD)"
    )
    ai_price_chat_output: float = Field(
        default=0.03,
        description="Preco por 1K tokens de output para chat (USD)"
    )
    ai_currency: str = Field(
        default="USD",
        description="Moeda para calculo de custos (USD, BRL, EUR)"
    )
    ai_currency_exchange_rate: float = Field(
        default=1.0,
        description="Taxa de conversao para moeda local (ex: 5.0 para BRL)"
    )

    # Limites de uso por empresa
    ai_monthly_token_limit: int = Field(
        default=0,
        description="Limite mensal de tokens por empresa (0 = ilimitado)"
    )
    ai_monthly_cost_limit: float = Field(
        default=0.0,
        description="Limite mensal de custo por empresa em moeda configurada (0 = ilimitado)"
    )

    # ================================================================
    # Seguranca e Autenticacao
    # ================================================================
    secret_key: str = Field(
        ...,
        description="Chave secreta para JWT. OBRIGATORIO via env var SECRET_KEY."
    )
    algorithm: str = Field(default="HS256", description="Algoritmo de assinatura JWT")
    access_token_expire_minutes: int = Field(default=30, description="TTL do access token (minutos)")
    refresh_token_expire_days: int = Field(default=7, description="TTL do refresh token (dias)")

    # PII / Criptografia
    enable_pii_encryption: bool = Field(default=True, description="Habilitar criptografia de PII")

    # Rate limiting
    rate_limit_per_minute: int = Field(default=60, description="Limite de requisicoes por minuto por usuario")

    # ================================================================
    # CORS
    # ================================================================
    cors_origins: list[str] = Field(
        default=["http://localhost:3000"],
        description="Origens CORS permitidas"
    )

    # ================================================================
    # Upload / Storage
    # ================================================================
    max_upload_size_mb: int = Field(default=20, description="Tamanho maximo de upload (MB)")
    storage_backend: str = Field(
        default="local",
        description="Backend de armazenamento: local, s3, minio"
    )
    storage_path: str = Field(default="./uploads", description="Caminho para storage local")
    s3_bucket: Optional[str] = Field(default=None, description="Bucket S3/MinIO")
    s3_endpoint: Optional[str] = Field(default=None, description="Endpoint S3/MinIO")
    s3_access_key: Optional[str] = Field(default=None, description="S3 Access Key")
    s3_secret_key: Optional[str] = Field(default=None, description="S3 Secret Key")

    # ================================================================
    # Redis / Celery
    # ================================================================
    redis_url: str = Field(default="redis://localhost:6379/0", description="URL do Redis")
    celery_result_expires: int = Field(default=3600, description="TTL dos resultados Celery (s)")
    celery_task_time_limit: int = Field(default=300, description="Limite de tempo por task (s)")
    celery_task_soft_time_limit: int = Field(default=240, description="Soft limit por task (s)")
    celery_worker_concurrency: int = Field(default=4, description="Workers concorrentes do Celery")

    # ================================================================
    # OCR
    # ================================================================
    ocr_languages: str = Field(default="por+eng", description="Idiomas do Tesseract OCR")
    ocr_min_confidence: float = Field(default=30.0, description="Confianca minima aceitavel do OCR (%)")
    ocr_resolutions: List[int] = Field(
        default=[300, 400, 200],
        description="Resolucoes DPI para tentativa adaptativa de OCR"
    )
    ocr_min_text_chars: int = Field(default=30, description="Min chars para considerar pagina com texto")
    ocr_psm_modes: List[int] = Field(
        default=[6, 3, 4, 1],
        description="PSM modes para tentativa progressiva (6=bloco, 3=auto, 4=coluna, 1=OSD)"
    )
    ocr_max_images_per_docx: int = Field(
        default=10,
        description="Max imagens embutidas para OCR em DOCX"
    )

    # ================================================================
    # Helpers
    # ================================================================

    @property
    def effective_pgvector_url(self) -> str:
        """Retorna a URL efetiva do pgvector (prioriza pgvector_database_url)"""
        return self.pgvector_database_url or self.database_url

    @property
    def pgvector_distance_ops(self) -> str:
        """Retorna o operador de distancia do pgvector baseado na metrica"""
        ops = {
            "cosine": "vector_cosine_ops",
            "l2": "vector_l2_ops",
            "inner_product": "vector_ip_ops",
        }
        return ops.get(self.pgvector_distance_metric, "vector_cosine_ops")

    @property
    def pgvector_distance_operator(self) -> str:
        """Retorna o operador SQL de distancia do pgvector"""
        operators = {
            "cosine": "<=>",
            "l2": "<->",
            "inner_product": "<#>",
        }
        return operators.get(self.pgvector_distance_metric, "<=>")

    def get_similarity_expression(self, vector_column: str, query_param: str) -> str:
        """Retorna a expressao SQL de similaridade baseada na metrica"""
        op = self.pgvector_distance_operator
        if self.pgvector_distance_metric == "cosine":
            return f"1 - ({vector_column} {op} {query_param}::vector)"
        elif self.pgvector_distance_metric == "inner_product":
            return f"({vector_column} {op} {query_param}::vector) * -1"
        else:  # l2
            return f"1.0 / (1.0 + ({vector_column} {op} {query_param}::vector))"


settings = Settings()
