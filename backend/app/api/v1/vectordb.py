"""
API de configuracao e gerenciamento do banco de dados vetorial

Permite:
- Visualizar configuracao atual
- Habilitar/desabilitar provedores (pgvector, supabase, qdrant)
- Testar conexao individual por provedor
- Obter estatisticas
- Health check multi-provedor
"""
import asyncio
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
    primary_provider: str
    enabled_providers: List[str]
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
    """Saude de todos os vector stores habilitados"""
    status: str
    primary: str
    providers: Dict[str, Any] = {}


class VectorDBInfoResponse(BaseModel):
    """Informacoes detalhadas do vector store"""
    provider: str
    info: Dict[str, Any] = {}


class VectorDBCountResponse(BaseModel):
    """Contagem de vetores"""
    provider: str
    total: int
    filters_applied: Optional[Dict[str, Any]] = None


class VectorDBTestConnectionResponse(BaseModel):
    """Resultado de teste de conexao individual"""
    provider: str
    status: str
    details: Dict[str, Any] = {}


# ============================================
# Endpoints
# ============================================

@router.get("/config", response_model=VectorDBConfigResponse)
def get_vectordb_config(
    current_user: User = Depends(require_permission("settings.read"))
):
    """
    Retorna a configuracao completa do banco de dados vetorial

    Inclui provedores habilitados, provedor primario, configuracoes de
    embedding, busca, indexacao HNSW e pesos da busca hibrida.

    **Requer permissao:** settings.read
    """
    enabled = settings.enabled_vector_providers

    # Config especifica de cada provedor habilitado (sem expor secrets)
    provider_config: Dict[str, Any] = {}

    if "pgvector" in enabled:
        pgvector_cfg: Dict[str, Any] = {}
        pgvector_url = settings.effective_pgvector_url
        if "@" in pgvector_url:
            parts = pgvector_url.split("@")
            pgvector_cfg["database_host"] = parts[-1] if len(parts) > 1 else "configured"
        else:
            pgvector_cfg["database_host"] = "configured"
        pgvector_cfg["distance_ops"] = settings.pgvector_distance_ops
        pgvector_cfg["distance_operator"] = settings.pgvector_distance_operator
        provider_config["pgvector"] = pgvector_cfg

    if "supabase" in enabled:
        provider_config["supabase"] = {
            "url": settings.supabase_url or "not configured",
            "key_configured": bool(settings.supabase_key),
            "table_name": settings.supabase_table_name,
            "function_name": settings.supabase_function_name,
        }

    if "qdrant" in enabled:
        provider_config["qdrant"] = {
            "url": settings.qdrant_url or "not configured",
            "api_key_configured": bool(settings.qdrant_api_key),
            "collection_name": settings.qdrant_collection_name,
            "grpc_port": settings.qdrant_grpc_port,
            "prefer_grpc": settings.qdrant_prefer_grpc,
        }

    return VectorDBConfigResponse(
        primary_provider=settings.vector_db_primary,
        enabled_providers=enabled,
        available_providers=[p.value for p in VectorDBProvider],
        embedding_model=settings.embedding_model if settings.embedding_mode.value == "api" else settings.embedding_local_model,
        embedding_dimensions=settings.active_embedding_dimensions,
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
    Verifica a saude de TODOS os bancos vetoriais habilitados

    Testa conexao com cada provedor habilitado e retorna status individual.

    **Requer permissao:** settings.read
    """
    from app.vectorstore.factory import get_all_enabled_stores

    stores = get_all_enabled_stores()
    providers_health: Dict[str, Any] = {}
    overall_status = "ok"

    for name, store in stores.items():
        try:
            health = await asyncio.wait_for(store.health_check(), timeout=10)
            providers_health[name] = {
                "status": health.get("status", "unknown"),
                "primary": name == settings.vector_db_primary,
                "details": health,
            }
        except asyncio.TimeoutError:
            providers_health[name] = {
                "status": "timeout",
                "primary": name == settings.vector_db_primary,
                "details": {"error": "Timeout ao verificar saude (10s)"},
            }
            overall_status = "degraded"
        except Exception as e:
            providers_health[name] = {
                "status": "error",
                "primary": name == settings.vector_db_primary,
                "details": {"error": str(e)},
            }
            overall_status = "degraded"

    return VectorDBHealthResponse(
        status=overall_status,
        primary=settings.vector_db_primary,
        providers=providers_health,
    )


@router.post("/test-connection/{provider_name}", response_model=VectorDBTestConnectionResponse)
async def test_provider_connection(
    provider_name: str,
    current_user: User = Depends(require_permission("settings.read"))
):
    """
    Testa conexao com um provedor especifico sem afetar os stores ativos.

    Cria uma instancia temporaria, executa health_check() e descarta.
    Util para verificar configuracao antes de habilitar um provedor.

    **Requer permissao:** settings.read
    """
    valid_providers = [p.value for p in VectorDBProvider]
    if provider_name not in valid_providers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provedor invalido: '{provider_name}'. Opcoes: {', '.join(valid_providers)}",
        )

    try:
        from app.vectorstore.factory import create_temporary_store

        temp_store = create_temporary_store(provider_name)
        health = await asyncio.wait_for(temp_store.health_check(), timeout=10)

        return VectorDBTestConnectionResponse(
            provider=provider_name,
            status=health.get("status", "unknown"),
            details=health,
        )
    except asyncio.TimeoutError:
        return VectorDBTestConnectionResponse(
            provider=provider_name,
            status="timeout",
            details={"error": "Timeout ao testar conexao (10s)"},
        )
    except Exception as e:
        return VectorDBTestConnectionResponse(
            provider=provider_name,
            status="error",
            details={"error": str(e)},
        )


@router.get("/info", response_model=VectorDBInfoResponse)
async def get_vectordb_info(
    current_user: User = Depends(require_permission("settings.read"))
):
    """
    Retorna informacoes detalhadas do vector store primario

    Inclui dimensoes, metrica, contagem de vetores e configuracoes
    do provedor.

    **Requer permissao:** settings.read
    """
    try:
        from app.vectorstore import get_vector_store

        store = get_vector_store()
        info = await store.get_info()

        return VectorDBInfoResponse(
            provider=settings.vector_db_primary,
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
    Conta vetores armazenados no provedor primario, opcionalmente filtrados

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
            provider=settings.vector_db_primary,
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
    Inicializa (ou reinicializa) todos os vector stores habilitados

    Cria colecoes, tabelas e indices necessarios para cada provedor
    habilitado. Seguro para executar multiplas vezes.

    **Requer permissao:** settings.create
    """
    try:
        from app.vectorstore.factory import initialize_vector_store, reset_vector_store

        # Reset para forcar re-criacao
        reset_vector_store()
        await initialize_vector_store()

        return {
            "status": "initialized",
            "primary_provider": settings.vector_db_primary,
            "enabled_providers": settings.enabled_vector_providers,
            "message": f"Vector stores inicializados: {', '.join(settings.enabled_vector_providers)}",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao inicializar vector stores: {str(e)}",
        )


@router.get("/providers")
def list_providers(
    current_user: User = Depends(require_permission("settings.read"))
):
    """
    Lista todos os provedores de vector DB e suas configuracoes

    Mostra quais provedores estao habilitados, qual e o primario,
    e quais estao configurados.

    **Requer permissao:** settings.read
    """
    enabled_list = settings.enabled_vector_providers
    providers = []

    for provider in VectorDBProvider:
        info: Dict[str, Any] = {
            "name": provider.value,
            "enabled": provider.value in enabled_list,
            "primary": provider.value == settings.vector_db_primary,
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
        "primary_provider": settings.vector_db_primary,
        "enabled_providers": enabled_list,
        "providers": providers,
    }
