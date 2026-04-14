"""
Manifesto de configuracao do sistema.

Define TODAS as configuracoes editaveis via frontend, organizadas por categoria.
Cada campo possui: key, label, tipo, descricao, se requer restart, e valor padrao.

O frontend renderiza formularios dinamicamente a partir deste manifesto.
"""

from typing import Any

# Tipos de campo suportados no frontend
FIELD_TYPES = {
    "text": "Campo de texto simples",
    "number": "Campo numerico (int ou float)",
    "boolean": "Toggle on/off",
    "select": "Dropdown de opcoes",
    "password": "Campo mascarado (senhas/chaves)",
    "textarea": "Area de texto grande",
    "list_int": "Lista de inteiros separados por virgula",
    "list_str": "Lista de strings separados por virgula",
}


def _field(
    key: str,
    label: str,
    field_type: str = "text",
    description: str = "",
    restart_required: bool = False,
    sensitive: bool = False,
    options: list | None = None,
    min_value: float | None = None,
    max_value: float | None = None,
    step: float | None = None,
    placeholder: str = "",
) -> dict[str, Any]:
    """Cria definicao de um campo de configuracao"""
    field = {
        "key": key,
        "label": label,
        "type": field_type,
        "description": description,
        "restart_required": restart_required,
        "sensitive": sensitive,
    }
    if options is not None:
        field["options"] = options
    if min_value is not None:
        field["min_value"] = min_value
    if max_value is not None:
        field["max_value"] = max_value
    if step is not None:
        field["step"] = step
    if placeholder:
        field["placeholder"] = placeholder
    return field


