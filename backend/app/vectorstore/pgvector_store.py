"""
Implementacao do VectorStore para PostgreSQL com pgvector

Usa o banco PostgreSQL existente com a extensao pgvector.
Compativel com indices HNSW e IVFFlat.

Suporta schemas customizados via DATABASE_SCHEMA.
"""
import logging
from typing import List, Optional, Dict, Any

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.vectorstore.base import VectorStore, VectorSearchResult
from app.core.config import settings

logger = logging.getLogger(__name__)


def _pgvector_similarity_expr(column: str, bind_name: str = "query_vector") -> str:
    """Expressao de similaridade segura para SQLAlchemy + psycopg.

    Nao usar :param::vector, porque SQLAlchemy/psycopg pode deixar o cast
    literal no SQL e o PostgreSQL acusa erro perto de ':'. Use CAST(:param AS vector).
    """
    metric = (settings.pgvector_distance_metric or "cosine").lower()
    bind = f"CAST(:{bind_name} AS vector)"
    if metric == "cosine":
        return f"1 - ({column} <=> {bind})"
    if metric == "l2":
        return f"1 - ({column} <-> {bind})"
    if metric in {"inner_product", "ip"}:
        return f"({column} <#> {bind}) * -1"
    logger.warning("Metrica pgvector invalida '%s', usando cosine", metric)
    return f"1 - ({column} <=> {bind})"


def _pgvector_distance_order(column: str, bind_name: str = "query_vector") -> str:
    metric = (settings.pgvector_distance_metric or "cosine").lower()
    op = "<=>"
    if metric == "l2":
        op = "<->"
    elif metric in {"inner_product", "ip"}:
        op = "<#>"
    return f"{column} {op} CAST(:{bind_name} AS vector)"


