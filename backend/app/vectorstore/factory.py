"""
Factory para criacao do VectorStore baseado na configuracao

Suporta multiplos provedores simultaneamente:
- pgvector: PostgreSQL com extensao pgvector (padrao)
- supabase: Supabase com pgvector gerenciado
- qdrant: Servidor Qdrant dedicado

Escritas sao enviadas a todos os provedores habilitados (fan-out).
Buscas usam o provedor primario (vector_db_primary).
"""
import logging
from typing import Optional, Dict

from app.vectorstore.base import VectorStore
from app.core.config import settings

logger = logging.getLogger(__name__)

# Registry global de vector stores habilitados
_vector_stores: Dict[str, VectorStore] = {}


def _create_store(provider_name: str) -> VectorStore:
    """
    Cria uma instancia do VectorStore para o provedor especificado.

    Args:
        provider_name: Nome do provedor (pgvector, supabase, qdrant)

    Returns:
        Instancia do VectorStore

    Raises:
        ValueError: Se o provedor nao for suportado
        RuntimeError: Se dependencias do provedor nao estiverem instaladas
    """
    if provider_name == "pgvector":
        from app.vectorstore.pgvector_store import PgVectorStore
        return PgVectorStore()
    elif provider_name == "supabase":
        from app.vectorstore.supabase_store import SupabaseVectorStore
        return SupabaseVectorStore()
    elif provider_name == "qdrant":
        from app.vectorstore.qdrant_store import QdrantVectorStore
        return QdrantVectorStore()
    else:
        raise ValueError(
            f"Provedor de vector store nao suportado: {provider_name}. "
            f"Opcoes: pgvector, supabase, qdrant"
        )


def _ensure_stores_initialized() -> None:
    """Inicializa lazily todos os stores habilitados que ainda nao estao no registry"""
    global _vector_stores
    for provider_name in settings.enabled_vector_providers:
        if provider_name not in _vector_stores:
            try:
                store = _create_store(provider_name)
                _vector_stores[provider_name] = store
                logger.info(f"Vector store initialized: {provider_name}")
            except Exception as e:
                logger.error(f"Falha ao inicializar vector store '{provider_name}': {e}")


def get_vector_store() -> VectorStore:
    """
    Retorna a instancia do VectorStore primario (backward-compatible).

    Singleton: cria uma unica instancia e reutiliza.

    Returns:
        VectorStore primario configurado

    Raises:
        RuntimeError: Se nenhum vector store estiver habilitado
    """
    return get_primary_store()


def get_primary_store() -> VectorStore:
    """
    Retorna o VectorStore primario para operacoes de busca.

    O provedor primario e definido por vector_db_primary.
    Se o primario nao estiver habilitado, usa o primeiro habilitado.

    Returns:
        VectorStore primario

    Raises:
        RuntimeError: Se nenhum vector store estiver habilitado
    """
    _ensure_stores_initialized()

    primary = settings.vector_db_primary
    if primary in _vector_stores:
        return _vector_stores[primary]

    # Fallback: se o primario nao esta habilitado, usar o primeiro disponivel
    if _vector_stores:
        fallback = next(iter(_vector_stores))
        logger.warning(
            f"Provedor primario '{primary}' nao habilitado. "
            f"Usando fallback: '{fallback}'"
        )
        return _vector_stores[fallback]

    raise RuntimeError(
        "Nenhum vector store habilitado. "
        "Habilite pelo menos um provedor nas configuracoes."
    )


def get_all_enabled_stores() -> Dict[str, VectorStore]:
    """
    Retorna todos os VectorStores habilitados.

    Usado para fan-out de escritas (gravar em todos os stores).

    Returns:
        Dict mapeando nome do provedor para instancia do VectorStore
    """
    _ensure_stores_initialized()
    return dict(_vector_stores)


def create_temporary_store(provider_name: str) -> VectorStore:
    """
    Cria uma instancia temporaria do VectorStore para teste de conexao.

    NAO e adicionada ao registry global. Use para testar conexao
    sem afetar os stores ativos.

    Args:
        provider_name: Nome do provedor a testar

    Returns:
        Instancia temporaria do VectorStore
    """
    return _create_store(provider_name)


def reset_vector_store() -> None:
    """
    Reseta o registry de vector stores.
    Usado quando as configuracoes mudam em runtime.
    """
    global _vector_stores
    _vector_stores.clear()
    logger.info("Vector store registry reset")


async def initialize_vector_store() -> None:
    """
    Inicializa todos os vector stores habilitados
    (criar indices, colecoes, etc.)

    Chamado no startup da aplicacao. Se um store falhar,
    loga o erro mas continua com os demais.
    """
    _ensure_stores_initialized()
    for name, store in _vector_stores.items():
        try:
            await store.initialize()
            logger.info(f"Vector store '{name}' initialization complete")
        except Exception as e:
            logger.error(f"Falha ao inicializar vector store '{name}': {e}")