CONFIG_MANIFEST: list[dict[str, Any]] = [
    # ================================================================
    # Geral
    # ================================================================
    {
        "category": "general",
        "label": "Geral",
        "icon": "Settings",
        "description": "Configuracoes gerais da aplicacao",
        "fields": [
            _field("app_name", "Nome da Aplicacao", "text",
                   "Nome exibido no sistema"),
            _field("log_level", "Nivel de Log", "select",
                   "Nivel de detalhamento dos logs do sistema",
                   restart_required=True,
                   options=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
            _field("debug", "Modo Debug", "boolean",
                   "Ativa modo de depuracao (NUNCA em producao)",
                   restart_required=True),
            _field("multi_tenant_enabled", "Multi-Tenant", "boolean",
                   "Cada empresa ve apenas seus proprios curriculos"),
            _field("default_company_name", "Nome da Empresa Padrao", "text",
                   "Nome da empresa padrao para novos usuarios"),
        ],
    },

    # ================================================================
    # Banco de Dados
    # ================================================================
    {
        "category": "database",
        "label": "Banco de Dados",
        "icon": "Storage",
        "description": "Configuracoes do PostgreSQL e pool de conexoes",
        "fields": [
            _field("database_url", "URL de Conexao", "password",
                   "URL de conexao com o PostgreSQL (requer restart)",
                   restart_required=True, sensitive=True,
                   placeholder="postgresql+psycopg://user:pass@host:5432/dbname"),
            _field("database_pool_size", "Tamanho do Pool", "number",
                   "Numero de conexoes permanentes no pool",
                   restart_required=True, min_value=1, max_value=100, step=1),
            _field("database_max_overflow", "Overflow Maximo", "number",
                   "Conexoes extras alem do pool",
                   restart_required=True, min_value=0, max_value=200, step=1),
            _field("database_pool_timeout", "Timeout do Pool (s)", "number",
                   "Timeout em segundos para obter conexao do pool",
                   restart_required=True, min_value=5, max_value=120, step=1),
        ],
    },

    # ================================================================
    # Redis / Celery
    # ================================================================
    {
        "category": "redis_celery",
        "label": "Redis / Celery",
        "icon": "Memory",
        "description": "Cache, filas de processamento e workers",
        "fields": [
            _field("redis_url", "URL do Redis", "password",
                   "URL de conexao com o Redis",
                   restart_required=True, sensitive=True,
                   placeholder="redis://:senha@host:6379/0"),
            _field("celery_worker_concurrency", "Workers Concorrentes", "number",
                   "Numero de workers Celery rodando em paralelo",
                   restart_required=True, min_value=1, max_value=16, step=1),
            _field("celery_task_time_limit", "Timeout por Task (s)", "number",
                   "Tempo maximo de execucao por task",
                   min_value=30, max_value=3600, step=10),
            _field("celery_task_soft_time_limit", "Soft Timeout (s)", "number",
                   "Aviso antes do timeout (deve ser menor que o timeout)",
                   min_value=30, max_value=3600, step=10),
            _field("celery_result_expires", "Expiracao de Resultados (s)", "number",
                   "Tempo ate expirar resultados de tasks completadas",
                   min_value=60, max_value=86400, step=60),
        ],
    },

    # ================================================================
    # IA & Embeddings
    # ================================================================
    {
        "category": "embeddings",
        "label": "IA & Embeddings",
        "icon": "Psychology",
        "description": "Vetorizacao de curriculos: modo API (OpenAI) ou local (sentence-transformers)",
        "fields": [
            _field("embedding_mode", "Modo de Vetorizacao", "select",
                   "api = OpenAI (pago, melhor qualidade) | code = local (gratis, mais lento)",
                   restart_required=True,
                   options=["api", "code"]),
            _field("openai_api_key", "OpenAI API Key", "password",
                   "Chave da API OpenAI (necessaria apenas no modo 'api')",
                   sensitive=True, placeholder="sk-..."),
            _field("openai_base_url", "OpenAI Base URL", "text",
                   "URL alternativa para API compativel com OpenAI (deixe vazio para padrao)",
                   placeholder="https://api.openai.com/v1"),
            _field("embedding_model", "Modelo API", "text",
                   "Modelo de embeddings via API (ex: text-embedding-3-small)",
                   placeholder="text-embedding-3-small"),
            _field("embedding_dimensions", "Dimensoes API", "number",
                   "Dimensoes do vetor do modelo API",
                   min_value=128, max_value=4096, step=1),
            _field("embedding_local_model", "Modelo Local", "text",
                   "Modelo sentence-transformers para modo local",
                   placeholder="all-MiniLM-L6-v2"),
            _field("embedding_local_dimensions", "Dimensoes Local", "number",
                   "Dimensoes do vetor do modelo local",
                   min_value=128, max_value=4096, step=1),
            _field("embedding_local_device", "Dispositivo Local", "select",
                   "Hardware para modelo local",
                   options=["cpu", "cuda", "mps"]),
            _field("embedding_batch_size", "Tamanho do Lote", "number",
                   "Quantos textos processar por lote",
                   min_value=1, max_value=100, step=1),
            _field("embedding_max_chars", "Max Caracteres", "number",
                   "Limite de caracteres por texto para embedding",
                   min_value=1000, max_value=100000, step=1000),
        ],
    },

    # ================================================================
    # Vector DB
    # ================================================================
    {
        "category": "vector_db",
        "label": "Banco Vetorial",
        "icon": "Hub",
        "description": "Provedor e parametros do banco de dados vetorial",
        "fields": [
            _field("vector_db_provider", "Provedor", "select",
                   "pgvector (recomendado), Supabase ou Qdrant",
                   restart_required=True,
                   options=["pgvector", "supabase", "qdrant"]),
            # pgvector
            _field("pgvector_database_url", "pgvector URL", "password",
                   "URL separada para pgvector (vazio = usa mesma URL do banco principal)",
                   sensitive=True, placeholder="postgresql+psycopg://..."),
            _field("pgvector_distance_metric", "Metrica de Distancia", "select",
                   "Metrica para calcular similaridade entre vetores",
                   options=["cosine", "l2", "inner_product"]),
            _field("pgvector_hnsw_m", "HNSW M", "number",
                   "Conexoes por no no indice HNSW (mais = melhor recall, mais memoria)",
                   min_value=4, max_value=64, step=2),
            _field("pgvector_hnsw_ef_construction", "HNSW EF Construction", "number",
                   "Qualidade da construcao do indice",
                   min_value=16, max_value=512, step=8),
            _field("pgvector_hnsw_ef_search", "HNSW EF Search", "number",
                   "Qualidade da busca (mais = melhor recall, mais lento)",
                   min_value=16, max_value=512, step=8),
            _field("enable_hnsw_index", "Habilitar Indice HNSW", "boolean",
                   "Usar indice HNSW para acelerar buscas vetoriais"),
            # Supabase
            _field("supabase_url", "Supabase URL", "text",
                   "URL do projeto Supabase", placeholder="https://xxx.supabase.co"),
            _field("supabase_key", "Supabase Key", "password",
                   "Chave de servico do Supabase", sensitive=True),
            _field("supabase_table_name", "Tabela Supabase", "text",
                   "Nome da tabela de embeddings"),
            _field("supabase_function_name", "Funcao RPC Supabase", "text",
                   "Nome da funcao de busca vetorial"),
            # Qdrant
            _field("qdrant_url", "Qdrant URL", "text",
                   "URL do servidor Qdrant", placeholder="http://localhost:6333"),
            _field("qdrant_api_key", "Qdrant API Key", "password",
                   "API Key do Qdrant Cloud", sensitive=True),
            _field("qdrant_collection_name", "Colecao Qdrant", "text",
                   "Nome da colecao no Qdrant"),
            _field("qdrant_grpc_port", "Qdrant gRPC Port", "number",
                   "Porta gRPC do Qdrant", min_value=1, max_value=65535, step=1),
            _field("qdrant_prefer_grpc", "Preferir gRPC", "boolean",
                   "Usar gRPC ao inves de REST para comunicacao com Qdrant"),
        ],
    },

    # ================================================================
    # LLM & Chat
    # ================================================================
    {
        "category": "llm_chat",
        "label": "LLM & Chat",
        "icon": "Chat",
        "description": "Modelo de linguagem e configuracoes do chat",
        "fields": [
            _field("chat_model", "Modelo LLM", "text",
                   "Modelo do chat (ex: gpt-4-turbo-preview, gpt-3.5-turbo)",
                   placeholder="gpt-4-turbo-preview"),
            _field("llm_temperature", "Temperatura", "number",
                   "Criatividade das respostas (0.0 = determinístico, 2.0 = muito criativo)",
                   min_value=0.0, max_value=2.0, step=0.1),
            _field("llm_max_tokens", "Max Tokens Resposta", "number",
                   "Maximo de tokens na resposta do LLM",
                   min_value=100, max_value=16000, step=100),
            _field("llm_max_retries", "Max Retentativas", "number",
                   "Tentativas antes de desistir de uma consulta LLM",
                   min_value=1, max_value=10, step=1),
            _field("llm_min_temperature", "Temperatura Minima (retry)", "number",
                   "Temperatura minima usada durante retentativas",
                   min_value=0.0, max_value=1.0, step=0.1),
            _field("llm_temperature_decay", "Decay de Temperatura", "number",
                   "Quanto reduzir a temperatura a cada retry",
                   min_value=0.0, max_value=0.5, step=0.05),
            _field("chat_max_messages_per_conversation", "Max Mensagens/Conversa", "number",
                   "Limite de mensagens por conversa de chat",
                   min_value=10, max_value=1000, step=10),
            _field("chat_max_context_messages", "Mensagens de Contexto", "number",
                   "Quantas mensagens anteriores enviar como contexto",
                   min_value=1, max_value=50, step=1),
            _field("chat_max_context_chars", "Max Chars Contexto", "number",
                   "Limite de caracteres no contexto do chat",
                   min_value=1000, max_value=100000, step=1000),
            _field("chat_max_chunks_per_query", "Max Chunks/Query", "number",
                   "Maximo de chunks de curriculo por consulta do chat",
                   min_value=1, max_value=50, step=1),
            _field("chat_temperature", "Temperatura do Chat", "number",
                   "Temperatura especifica para o chat conversacional",
                   min_value=0.0, max_value=2.0, step=0.1),
            _field("chat_max_tokens", "Max Tokens Chat", "number",
                   "Maximo de tokens na resposta do chat",
                   min_value=100, max_value=16000, step=100),
        ],
    },

    # ================================================================
    # Busca
    # ================================================================
    {
        "category": "search",
        "label": "Busca & Ranking",
        "icon": "Search",
        "description": "Parametros de busca vetorial, hibrida e ranking de resultados",
        "fields": [
            _field("vector_search_threshold", "Threshold de Similaridade", "number",
                   "Similaridade minima para considerar um resultado (0.0 - 1.0)",
                   min_value=0.0, max_value=1.0, step=0.05),
            _field("vector_search_limit", "Limite de Resultados", "number",
                   "Maximo de chunks retornados pela busca vetorial",
                   min_value=5, max_value=200, step=5),
            _field("hybrid_vector_weight", "Peso Vetorial", "number",
                   "Peso da busca vetorial na busca hibrida (0-1)",
                   min_value=0.0, max_value=1.0, step=0.05),
            _field("hybrid_text_weight", "Peso Full-Text", "number",
                   "Peso da busca full-text na busca hibrida (0-1)",
                   min_value=0.0, max_value=1.0, step=0.05),
            _field("hybrid_filter_weight", "Peso dos Filtros", "number",
                   "Peso dos filtros na busca hibrida (0-1)",
                   min_value=0.0, max_value=1.0, step=0.05),
            _field("hybrid_domain_weight", "Peso do Dominio", "number",
                   "Peso do dominio (area de atuacao) na busca hibrida (0-1)",
                   min_value=0.0, max_value=1.0, step=0.05),
            _field("confidence_score_weight", "Peso Score Confianca", "number",
                   "Peso do score medio no calculo de confianca",
                   min_value=0.0, max_value=1.0, step=0.05),
            _field("confidence_coverage_weight", "Peso Cobertura", "number",
                   "Peso da cobertura no calculo de confianca",
                   min_value=0.0, max_value=1.0, step=0.05),
            _field("fts_language", "Idioma Full-Text", "select",
                   "Idioma do full-text search do PostgreSQL",
                   options=["portuguese", "english", "spanish", "simple"]),
        ],
    },

    # ================================================================
    # Job Matching
    # ================================================================
    {
        "category": "job_matching",
        "label": "Matching de Vagas",
        "icon": "WorkOutline",
        "description": "Parametros de matching entre candidatos e vagas",
        "fields": [
            _field("job_matching_strength_threshold", "Threshold Ponto Forte (%)", "number",
                   "Score minimo para considerar requisito como ponto forte",
                   min_value=0, max_value=100, step=5),
            _field("job_matching_gap_threshold", "Threshold Gap (%)", "number",
                   "Score abaixo do qual requisito e considerado lacuna",
                   min_value=0, max_value=100, step=5),
            _field("job_matching_cnh_bonus", "Bonus CNH", "number",
                   "Bonus de score para candidato com CNH requerida",
                   min_value=0, max_value=20, step=1),
            _field("job_matching_experience_bonus", "Bonus Experiencia", "number",
                   "Bonus de score para experiencia suficiente",
                   min_value=0, max_value=20, step=1),
            _field("job_matching_keyword_bonus", "Bonus Keyword", "number",
                   "Bonus por keyword repetida acima do threshold",
                   min_value=0, max_value=20, step=1),
            _field("job_matching_suggestion_threshold", "Threshold Sugestao (%)", "number",
                   "Score minimo para sugerir vaga a candidato",
                   min_value=0, max_value=100, step=5),
        ],
    },

    # ================================================================
    # OCR
    # ================================================================
    {
        "category": "ocr",
        "label": "OCR",
        "icon": "DocumentScanner",
        "description": "Reconhecimento optico de caracteres para PDFs escaneados",
        "fields": [
            _field("ocr_languages", "Idiomas OCR", "text",
                   "Idiomas do Tesseract separados por + (ex: por+eng)",
                   placeholder="por+eng"),
            _field("ocr_min_confidence", "Confianca Minima (%)", "number",
                   "Confianca minima aceitavel do OCR",
                   min_value=0, max_value=100, step=5),
            _field("ocr_good_confidence_threshold", "Confianca Boa (%)", "number",
                   "Confianca a partir da qual OCR para de tentar outras resolucoes",
                   min_value=0, max_value=100, step=5),
            _field("ocr_resolutions", "Resolucoes DPI", "list_int",
                   "Resolucoes DPI para tentativa adaptativa (ex: 300,400,200)",
                   placeholder="300,400,200"),
            _field("ocr_min_text_chars", "Min Caracteres", "number",
                   "Minimo de caracteres para considerar pagina com texto",
                   min_value=5, max_value=200, step=5),
            _field("ocr_max_images_per_docx", "Max Imagens DOCX", "number",
                   "Maximo de imagens embutidas para OCR em DOCX",
                   min_value=1, max_value=50, step=1),
        ],
    },

    # ================================================================
    # Chunking & Indexacao
    # ================================================================
    {
        "category": "chunking",
        "label": "Chunking & Indexacao",
        "icon": "ViewModule",
        "description": "Como os textos dos curriculos sao divididos e indexados",
        "fields": [
            _field("chunk_size", "Tamanho do Chunk", "number",
                   "Tamanho maximo de cada chunk em caracteres",
                   min_value=100, max_value=10000, step=100),
            _field("chunk_overlap", "Sobreposicao", "number",
                   "Caracteres de sobreposicao entre chunks",
                   min_value=0, max_value=2000, step=50),
            _field("chunk_min_size", "Tamanho Minimo", "number",
                   "Tamanho minimo para gerar embedding de um chunk",
                   min_value=10, max_value=1000, step=10),
            _field("enable_keyword_extraction", "Extracao de Keywords", "boolean",
                   "Habilitar extracao automatica de keywords dos curriculos"),
        ],
    },

    # ================================================================
    # Armazenamento
    # ================================================================
    {
        "category": "storage",
        "label": "Armazenamento",
        "icon": "CloudUpload",
        "description": "Upload de arquivos e backend de armazenamento",
        "fields": [
            _field("max_upload_size_mb", "Tamanho Max Upload (MB)", "number",
                   "Tamanho maximo de arquivo para upload",
                   min_value=1, max_value=100, step=1),
            _field("storage_backend", "Backend", "select",
                   "Onde armazenar os arquivos de curriculos",
                   restart_required=True,
                   options=["local", "s3", "minio"]),
            _field("storage_path", "Caminho Local", "text",
                   "Diretorio para armazenamento local",
                   placeholder="./uploads"),
            _field("s3_bucket", "S3 Bucket", "text",
                   "Nome do bucket S3/MinIO", placeholder="meu-bucket"),
            _field("s3_endpoint", "S3 Endpoint", "text",
                   "Endpoint S3/MinIO", placeholder="https://s3.amazonaws.com"),
            _field("s3_access_key", "S3 Access Key", "password",
                   "Chave de acesso S3/MinIO", sensitive=True),
            _field("s3_secret_key", "S3 Secret Key", "password",
                   "Chave secreta S3/MinIO", sensitive=True),
            _field("company_logo_max_size_kb", "Max Logo (KB)", "number",
                   "Tamanho maximo do logo da empresa em KB",
                   min_value=50, max_value=5000, step=50),
            _field("company_logo_allowed_formats", "Formatos de Logo", "list_str",
                   "Formatos permitidos para logo (ex: png,jpg,jpeg,svg,webp)",
                   placeholder="png,jpg,jpeg,svg,webp"),
        ],
    },

    # ================================================================
    # Seguranca
    # ================================================================
    {
        "category": "security",
        "label": "Seguranca",
        "icon": "Security",
        "description": "Autenticacao JWT, criptografia e controle de acesso",
        "fields": [
            _field("secret_key", "Chave Secreta JWT", "password",
                   "Chave secreta para assinar tokens JWT (NUNCA compartilhe)",
                   restart_required=True, sensitive=True),
            _field("algorithm", "Algoritmo JWT", "select",
                   "Algoritmo de assinatura dos tokens",
                   restart_required=True,
                   options=["HS256", "HS384", "HS512"]),
            _field("access_token_expire_minutes", "Expiracao Access Token (min)", "number",
                   "Tempo de vida do token de acesso em minutos",
                   min_value=5, max_value=1440, step=5),
            _field("refresh_token_expire_days", "Expiracao Refresh Token (dias)", "number",
                   "Tempo de vida do token de refresh em dias",
                   min_value=1, max_value=90, step=1),
            _field("enable_pii_encryption", "Criptografia PII", "boolean",
                   "Criptografar dados pessoais sensiveis (CPF, RG, etc.) - LGPD"),
            _field("rate_limit_per_minute", "Rate Limit (req/min)", "number",
                   "Limite de requisicoes por minuto por usuario",
                   min_value=10, max_value=1000, step=10),
            _field("cors_origins", "Origens CORS", "list_str",
                   "Dominios permitidos para requisicoes CORS (ex: https://meusite.com.br)",
                   restart_required=True,
                   placeholder="https://meusite.com.br"),
        ],
    },

    # ================================================================
    # Precificacao IA
    # ================================================================
    {
        "category": "ai_pricing",
        "label": "Custos de IA",
        "icon": "AttachMoney",
        "description": "Precificacao, moeda e limites de uso de IA",
        "fields": [
            _field("ai_pricing_enabled", "Rastreamento de Custos", "boolean",
                   "Habilitar calculo e registro de custos de IA"),
            _field("ai_currency", "Moeda", "select",
                   "Moeda para exibicao de custos",
                   options=["USD", "BRL", "EUR", "GBP"]),
            _field("ai_currency_exchange_rate", "Taxa de Cambio", "number",
                   "Taxa de conversao USD -> moeda local (ex: 5.0 para BRL)",
                   min_value=0.01, max_value=1000, step=0.01),
            _field("ai_price_embedding_input", "Preco Embedding/1K tokens", "number",
                   "Custo por 1000 tokens de embedding (USD)",
                   min_value=0, max_value=1, step=0.00001),
            _field("ai_price_llm_input", "Preco LLM Input/1K tokens", "number",
                   "Custo por 1000 tokens de input LLM (USD)",
                   min_value=0, max_value=1, step=0.001),
            _field("ai_price_llm_output", "Preco LLM Output/1K tokens", "number",
                   "Custo por 1000 tokens de output LLM (USD)",
                   min_value=0, max_value=1, step=0.001),
            _field("ai_price_chat_input", "Preco Chat Input/1K tokens", "number",
                   "Custo por 1000 tokens de input do chat (USD)",
                   min_value=0, max_value=1, step=0.001),
            _field("ai_price_chat_output", "Preco Chat Output/1K tokens", "number",
                   "Custo por 1000 tokens de output do chat (USD)",
                   min_value=0, max_value=1, step=0.001),
            _field("ai_monthly_token_limit", "Limite Mensal Tokens", "number",
                   "Limite de tokens por empresa/mes (0 = ilimitado)",
                   min_value=0, max_value=100000000, step=10000),
            _field("ai_monthly_cost_limit", "Limite Mensal Custo", "number",
                   "Limite de custo por empresa/mes na moeda configurada (0 = ilimitado)",
                   min_value=0, max_value=100000, step=10),
        ],
    },

    # ================================================================
    # LinkedIn
    # ================================================================
    {
        "category": "linkedin",
        "label": "LinkedIn",
        "icon": "LinkedIn",
        "description": "Integracao com LinkedIn para enriquecimento de perfis",
        "fields": [
            _field("linkedin_api_enabled", "Habilitar LinkedIn", "boolean",
                   "Ativar integracao com a API do LinkedIn"),
            _field("linkedin_client_id", "Client ID", "text",
                   "LinkedIn OAuth Client ID", placeholder="77..."),
            _field("linkedin_client_secret", "Client Secret", "password",
                   "LinkedIn OAuth Client Secret", sensitive=True),
            _field("linkedin_redirect_uri", "Redirect URI", "text",
                   "URL de callback OAuth", placeholder="https://meusite.com/callback"),
            _field("linkedin_request_timeout", "Timeout (s)", "number",
                   "Timeout para requisicoes ao LinkedIn",
                   min_value=5, max_value=120, step=5),
            _field("linkedin_search_results_limit", "Max Resultados", "number",
                   "Limite de resultados por busca",
                   min_value=10, max_value=200, step=10),
        ],
    },

    # ================================================================
    # Prompts do Sistema
    # ================================================================
    {
        "category": "prompts",
        "label": "Prompts do Sistema",
        "icon": "SmartToy",
        "description": "Prompts de sistema para o LLM e Chat - editaveis para customizar comportamento da IA",
        "fields": [
            _field("prompt_llm_general", "Prompt LLM Geral", "textarea",
                   "Prompt do sistema para consultas gerais de RH e analise de curriculos"),
            _field("prompt_llm_production", "Prompt LLM Producao", "textarea",
                   "Prompt especializado para recrutamento de producao industrial"),
            _field("prompt_llm_logistics", "Prompt LLM Logistica", "textarea",
                   "Prompt especializado para recrutamento de logistica e supply chain"),
            _field("prompt_llm_quality", "Prompt LLM Qualidade", "textarea",
                   "Prompt especializado para recrutamento de qualidade industrial"),
            _field("prompt_chat_default", "Prompt Chat Padrao", "textarea",
                   "Prompt principal do chat conversacional de RH"),
            _field("prompt_chat_job_analysis", "Prompt Analise de Vagas", "textarea",
                   "Prompt para matching de candidatos com vagas"),
        ],
    },

    # ================================================================
    # Keywords de Dominio
    # ================================================================
    {
        "category": "domain_keywords",
        "label": "Palavras-chave de Dominio",
        "icon": "Label",
        "description": "Palavras-chave usadas para deteccao automatica de dominio nas consultas",
        "fields": [
            _field("domain_keywords_production", "Keywords Producao", "list_str",
                   "Palavras-chave que ativam o prompt de producao industrial (separadas por virgula)"),
            _field("domain_keywords_logistics", "Keywords Logistica", "list_str",
                   "Palavras-chave que ativam o prompt de logistica (separadas por virgula)"),
            _field("domain_keywords_quality", "Keywords Qualidade", "list_str",
                   "Palavras-chave que ativam o prompt de qualidade industrial (separadas por virgula)"),
        ],
    },
]


def get_all_field_keys() -> list[str]:
    """Retorna lista de todas as chaves de configuracao do manifesto"""
    keys = []
    for category in CONFIG_MANIFEST:
        for field in category["fields"]:
            keys.append(field["key"])
    return keys


def get_field_metadata(key: str) -> dict[str, Any] | None:
    """Retorna metadados de um campo especifico"""
    for category in CONFIG_MANIFEST:
        for field in category["fields"]:
            if field["key"] == key:
                return {**field, "category": category["category"]}
    return None
