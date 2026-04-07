"""
Implementacao do VectorStore para PostgreSQL com pgvector

Usa o banco PostgreSQL existente com a extensao pgvector.
Compativel com indices HNSW e IVFFlat.
"""
import logging
from typing import List, Optional, Dict, Any

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.vectorstore.base import VectorStore, VectorSearchResult
from app.core.config import settings

logger = logging.getLogger(__name__)


class PgVectorStore(VectorStore):
    """
    VectorStore usando PostgreSQL + pgvector

    Armazena vetores na tabela `embeddings` vinculada a `chunks`.
    """

    def __init__(self):
        self._engine = None
        self._session_factory = None

    def _get_engine(self):
        if self._engine is None:
            from sqlalchemy import create_engine
            self._engine = create_engine(
                settings.effective_pgvector_url,
                pool_size=settings.database_pool_size,
                max_overflow=settings.database_max_overflow,
                pool_timeout=settings.database_pool_timeout,
            )
        return self._engine

    def _get_session(self) -> Session:
        if self._session_factory is None:
            from sqlalchemy.orm import sessionmaker
            self._session_factory = sessionmaker(bind=self._get_engine())
        return self._session_factory()

    async def initialize(self) -> None:
        """Cria extensao pgvector e indices se necessario"""
        engine = self._get_engine()

        with engine.connect() as conn:
            # Criar extensao pgvector
            try:
                conn.execute(sql_text("CREATE EXTENSION IF NOT EXISTS vector;"))
                conn.commit()
                logger.info("pgvector extension verified")
            except Exception as e:
                logger.warning(f"Could not create pgvector extension: {e}")

            # Criar indice HNSW se habilitado
            if settings.enable_hnsw_index:
                try:
                    result = conn.execute(sql_text(
                        "SELECT indexname FROM pg_indexes "
                        "WHERE indexname = 'idx_embeddings_vector_hnsw'"
                    ))
                    if result.fetchone() is None:
                        conn.execute(sql_text(
                            f"CREATE INDEX idx_embeddings_vector_hnsw "
                            f"ON embeddings USING hnsw (vector {settings.pgvector_distance_ops}) "
                            f"WITH (m = {settings.pgvector_hnsw_m}, "
                            f"ef_construction = {settings.pgvector_hnsw_ef_construction});"
                        ))
                        conn.commit()
                        logger.info("HNSW index created")
                except Exception as e:
                    logger.warning(f"Could not create HNSW index: {e}")

            # Criar indice GIN para full-text search
            try:
                result = conn.execute(sql_text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE indexname = 'idx_chunks_content_fts'"
                ))
                if result.fetchone() is None:
                    conn.execute(sql_text(
                        f"CREATE INDEX idx_chunks_content_fts "
                        f"ON chunks USING GIN ("
                        f"to_tsvector('{settings.fts_language}', content));"
                    ))
                    conn.commit()
                    logger.info("FTS index created")
            except Exception as e:
                logger.warning(f"Could not create FTS index: {e}")

            # Indice GIN para meta_json
            try:
                result = conn.execute(sql_text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE indexname = 'idx_chunks_meta_json'"
                ))
                if result.fetchone() is None:
                    conn.execute(sql_text(
                        "CREATE INDEX idx_chunks_meta_json "
                        "ON chunks USING GIN (meta_json jsonb_path_ops);"
                    ))
                    conn.commit()
            except Exception as e:
                logger.debug(f"JSON index: {e}")

    async def upsert(
        self,
        id: str,
        vector: List[float],
        metadata: Optional[Dict[str, Any]] = None,
        content: Optional[str] = None,
    ) -> None:
        """Insere ou atualiza embedding na tabela embeddings"""
        session = self._get_session()
        try:
            chunk_id = int(id)
            model = metadata.get("model", settings.embedding_model) if metadata else settings.embedding_model

            # Verificar se ja existe
            result = session.execute(
                sql_text("SELECT id FROM embeddings WHERE chunk_id = :chunk_id"),
                {"chunk_id": chunk_id}
            )
            existing = result.fetchone()

            if existing:
                session.execute(
                    sql_text(
                        "UPDATE embeddings SET vector = :vector::vector, model = :model "
                        "WHERE chunk_id = :chunk_id"
                    ),
                    {"vector": str(vector), "model": model, "chunk_id": chunk_id}
                )
            else:
                session.execute(
                    sql_text(
                        "INSERT INTO embeddings (chunk_id, model, vector) "
                        "VALUES (:chunk_id, :model, :vector::vector)"
                    ),
                    {"chunk_id": chunk_id, "model": model, "vector": str(vector)}
                )

            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    async def upsert_batch(
        self,
        ids: List[str],
        vectors: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        contents: Optional[List[str]] = None,
    ) -> None:
        """Insere vetores em lote"""
        for i, (id_val, vector) in enumerate(zip(ids, vectors)):
            meta = metadatas[i] if metadatas else None
            content = contents[i] if contents else None
            await self.upsert(id_val, vector, meta, content)

    async def search(
        self,
        query_vector: List[float],
        limit: int = 10,
        threshold: float = 0.0,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """Busca vetorial usando pgvector"""
        session = self._get_session()

        try:
            similarity_expr = settings.get_similarity_expression("e.vector", ":query_vector")
            dist_op = settings.pgvector_distance_operator

            # Construir filtros
            filter_clause = ""
            params: Dict[str, Any] = {
                "query_vector": str(query_vector),
                "threshold": threshold,
                "limit": limit,
            }

            if filters:
                if filters.get("candidate_id"):
                    filter_clause += " AND c.candidate_id = :candidate_id"
                    params["candidate_id"] = filters["candidate_id"]
                if filters.get("document_id"):
                    filter_clause += " AND c.document_id = :document_id"
                    params["document_id"] = filters["document_id"]
                if filters.get("section"):
                    filter_clause += " AND c.section = :section"
                    params["section"] = filters["section"]

            sql = sql_text(f"""
                SELECT
                    c.id as chunk_id,
                    c.candidate_id,
                    c.document_id,
                    c.section,
                    c.content,
                    c.meta_json,
                    {similarity_expr} as similarity
                FROM chunks c
                JOIN embeddings e ON e.chunk_id = c.id
                WHERE {similarity_expr} >= :threshold
                {filter_clause}
                ORDER BY e.vector {dist_op} :query_vector::vector
                LIMIT :limit
            """)

            result = session.execute(sql, params)
            results = []

            for row in result:
                results.append(VectorSearchResult(
                    id=str(row.chunk_id),
                    score=float(row.similarity),
                    metadata={
                        "candidate_id": row.candidate_id,
                        "document_id": row.document_id,
                        "section": row.section,
                        "meta_json": row.meta_json,
                    },
                    content=row.content,
                ))

            return results

        finally:
            session.close()

    async def delete(self, id: str) -> None:
        """Remove embedding por chunk_id"""
        session = self._get_session()
        try:
            session.execute(
                sql_text("DELETE FROM embeddings WHERE chunk_id = :chunk_id"),
                {"chunk_id": int(id)}
            )
            session.commit()
        finally:
            session.close()

    async def delete_by_filter(self, filters: Dict[str, Any]) -> int:
        """Remove embeddings por filtro"""
        session = self._get_session()
        try:
            if filters.get("document_id"):
                result = session.execute(
                    sql_text(
                        "DELETE FROM embeddings WHERE chunk_id IN "
                        "(SELECT id FROM chunks WHERE document_id = :document_id)"
                    ),
                    {"document_id": filters["document_id"]}
                )
            elif filters.get("candidate_id"):
                result = session.execute(
                    sql_text(
                        "DELETE FROM embeddings WHERE chunk_id IN "
                        "(SELECT id FROM chunks WHERE candidate_id = :candidate_id)"
                    ),
                    {"candidate_id": filters["candidate_id"]}
                )
            else:
                return 0

            session.commit()
            return result.rowcount
        finally:
            session.close()

    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Conta embeddings"""
        session = self._get_session()
        try:
            if filters and filters.get("candidate_id"):
                result = session.execute(
                    sql_text(
                        "SELECT COUNT(*) FROM embeddings e "
                        "JOIN chunks c ON c.id = e.chunk_id "
                        "WHERE c.candidate_id = :candidate_id"
                    ),
                    {"candidate_id": filters["candidate_id"]}
                )
            else:
                result = session.execute(sql_text("SELECT COUNT(*) FROM embeddings"))
            return result.scalar() or 0
        finally:
            session.close()

    async def health_check(self) -> Dict[str, Any]:
        """Verifica saude do pgvector"""
        session = self._get_session()
        try:
            result = session.execute(sql_text("SELECT 1"))
            result.fetchone()

            # Verificar extensao pgvector
            ext_result = session.execute(sql_text(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
            ))
            ext_row = ext_result.fetchone()
            pgvector_version = ext_row[0] if ext_row else "not installed"

            count = await self.count()

            return {
                "status": "healthy",
                "provider": "pgvector",
                "pgvector_version": pgvector_version,
                "embeddings_count": count,
                "distance_metric": settings.pgvector_distance_metric,
                "dimensions": settings.embedding_dimensions,
            }
        except Exception as e:
            return {"status": "unhealthy", "provider": "pgvector", "error": str(e)}
        finally:
            session.close()

    async def get_info(self) -> Dict[str, Any]:
        """Retorna info do store"""
        health = await self.health_check()
        return {
            **health,
            "hnsw_m": settings.pgvector_hnsw_m,
            "hnsw_ef_construction": settings.pgvector_hnsw_ef_construction,
            "fts_language": settings.fts_language,
            "database_url": settings.effective_pgvector_url.split("@")[-1] if "@" in settings.effective_pgvector_url else "configured",
        }
