"""
API de configuracao e gerenciamento do banco de dados vetorial

Permite:
- Visualizar configuracao atual
- Trocar provedor (pgvector, supabase, qdrant)
- Testar conexao
- Obter estatisticas
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from app.core.config import settings, VectorDBProvider
from app.core.dependencies import require_permission
from app.db.models import User

router = APIRouter(prefix="/vectordb", tags=["vector-database"])


# ============================================
# Schemas
# ============================================

class VectorDBConfigResponse(BaseModel):
    """Configuracao atual do vector DB"""
    provider: str
    available_providers: List[str]

    # Embeddings
    embedding_model: str
    embedding_dimensions: int
    embedding_batch_size: int
    embedding_max_chars: int

    # Provider-specific
    provider_config: Dict[str, Any]

    # Search
    search_threshold: float
    search_limit: int

    # HNSW
    hnsw_enabled: bool
    hnsw_m: int
    hnsw_ef_construction: int
    hnsw_ef_search: int
    distance_metric: str

    # Chunking
    chunk_size: int
    chunk_overlap: int
    chunk_min_size: int

    # Hybrid search weights
    hybrid_weights: Dict[str, float]


class VectorDBHealthResponse(BaseModel):
    """Saude do vector store"""
    status: str
    provider: str
    details: Dict[str, Any] = {}


class VectorDBInfoResponse(BaseModel):
    """Informacoes detalhadas do vector store"""
    provider: str
    info: Dict[str, Any] = {}


class VectorDBCountResponse(BaseModel):
    """Contagem de vetores"""
    provider: str
    total: int
    filters_applied: Optional[Dict[str, Any]] = None


# ============================================
# Endpoints
# ============================================

@router.get("/config", response_model=VectorDBConfigResponse)
def get_vectordb_config(
    current_user: User = Depends(require_permission("settings.read"))
):
    """
    Retorna a configuracao completa do banco de dados vetorial

    Inclui provedor atual, configuracoes de embedding, busca,
    indexacao HNSW e pesos da busca hibrida.

    **Requer permissao:** settings.read
    """
    provider = settings.vector_db_provider

    # Config especifica do provedor (sem expor secrets)
    provider_config: Dict[str, Any] = {}

    if provider == VectorDBProvider.PGVECTOR:
        pgvector_url = settings.effective_pgvector_url
        # Mascara a senha na URL
        if "@" in pgvector_url:
            parts = pgvector_url.split("@")
            provider_config["database_host"] = parts[-1] if len(parts) > 1 else "configured"
        else:
            provider_config["database_host"] = "configured"
        provider_config["distance_ops"] = settings.pgvector_distance_ops
        provider_config["distance_operator"] = settings.pgvector_distance_operator

    elif provider == VectorDBProvider.SUPABASE:
        provider_config["url"] = settings.supabase_url or "not configured"
        provider_config["key_configured"] = bool(settings.supabase_key)
        provider_config["table_name"] = settings.supabase_table_name
        provider_config["function_name"] = settings.supabase_function_name

    elif provider == VectorDBProvider.QDRANT:
        provider_config["url"] = settings.qdrant_url or "not configured"
        provider_config["api_key_configured"] = bool(settings.qdrant_api_key)
        provider_config["collection_name"] = settings.qdrant_collection_name
        provider_config["grpc_port"] = settings.qdrant_grpc_port
        provider_config["prefer_grpc"] = settings.qdrant_prefer_grpc

    return VectorDBConfigResponse(
        provider=provider.value,
        available_providers=[p.value for p in VectorDBProvider],
        embedding_model=settings.embedding_model,
        embedding_dimensions=settings.embedding_dimensions,
        embedding_batch_size=settings.embedding_batch_size,
        embedding_max_chars=settings.embedding_max_chars,
        provider_config=provider_config,
        search_threshold=settings.vector_search_threshold,
        search_limit=settings.vector_search_limit,
        hnsw_enabled=settings.enable_hnsw_index,
        hnsw_m=settings.pgvector_hnsw_m,
        hnsw_ef_construction=settings.pgvector_hnsw_ef_construction,
        hnsw_ef_search=settings.pgvector_hnsw_ef_search,
        distance_metric=settings.pgvector_distance_metric,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        chunk_min_size=settings.chunk_min_size,
        hybrid_weights={
            "vector": settings.hybrid_vector_weight,
            "text": settings.hybrid_text_weight,
            "filter": settings.hybrid_filter_weight,
            "domain": settings.hybrid_domain_weight,
        },
    )


@router.get("/health", response_model=VectorDBHealthResponse)
async def check_vectordb_health(
    current_user: User = Depends(require_permission("settings.read"))
):
    """
    Verifica a saude e conectividade do banco de dados vetorial

    Testa a conexao com o provedor configurado e retorna status.

    **Requer permissao:** settings.read
    """
    try:
        from app.vectorstore import get_vector_store

        store = get_vector_store()
        health = await store.health_check()

        return VectorDBHealthResponse(
            status=health.get("status", "unknown"),
            provider=settings.vector_db_provider.value,
            details=health,
        )
    except Exception as e:
        return VectorDBHealthResponse(
            status="error",
            provider=settings.vector_db_provider.value,
            details={"error": str(e)},
        )


@router.get("/info", response_model=VectorDBInfoResponse)
async def get_vectordb_info(
    current_user: User = Depends(require_permission("settings.read"))
):
    """
    Retorna informacoes detalhadas do vector store

    Inclui dimensoes, metrica, contagem de vetores e configuracoes
    do provedor.

    **Requer permissao:** settings.read
    """
    try:
        from app.vectorstore import get_vector_store

        store = get_vector_store()
        info = await store.get_info()

        return VectorDBInfoResponse(
            provider=settings.vector_db_provider.value,
            info=info,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao obter informacoes do vector store: {str(e)}",
        )


@router.get("/count", response_model=VectorDBCountResponse)
async def get_vectordb_count(
    candidate_id: Optional[int] = None,
    document_id: Optional[int] = None,
    section: Optional[str] = None,
    current_user: User = Depends(require_permission("settings.read")),
):
    """
    Conta vetores armazenados, opcionalmente filtrados

    **Filtros opcionais:**
    - candidate_id: Filtrar por candidato
    - document_id: Filtrar por documento
    - section: Filtrar por secao (experiencia, formacao, skills, etc.)

    **Requer permissao:** settings.read
    """
    try:
        from app.vectorstore import get_vector_store

        store = get_vector_store()

        filters: Optional[Dict[str, Any]] = None
        if any([candidate_id, document_id, section]):
            filters = {}
            if candidate_id:
                filters["candidate_id"] = candidate_id
            if document_id:
                filters["document_id"] = document_id
            if section:
                filters["section"] = section

        total = await store.count(filters=filters)

        return VectorDBCountResponse(
            provider=settings.vector_db_provider.value,
            total=total,
            filters_applied=filters,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao contar vetores: {str(e)}",
        )


@router.post("/initialize")
async def initialize_vectordb(
    current_user: User = Depends(require_permission("settings.create"))
):
    """
    Inicializa (ou reinicializa) o vector store

    Cria colecoes, tabelas e indices necessarios para o provedor
    configurado. Seguro para executar multiplas vezes.

    **Requer permissao:** settings.create
    """
    try:
        from app.vectorstore.factory import initialize_vector_store, reset_vector_store

        # Reset para forcar re-criacao
        reset_vector_store()
        await initialize_vector_store()

        return {
            "status": "initialized",
            "provider": settings.vector_db_provider.value,
            "message": f"Vector store '{settings.vector_db_provider.value}' inicializado com sucesso",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao inicializar vector store: {str(e)}",
        )


@router.get("/providers")
def list_providers(
    current_user: User = Depends(require_permission("settings.read"))
):
    """
    Lista todos os provedores de vector DB disponiveis e suas configuracoes

    Mostra quais provedores estao configurados e prontos para uso.

    **Requer permissao:** settings.read
    """
    providers = []

    for provider in VectorDBProvider:
        info: Dict[str, Any] = {
            "name": provider.value,
            "active": provider == settings.vector_db_provider,
            "configured": False,
            "description": "",
            "required_env_vars": [],
        }

        if provider == VectorDBProvider.PGVECTOR:
            info["configured"] = bool(settings.database_url)
            info["description"] = "PostgreSQL com extensao pgvector (padrao, usa o mesmo banco relacional)"
            info["required_env_vars"] = ["DATABASE_URL (obrigatorio)", "PGVECTOR_DATABASE_URL (opcional, se separado)"]

        elif provider == VectorDBProvider.SUPABASE:
            info["configured"] = bool(settings.supabase_url and settings.supabase_key)
            info["description"] = "Supabase com pgvector gerenciado (cloud)"
            info["required_env_vars"] = ["SUPABASE_URL", "SUPABASE_KEY"]

        elif provider == VectorDBProvider.QDRANT:
            info["configured"] = bool(settings.qdrant_url)
            info["description"] = "Qdrant - banco vetorial dedicado (self-hosted ou cloud)"
            info["required_env_vars"] = ["QDRANT_URL", "QDRANT_API_KEY (se cloud)"]

        providers.append(info)

    return {
        "current_provider": settings.vector_db_provider.value,
        "providers": providers,
        "how_to_switch": "Defina a variavel de ambiente VECTOR_DB_PROVIDER com o nome do provedor desejado e reinicie a aplicacao.",
    }
