"""
Factory para criacao do VectorStore baseado na configuracao

Seleciona dinamicamente o provedor conforme VECTOR_DB_PROVIDER:
- pgvector: PostgreSQL com extensao pgvector (padrao)
- supabase: Supabase com pgvector gerenciado
- qdrant: Servidor Qdrant dedicado
"""
import logging
from typing import Optional

from app.vectorstore.base import VectorStore
from app.core.config import settings, VectorDBProvider

logger = logging.getLogger(__name__)

# Cache global do vector store
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """
    Retorna a instancia do VectorStore configurado

    Singleton: cria uma unica instancia e reutiliza.
    O provedor e definido pela variavel VECTOR_DB_PROVIDER.

    Returns:
        VectorStore configurado

    Raises:
        ValueError: Se o provedor nao for suportado
        RuntimeError: Se dependencias do provedor nao estiverem instaladas
    """
    global _vector_store

    if _vector_store is not None:
        return _vector_store

    provider = settings.vector_db_provider

    logger.info(f"Initializing vector store: {provider.value}")

    if provider == VectorDBProvider.PGVECTOR:
        from app.vectorstore.pgvector_store import PgVectorStore
        _vector_store = PgVectorStore()

    elif provider == VectorDBProvider.SUPABASE:
        from app.vectorstore.supabase_store import SupabaseVectorStore
        _vector_store = SupabaseVectorStore()

    elif provider == VectorDBProvider.QDRANT:
        from app.vectorstore.qdrant_store import QdrantVectorStore
        _vector_store = QdrantVectorStore()

    else:
        raise ValueError(
            f"Provedor de vector store nao suportado: {provider}. "
            f"Opcoes: {', '.join(p.value for p in VectorDBProvider)}"
        )

    logger.info(f"Vector store initialized: {provider.value}")
    return _vector_store


def reset_vector_store() -> None:
    """
    Reseta o cache do vector store.
    Usado quando as configuracoes mudam em runtime.
    """
    global _vector_store
    _vector_store = None
    logger.info("Vector store cache reset")


async def initialize_vector_store() -> None:
    """
    Inicializa o vector store (criar indices, colecoes, etc.)
    Chamado no startup da aplicacao.
    """
    store = get_vector_store()
    await store.initialize()
    logger.info("Vector store initialization complete")
