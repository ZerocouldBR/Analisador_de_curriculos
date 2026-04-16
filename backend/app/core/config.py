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
import secrets
import warnings

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
from enum import Enum

# Chave default para desenvolvimento local - NUNCA usar em producao
_DEV_SECRET_KEY = secrets.token_urlsafe(32)


class VectorDBProvider(str, Enum):
    """Provedores de banco de dados vetorial suportados"""
    PGVECTOR = "pgvector"
    SUPABASE = "supabase"
    QDRANT = "qdrant"


class LLMProvider(str, Enum):
    """Provedores de LLM suportados"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


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
        description="Provedor do banco vetorial: pgvector, supabase, qdrant (legado)"
    )

    # -- Habilitacao individual de provedores --
    pgvector_enabled: bool = Field(default=True, description="Habilitar pgvector como provedor vetorial")
    supabase_enabled: bool = Field(default=False, description="Habilitar Supabase como provedor vetorial")
    qdrant_enabled: bool = Field(default=False, description="Habilitar Qdrant como provedor vetorial")
    vector_db_primary: str = Field(default="pgvector", description="Provedor primario para buscas vetoriais")

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
    # -- Provedor de LLM --
    llm_provider: LLMProvider = Field(
        default=LLMProvider.OPENAI,
        description="Provedor de LLM: openai ou anthropic"
    )

    # -- OpenAI --
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: Optional[str] = Field(
        default=None,
        description="URL base da API OpenAI (para proxies ou alternativas compativeis)"
    )
    openai_organization: Optional[str] = Field(default=None, description="Organization ID da OpenAI")

    # -- Anthropic --
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_base_url: Optional[str] = Field(
        default=None,
        description="URL base da API Anthropic (para proxies)"
    )

    # -- LinkedIn --
    linkedin_api_enabled: bool = Field(default=False, description="Habilitar integracao LinkedIn API")
    linkedin_api_provider: str = Field(
        default="none",
        description="Provider da API LinkedIn: none, proxycurl, rapidapi, official"
    )
    linkedin_client_id: Optional[str] = Field(default=None, description="LinkedIn OAuth Client ID")
    linkedin_client_secret: Optional[str] = Field(default=None, description="LinkedIn OAuth Client Secret")
    linkedin_redirect_uri: Optional[str] = Field(default=None, description="LinkedIn OAuth Redirect URI")
    proxycurl_api_key: Optional[str] = Field(default=None, description="Chave da API Proxycurl para enriquecimento LinkedIn")

    # ================================================================
    # LLM e Chat
    # ================================================================
    chat_model: str = Field(default="gpt-4o", description="Modelo do chat LLM")
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
    # Prompts do Sistema (editaveis via DB/API)
    # ================================================================
    prompt_llm_general: str = Field(
        default="""Voce e um assistente especializado em analise de curriculos para RH.

Suas responsabilidades:
1. Analisar curriculos e responder perguntas sobre candidatos
2. Identificar habilidades, experiencias e qualificacoes relevantes
3. Comparar candidatos quando solicitado
4. Fornecer respostas objetivas e baseadas nos dados disponiveis

Diretrizes:
- Baseie suas respostas APENAS no contexto fornecido
- Se a informacao nao estiver disponivel, informe claramente
- Use os indices de palavras-chave para localizar informacoes rapidamente
- Estruture respostas longas com topicos ou listas
- Cite a fonte (nome do candidato, secao) quando relevante""",
        description="Prompt do LLM para consultas gerais"
    )

    prompt_llm_production: str = Field(
        default="""Voce e um assistente especializado em recrutamento para PRODUCAO INDUSTRIAL.

Voce ajuda empresas a encontrar candidatos para vagas de producao, manufatura e chao de fabrica.

AREAS DE EXPERTISE:
- Operadores de producao (linhas de montagem, maquinas, CNC)
- Lideres e supervisores de producao
- PCP (Planejamento e Controle de Producao)
- Manutencao industrial (mecanica, eletrica, preventiva, corretiva)
- Seguranca do trabalho (NRs, CIPA, EPI)
- Qualidade industrial (ISO, CEP, FMEA, 5S, Lean)
- Sistemas ERP (SAP, TOTVS/Protheus)

