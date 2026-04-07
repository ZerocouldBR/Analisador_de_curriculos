"""
Implementacao do VectorStore para Supabase

Usa o Supabase como backend vetorial via pgvector gerenciado.
Requer:
- Projeto Supabase com extensao pgvector habilitada
- Tabela de embeddings criada
- Funcao RPC para busca vetorial

Setup no Supabase (SQL Editor):

-- Habilitar pgvector
create extension if not exists vector;

-- Criar tabela de embeddings
create table if not exists embeddings (
    id bigserial primary key,
    chunk_id text not null,
    content text,
    metadata jsonb,
    vector vector(1536),  -- ajustar dimensao conforme modelo
    created_at timestamptz default now()
);

-- Criar indice HNSW
create index on embeddings using hnsw (vector vector_cosine_ops);

-- Criar funcao de busca
create or replace function match_embeddings(
    query_embedding vector(1536),
    match_threshold float default 0.3,
    match_count int default 10,
    filter_metadata jsonb default '{}'
)
returns table (
    id bigint,
    chunk_id text,
    content text,
    metadata jsonb,
    similarity float
)
language plpgsql
as $$
begin
    return query
    select
        e.id,
        e.chunk_id,
        e.content,
        e.metadata,
        1 - (e.vector <=> query_embedding) as similarity
    from embeddings e
    where 1 - (e.vector <=> query_embedding) >= match_threshold
      and (filter_metadata = '{}' or e.metadata @> filter_metadata)
    order by e.vector <=> query_embedding
    limit match_count;
end;
$$;
"""
import json
import logging
from typing import List, Optional, Dict, Any

from app.vectorstore.base import VectorStore, VectorSearchResult
from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False


class SupabaseVectorStore(VectorStore):
    """
    VectorStore usando Supabase (PostgreSQL gerenciado + pgvector)

    Requer:
    - pip install supabase
    - Variaveis: SUPABASE_URL, SUPABASE_KEY
    """

    def __init__(self):
        self._client: Optional[Any] = None

    def _get_client(self) -> Any:
        if not SUPABASE_AVAILABLE:
            raise RuntimeError(
                "supabase nao disponivel. Execute: pip install supabase"
            )

        if self._client is None:
            if not settings.supabase_url or not settings.supabase_key:
                raise ValueError(
                    "SUPABASE_URL e SUPABASE_KEY devem estar configurados"
                )
            self._client = create_client(
                settings.supabase_url,
                settings.supabase_key
            )
        return self._client

    async def initialize(self) -> None:
        """Verifica conexao com Supabase"""
        client = self._get_client()
        logger.info(f"Supabase client initialized: {settings.supabase_url}")

    async def upsert(
        self,
        id: str,
        vector: List[float],
        metadata: Optional[Dict[str, Any]] = None,
        content: Optional[str] = None,
    ) -> None:
        """Insere ou atualiza embedding no Supabase"""
        client = self._get_client()
        table = settings.supabase_table_name

        data = {
            "chunk_id": id,
            "vector": vector,
            "metadata": metadata or {},
            "content": content or "",
        }

        # Verificar se existe
        existing = client.table(table).select("id").eq("chunk_id", id).execute()

        if existing.data:
            client.table(table).update(data).eq("chunk_id", id).execute()
        else:
            client.table(table).insert(data).execute()

    async def upsert_batch(
        self,
        ids: List[str],
        vectors: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        contents: Optional[List[str]] = None,
    ) -> None:
        """Insere em lote no Supabase"""
        client = self._get_client()
        table = settings.supabase_table_name

        rows = []
        for i, (id_val, vector) in enumerate(zip(ids, vectors)):
            rows.append({
                "chunk_id": id_val,
                "vector": vector,
                "metadata": metadatas[i] if metadatas else {},
                "content": contents[i] if contents else "",
            })

        # Supabase suporta upsert em batch
        if rows:
            client.table(table).upsert(rows, on_conflict="chunk_id").execute()

    async def search(
        self,
        query_vector: List[float],
        limit: int = 10,
        threshold: float = 0.0,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """Busca vetorial via funcao RPC do Supabase"""
        client = self._get_client()

        filter_metadata = {}
        if filters:
            filter_metadata = {k: v for k, v in filters.items() if v is not None}

        result = client.rpc(
            settings.supabase_function_name,
            {
                "query_embedding": query_vector,
                "match_threshold": threshold,
                "match_count": limit,
                "filter_metadata": json.dumps(filter_metadata),
            }
        ).execute()

        results = []
        for row in (result.data or []):
            results.append(VectorSearchResult(
                id=str(row.get("chunk_id", row.get("id", ""))),
                score=float(row.get("similarity", 0)),
                metadata=row.get("metadata", {}),
                content=row.get("content"),
            ))

        return results

    async def delete(self, id: str) -> None:
        """Remove embedding do Supabase"""
        client = self._get_client()
        client.table(settings.supabase_table_name).delete().eq("chunk_id", id).execute()

    async def delete_by_filter(self, filters: Dict[str, Any]) -> int:
        """Remove embeddings por filtro de metadados"""
        client = self._get_client()
        table = settings.supabase_table_name

        # Supabase nao suporta filtro JSONB diretamente via client, usar abordagem simples
        if filters.get("document_id"):
            result = client.table(table).select("id").contains(
                "metadata", {"document_id": filters["document_id"]}
            ).execute()

            count = len(result.data or [])
            for row in (result.data or []):
                client.table(table).delete().eq("id", row["id"]).execute()
            return count

        return 0

    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Conta embeddings no Supabase"""
        client = self._get_client()
        result = client.table(settings.supabase_table_name).select(
            "id", count="exact"
        ).execute()
        return result.count or 0

    async def health_check(self) -> Dict[str, Any]:
        """Verifica saude do Supabase"""
        try:
            client = self._get_client()
            result = client.table(settings.supabase_table_name).select(
                "id", count="exact"
            ).limit(1).execute()

            return {
                "status": "healthy",
                "provider": "supabase",
                "url": settings.supabase_url,
                "table": settings.supabase_table_name,
                "embeddings_count": result.count or 0,
                "dimensions": settings.embedding_dimensions,
            }
        except Exception as e:
            return {"status": "unhealthy", "provider": "supabase", "error": str(e)}

    async def get_info(self) -> Dict[str, Any]:
        """Retorna info do Supabase store"""
        health = await self.health_check()
        return {
            **health,
            "function_name": settings.supabase_function_name,
            "sdk_available": SUPABASE_AVAILABLE,
        }
