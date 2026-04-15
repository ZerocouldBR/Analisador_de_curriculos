"""
Implementacao do VectorStore para Supabase

Usa o Supabase como backend vetorial via pgvector gerenciado.
Requer:
- Projeto Supabase com extensao pgvector habilitada
- Tabela de embeddings criada
- Funcao RPC para busca vetorial

Para gerar o SQL de setup atualizado com as dimensoes corretas:
    python -m app.db.init_db --supabase-sql

O SQL gerado leva em conta:
- Dimensoes do embedding (1536 para API/OpenAI, 384 para local/sentence-transformers)
- Nome da tabela e funcao configurados
- Metrica de distancia configurada
- Parametros HNSW configurados
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
    - Tabela e funcao RPC criados via SQL Editor

    Para gerar o SQL de setup:
        python -m app.db.init_db --supabase-sql
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
        """Verifica conexao com Supabase e valida configuracao"""
        client = self._get_client()
        table = settings.supabase_table_name

        # Verificar se a tabela existe tentando uma query
        try:
            result = client.table(table).select("id", count="exact").limit(0).execute()
            logger.info(
                f"Supabase client initialized: {settings.supabase_url} "
                f"(table={table}, dimensions={settings.active_embedding_dimensions})"
            )
        except Exception as e:
            logger.error(
                f"Supabase table '{table}' not accessible: {e}. "
                f"Execute o SQL de setup: python -m app.db.init_db --supabase-sql"
            )
            raise

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

        if filters.get("document_id"):
            result = client.table(table).select("id").contains(
                "metadata", {"document_id": filters["document_id"]}
            ).execute()

            count = len(result.data or [])
            for row in (result.data or []):
                client.table(table).delete().eq("id", row["id"]).execute()
            return count

        if filters.get("candidate_id"):
            result = client.table(table).select("id").contains(
                "metadata", {"candidate_id": filters["candidate_id"]}
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
                "dimensions": settings.active_embedding_dimensions,
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
            "embedding_mode": settings.embedding_mode.value,
        }