CRITERIOS IMPORTANTES PARA AVALIAR CANDIDATOS DE PRODUCAO:
1. Experiencia pratica em chao de fabrica
2. NRs obrigatorias para a funcao (NR-12, NR-10, NR-11, NR-33, NR-35)
3. Certificacoes de seguranca (CIPA, Brigadista, Primeiros Socorros)
4. Habilitacoes (CNH, MOPP, Empilhadeira)
5. Conhecimento em Lean Manufacturing (5S, Kaizen, TPM)
6. Experiencia com equipamentos e maquinas especificas
7. Disponibilidade de turnos (1o, 2o, 3o turno, escalas)
8. Sistemas ERP utilizados (SAP PP/MM, TOTVS)

Diretrizes:
- Baseie suas respostas APENAS no contexto fornecido
- Destaque NRs e certificacoes de seguranca relevantes
- Mencione experiencia com maquinas e equipamentos
- Indique disponibilidade de turno quando relevante
- Classifique candidatos por aderencia ao perfil industrial
- Use linguagem tecnica de producao quando apropriado""",
        description="Prompt do LLM para consultas de producao industrial"
    )

    prompt_llm_logistics: str = Field(
        default="""Voce e um assistente especializado em recrutamento para LOGISTICA e SUPPLY CHAIN.

Voce ajuda empresas a encontrar candidatos para vagas de logistica, armazem e cadeia de suprimentos.

AREAS DE EXPERTISE:
- Operacoes de armazem (recebimento, expedicao, picking, packing)
- Controle de estoque e inventario
- Operacao de empilhadeira e equipamentos de movimentacao
- Supply chain e gestao de suprimentos
- Transporte e distribuicao (roteirizacao, frotas)
- WMS e sistemas logisticos
- Comercio exterior (importacao, exportacao)

CRITERIOS IMPORTANTES PARA AVALIAR CANDIDATOS DE LOGISTICA:
1. Experiencia em operacoes logisticas (armazem, CD, almoxarifado)
2. Habilitacao para empilhadeira e NR-11
3. CNH (categoria relevante para a funcao)
4. Conhecimento em WMS e sistemas de gestao de estoque
5. Experiencia com ERP (SAP WM/MM, TOTVS)
6. Metodologias (FIFO, FEFO, Just-in-Time, Kanban)
7. Gestao de KPIs logisticos (OTIF, acuracidade, lead time)
8. Disponibilidade para turnos e escalas

Diretrizes:
- Baseie suas respostas APENAS no contexto fornecido
- Destaque habilitacoes e NRs de logistica
- Mencione experiencia com sistemas WMS/ERP
- Indique CNH e certificacoes de empilhadeira
- Avalie conhecimento de metodologias logisticas
- Use linguagem tecnica de logistica quando apropriado""",
        description="Prompt do LLM para consultas de logistica"
    )

    prompt_llm_quality: str = Field(
        default="""Voce e um assistente especializado em recrutamento para QUALIDADE INDUSTRIAL.

Voce ajuda empresas a encontrar candidatos para vagas de qualidade, metrologia e melhoria continua.

AREAS DE EXPERTISE:
- Controle de qualidade e inspecao
- Metrologia e instrumentos de medicao
- Normas ISO (9001, 14001, 45001, IATF 16949)
- Ferramentas da qualidade (FMEA, APQP, PPAP, 8D, MASP)
- CEP e controle estatistico de processo
- Lean Six Sigma (Green Belt, Black Belt)
- Auditoria interna e externa

CRITERIOS IMPORTANTES:
1. Experiencia com sistemas de gestao da qualidade
2. Conhecimento de normas ISO e IATF
3. Dominio de ferramentas da qualidade
4. Experiencia com metrologia e instrumentos
5. Certificacoes (auditor, Green Belt, Black Belt)
6. CEP e analise estatistica
7. Experiencia no setor industrial relevante