class PgVectorStore(VectorStore):
    """
    VectorStore usando PostgreSQL + pgvector

    Armazena vetores na tabela `embeddings` vinculada a `chunks`.
    Suporta schemas customizados via DATABASE_SCHEMA.
    """

    def __init__(self):
        self._engine = None
        self._session_factory = None

    def _get_engine(self):
        if self._engine is None:
            from app.db.database import create_configured_engine
            self._engine = create_configured_engine(settings.effective_pgvector_url)
        return self._engine

    def _get_session(self) -> Session:
        if self._session_factory is None:
            from sqlalchemy.orm import sessionmaker
            self._session_factory = sessionmaker(bind=self._get_engine())
        return self._session_factory()

    def _sp(self) -> str:
        return settings.database_schema_sql

    async def initialize(self) -> None:
        engine = self._get_engine()
        sp = self._sp()

        with engine.connect() as conn:
            schema = settings.database_schema
            if schema and schema != "public":
                try:
                    conn.execute(sql_text(f"CREATE SCHEMA IF NOT EXISTS {schema};"))
                    conn.commit()
                except Exception as e:
                    logger.debug(f"Schema creation: {e}")

            try:
                conn.execute(sql_text("CREATE EXTENSION IF NOT EXISTS vector;"))
                conn.commit()
                logger.info("pgvector extension verified")
            except Exception as e:
                logger.warning(f"Could not create pgvector extension: {e}")

            if settings.enable_hnsw_index:
                try:
                    result = conn.execute(sql_text(
                        "SELECT indexname FROM pg_indexes WHERE indexname = 'idx_embeddings_vector_hnsw'"
                    ))
                    if result.fetchone() is None:
                        conn.execute(sql_text(
                            f"CREATE INDEX idx_embeddings_vector_hnsw "
                            f"ON {sp}embeddings USING hnsw (vector {settings.pgvector_distance_ops}) "
                            f"WITH (m = {settings.pgvector_hnsw_m}, ef_construction = {settings.pgvector_hnsw_ef_construction});"
                        ))
                        conn.commit()
                        logger.info("HNSW index created")
                except Exception as e:
                    logger.warning(f"Could not create HNSW index: {e}")

            try:
                _VALID_FTS_LANGS = {"portuguese", "english", "spanish", "french", "german", "italian", "dutch", "russian", "simple"}
                fts_lang = settings.fts_language if settings.fts_language in _VALID_FTS_LANGS else "portuguese"
                result = conn.execute(sql_text(
                    "SELECT indexname FROM pg_indexes WHERE indexname = 'idx_chunks_content_fts'"
                ))
                if result.fetchone() is None:
                    conn.execute(sql_text(
                        f"CREATE INDEX idx_chunks_content_fts ON {sp}chunks USING GIN (to_tsvector('{fts_lang}', content));"
                    ))
                    conn.commit()
                    logger.info("FTS index created")
            except Exception as e:
                logger.warning(f"Could not create FTS index: {e}")

            try:
                result = conn.execute(sql_text(
                    "SELECT indexname FROM pg_indexes WHERE indexname = 'idx_chunks_meta_json'"
                ))
                if result.fetchone() is None:
                    conn.execute(sql_text(
                        f"CREATE INDEX idx_chunks_meta_json ON {sp}chunks USING GIN (meta_json jsonb_path_ops);"
                    ))
                    conn.commit()
            except Exception as e:
                logger.debug(f"JSON index: {e}")

    async def upsert(self, id: str, vector: List[float], metadata: Optional[Dict[str, Any]] = None, content: Optional[str] = None) -> None:
        session = self._get_session()
        sp = self._sp()
        try:
            chunk_id = int(id)
            model = metadata.get("model", settings.embedding_model) if metadata else settings.embedding_model
            vector_text = str(vector)

            result = session.execute(
                sql_text(f"SELECT id FROM {sp}embeddings WHERE chunk_id = :chunk_id"),
                {"chunk_id": chunk_id},
            )
            existing = result.fetchone()

            if existing:
                session.execute(
                    sql_text(
                        f"UPDATE {sp}embeddings SET vector = CAST(:vector AS vector), model = :model WHERE chunk_id = :chunk_id"
                    ),
                    {"vector": vector_text, "model": model, "chunk_id": chunk_id},
                )
            else:
                session.execute(
                    sql_text(
                        f"INSERT INTO {sp}embeddings (chunk_id, model, vector) VALUES (:chunk_id, :model, CAST(:vector AS vector))"
                    ),
                    {"chunk_id": chunk_id, "model": model, "vector": vector_text},
                )

            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    async def upsert_batch(self, ids: List[str], vectors: List[List[float]], metadatas: Optional[List[Dict[str, Any]]] = None, contents: Optional[List[str]] = None) -> None:
        for i, (id_val, vector) in enumerate(zip(ids, vectors)):
            meta = metadatas[i] if metadatas else None
            content = contents[i] if contents else None
            await self.upsert(id_val, vector, meta, content)

    async def search(self, query_vector: List[float], limit: int = 10, threshold: float = 0.0, filters: Optional[Dict[str, Any]] = None) -> List[VectorSearchResult]:
        session = self._get_session()
        sp = self._sp()

        try:
            similarity_expr = _pgvector_similarity_expr("e.vector", "query_vector")
            order_expr = _pgvector_distance_order("e.vector", "query_vector")

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
                FROM {sp}chunks c
                JOIN {sp}embeddings e ON e.chunk_id = c.id
                WHERE {similarity_expr} >= :threshold
                {filter_clause}
                ORDER BY {order_expr}
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
        session = self._get_session()
        sp = self._sp()
        try:
            session.execute(sql_text(f"DELETE FROM {sp}embeddings WHERE chunk_id = :chunk_id"), {"chunk_id": int(id)})
            session.commit()
        finally:
            session.close()

    async def delete_by_filter(self, filters: Dict[str, Any]) -> int:
        session = self._get_session()
        sp = self._sp()
        try:
            if filters.get("document_id"):
                result = session.execute(
                    sql_text(f"DELETE FROM {sp}embeddings WHERE chunk_id IN (SELECT id FROM {sp}chunks WHERE document_id = :document_id)"),
                    {"document_id": filters["document_id"]},
                )
            elif filters.get("candidate_id"):
                result = session.execute(
                    sql_text(f"DELETE FROM {sp}embeddings WHERE chunk_id IN (SELECT id FROM {sp}chunks WHERE candidate_id = :candidate_id)"),
                    {"candidate_id": filters["candidate_id"]},
                )
            else:
                return 0

            session.commit()
            return result.rowcount
        finally:
            session.close()

    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        session = self._get_session()
        sp = self._sp()
        try:
            if filters and filters.get("candidate_id"):
                result = session.execute(
                    sql_text(f"SELECT COUNT(*) FROM {sp}embeddings e JOIN {sp}chunks c ON c.id = e.chunk_id WHERE c.candidate_id = :candidate_id"),
                    {"candidate_id": filters["candidate_id"]},
                )
            else:
                result = session.execute(sql_text(f"SELECT COUNT(*) FROM {sp}embeddings"))
            return result.scalar() or 0
        finally:
            session.close()

    async def health_check(self) -> Dict[str, Any]:
        session = self._get_session()
        try:
            result = session.execute(sql_text("SELECT 1"))
            result.fetchone()

            ext_result = session.execute(sql_text("SELECT extversion FROM pg_extension WHERE extname = 'vector'"))
            ext_row = ext_result.fetchone()
            pgvector_version = ext_row[0] if ext_row else "not installed"
            count = await self.count()

            return {
                "status": "healthy",
                "provider": "pgvector",
                "pgvector_version": pgvector_version,
                "embeddings_count": count,
                "distance_metric": settings.pgvector_distance_metric,
                "dimensions": settings.active_embedding_dimensions,
                "schema": settings.database_schema,
            }
        except Exception as e:
            return {"status": "unhealthy", "provider": "pgvector", "error": str(e)}
        finally:
            session.close()

    async def get_info(self) -> Dict[str, Any]:
        health = await self.health_check()
        return {
            **health,
            "hnsw_m": settings.pgvector_hnsw_m,
            "hnsw_ef_construction": settings.pgvector_hnsw_ef_construction,
            "fts_language": settings.fts_language,
            "database_url": settings.effective_pgvector_url.split("@")[-1] if "@" in settings.effective_pgvector_url else "configured",
        }
