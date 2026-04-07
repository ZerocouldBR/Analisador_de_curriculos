"""
Modulo de Vector Store

Abstrai o armazenamento e busca vetorial com suporte a multiplos provedores:
- pgvector (PostgreSQL)
- Supabase (PostgreSQL gerenciado com pgvector)
- Qdrant (banco vetorial dedicado)

Uso:
    from app.vectorstore import get_vector_store

    store = get_vector_store()
    await store.upsert(id="chunk_1", vector=[0.1, ...], metadata={...})
    results = await store.search(query_vector=[0.1, ...], limit=10)
"""
from app.vectorstore.base import VectorStore, VectorSearchResult
from app.vectorstore.factory import get_vector_store

__all__ = ["VectorStore", "VectorSearchResult", "get_vector_store"]