Diretrizes:
- Baseie suas respostas APENAS no contexto fornecido
- Destaque certificacoes ISO e ferramentas da qualidade
- Mencione experiencia com metrologia
- Avalie certificacoes Lean/Six Sigma
- Use linguagem tecnica de qualidade quando apropriado""",
        description="Prompt do LLM para consultas de qualidade industrial"
    )

    prompt_chat_default: str = Field(
        default="""Voce e um assistente de RH especializado em analise de curriculos e recrutamento.

Seu papel e ajudar recrutadores a:
1. Encontrar os melhores candidatos para vagas abertas
2. Analisar curriculos em detalhe
3. Comparar candidatos entre si
4. Identificar gaps e pontos fortes
5. Sugerir perguntas para entrevistas

REGRAS IMPORTANTES:
- Base suas respostas APENAS nos dados de curriculos fornecidos no contexto
- Nunca invente informacoes sobre candidatos
- Quando nao tiver dados suficientes, informe claramente
- Sempre cite o nome do candidato ao referenciar informacoes
- Use linguagem profissional e objetiva
- Estruture respostas longas com topicos ou tabelas
- Ao comparar candidatos, use criterios objetivos
- Considere tanto hard skills quanto soft skills
- Avalie certificacoes e habilitacoes relevantes para a vaga

FORMATO DE RESPOSTA:
- Para rankings: use tabela com nome, score, pontos fortes e gaps
- Para analises: use topicos claros com icones ou bullets
- Para comparacoes: use formato lado a lado
- Sempre termine com sugestoes de proximos passos quando relevante""",
        description="Prompt principal do chat de RH"
    )

    prompt_chat_job_analysis: str = Field(
        default="""Voce e um especialista em matching de candidatos com vagas.

Voce recebera a descricao de uma vaga e dados de curriculos. Sua tarefa e:

1. ANALISAR a vaga e identificar requisitos obrigatorios e desejaveis
2. AVALIAR cada candidato contra os requisitos
3. RANQUEAR candidatos por aderencia (0-100%)
4. DETALHAR pontos fortes e gaps de cada candidato
5. RECOMENDAR os melhores candidatos com justificativa

Para cada candidato, avalie:
- Experiencia relevante (anos, nivel, setor)
- Hard skills tecnicas
- Certificacoes e habilitacoes
- Formacao academica
- Disponibilidade (turno, viagem, mudanca)
- Soft skills identificaveis
- Fit cultural e senioridade

REGRAS:
- Base suas avaliacoes APENAS nos dados fornecidos
- Seja objetivo e justo na avaliacao
- Destaque riscos e pontos de atencao
- Sugira perguntas para entrevista focadas nos gaps identificados""",
        description="Prompt para analise de vagas vs candidatos"
    )

    # Keywords de dominio para deteccao automatica
    domain_keywords_production: List[str] = Field(
        default=[
            "producao", "produção", "operador", "fabrica", "fábrica",
            "montagem", "maquina", "máquina", "cnc", "torno", "solda",
            "manutencao", "manutenção", "industrial", "chao de fabrica",
            "lider de producao", "supervisor", "pcp", "planejamento",
            "turno", "lean", "kaizen", "5s", "tpm"
        ],
        description="Palavras-chave para deteccao de dominio producao"
    )

    domain_keywords_logistics: List[str] = Field(
        default=[
            "logistica", "logística", "armazem", "armazém", "almoxarifado",
            "estoque", "empilhadeira", "expedicao", "expedição", "supply chain",
            "transporte", "distribuicao", "distribuição", "frete", "wms",
            "picking", "packing", "cross docking", "conferente", "separador",
            "inventario", "inventário"
        ],
        description="Palavras-chave para deteccao de dominio logistica"
    )

    domain_keywords_quality: List[str] = Field(
        default=[
            "qualidade", "inspetor", "inspecao", "inspeção", "metrologia",
            "iso", "auditoria", "cep", "fmea", "six sigma", "seis sigma",
            "green belt", "black belt", "nao conformidade", "calibracao",
            "calibração"
        ],
        description="Palavras-chave para deteccao de dominio qualidade"
    )

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
    # Sourcing Hibrido
    # ================================================================
    sourcing_enabled: bool = Field(
        default=False, description="Habilitar modulo de sourcing hibrido"
    )
    sourcing_sync_interval_days: int = Field(
        default=5, description="Intervalo padrao entre sincronizacoes (dias)"
    )
    sourcing_dedup_email_weight: float = Field(
        default=0.4, description="Peso do email na deduplicacao"
    )
    sourcing_dedup_phone_weight: float = Field(
        default=0.2, description="Peso do telefone na deduplicacao"
    )
    sourcing_dedup_name_weight: float = Field(
        default=0.25, description="Peso do nome na deduplicacao"
    )
    sourcing_dedup_linkedin_weight: float = Field(
        default=0.15, description="Peso do LinkedIn URL na deduplicacao"
    )
    sourcing_dedup_threshold: float = Field(
        default=0.7, description="Score minimo para considerar duplicata (0.0-1.0)"
    )
    sourcing_merge_priority_order: List[str] = Field(
        default=["linkedin", "manual", "csv_import", "xlsx_import", "webhook", "external_partner"],
        description="Ordem de prioridade para resolucao de conflitos entre fontes"
    )
    sourcing_max_sync_candidates: int = Field(
        default=500, description="Maximo de candidatos processados por sincronizacao"
    )
    sourcing_snapshot_retention_days: int = Field(
        default=365, description="Retencao de snapshots em dias"
    )
    sourcing_dedup_name_fuzzy_threshold: float = Field(
        default=0.85, description="Threshold minimo de similaridade fuzzy para nomes (0.0-1.0)"
    )
    sourcing_external_request_timeout: int = Field(
        default=30, description="Timeout padrao para requisicoes a APIs externas de sourcing (s)"
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
        default=_DEV_SECRET_KEY,
        description="Chave secreta para JWT. Defina SECRET_KEY em .env para producao."
    )
    algorithm: str = Field(default="HS256", description="Algoritmo de assinatura JWT")
    access_token_expire_minutes: int = Field(default=15, description="TTL do access token (minutos)")
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
    # Esquema (Schema) do Banco de Dados
    # ================================================================
    database_schema: str = Field(
        default="public",
        description=(
            "Schema do PostgreSQL onde as tabelas serao criadas. "
            "Use 'public' (padrao) ou um schema customizado (ex: 'analisador'). "
            "O schema sera criado automaticamente pelo init_db se nao existir."
        )
    )

    # ================================================================
    # Upload / Storage
    # ================================================================
    max_upload_size_mb: int = Field(default=20, description="Tamanho maximo de upload (MB)")
    supported_upload_extensions: List[str] = Field(
        default=[".pdf", ".docx", ".doc", ".txt", ".rtf", ".odt", ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"],
        description="Extensoes de arquivo permitidas para upload de curriculos"
    )
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
    def active_llm_api_key(self) -> Optional[str]:
        """Retorna a API key do provedor de LLM ativo"""
        if self.llm_provider == LLMProvider.ANTHROPIC:
            return self.anthropic_api_key
        return self.openai_api_key

    @property
    def database_schema_sql(self) -> str:
        """Retorna o schema como prefixo SQL (ex: 'analisador.' ou '' para public)"""
        if self.database_schema and self.database_schema != "public":
            return f"{self.database_schema}."
        return ""

    @property
    def enabled_vector_providers(self) -> list[str]:
        """Retorna lista dos provedores vetoriais habilitados"""
        providers = []
        if self.pgvector_enabled:
            providers.append("pgvector")
        if self.supabase_enabled:
            providers.append("supabase")
        if self.qdrant_enabled:
            providers.append("qdrant")
        # Fallback legado: se nenhum habilitado, usa vector_db_provider
        return providers or [self.vector_db_provider.value]

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

if settings.secret_key == _DEV_SECRET_KEY:
    warnings.warn(
        "\n⚠️  SECRET_KEY nao definida! Usando chave temporaria (tokens JWT invalidados a cada restart)."
        "\n   Para producao, defina SECRET_KEY no arquivo .env:"
        "\n   python -c \"import secrets; print(secrets.token_urlsafe(32))\"",
        stacklevel=1,
    )
