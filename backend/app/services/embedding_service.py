"""
Servico de embeddings e busca vetorial

Todas as configuracoes vem de app.core.config.settings.
Nenhum valor hardcoded.

Usa a camada de abstracao VectorStore para suportar
multiplos provedores (pgvector, Supabase, Qdrant).
"""
import re
import hashlib
import logging
from typing import List, Optional, Tuple, Dict, Any

from openai import AsyncOpenAI
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.models import Chunk, Embedding, Candidate
from app.core.config import settings, EmbeddingMode
from app.vectorstore import get_vector_store

logger = logging.getLogger(__name__)


class SemanticChunker:
    """
    Chunker semantico que divide texto preservando contexto.

    Parametros configurados via settings:
    - chunk_size, chunk_overlap, chunk_min_size
    """

    SECTION_MARKERS = [
        r'(?i)^(?:experiencia|experience|experiência)\s*(?:profissional)?',
        r'(?i)^(?:formacao|formação|educacao|educação|education)',
        r'(?i)^(?:habilidades|skills|competencias|competências)',
        r'(?i)^(?:certificacoes|certificações|certifications|cursos)',
        r'(?i)^(?:idiomas|languages|linguas|línguas)',
        r'(?i)^(?:objetivo|objective|resumo|summary|perfil|profile)',
        r'(?i)^(?:dados\s*pessoais|personal\s*info|informacoes\s*pessoais)',
        r'(?i)^(?:projetos|projects)',
        r'(?i)^(?:disponibilidade|availability)',
        r'(?i)^(?:referencias|references)',
    ]

    @classmethod
    def create_semantic_chunks(
        cls,
        text: str,
        section_name: str = "full_text",
        chunk_size: Optional[int] = None,
        overlap: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Divide texto em chunks semanticos com overlap"""
        _chunk_size = chunk_size or settings.chunk_size
        _overlap = overlap or settings.chunk_overlap
        _min_size = settings.chunk_min_size

        if len(text) <= _chunk_size:
            return [{
                "content": text.strip(),
                "metadata": {
                    "chunk_index": 0,
                    "total_chunks": 1,
                    "section": section_name,
                    "has_overlap": False,
                }
            }]

        sections = cls._split_by_sections(text)

        chunks = []
        for section_text, detected_section in sections:
            if len(section_text) <= _chunk_size:
                chunks.append({
                    "content": section_text.strip(),
                    "metadata": {
                        "section": detected_section or section_name,
                        "has_overlap": False,
                    }
                })
            else:
                sub_chunks = cls._split_with_overlap(
                    section_text, _chunk_size, _overlap
                )
                for sc in sub_chunks:
                    sc["metadata"]["section"] = detected_section or section_name
                    chunks.append(sc)

        chunks = [c for c in chunks if len(c["content"].strip()) >= _min_size]

        for i, chunk in enumerate(chunks):
            chunk["metadata"]["chunk_index"] = i
            chunk["metadata"]["total_chunks"] = len(chunks)

        return chunks

    @classmethod
    def _split_by_sections(cls, text: str) -> List[Tuple[str, Optional[str]]]:
        """Divide texto por marcadores de secao"""
        lines = text.split('\n')
        sections = []
        current_section = []
        current_name = None

        for line in lines:
            is_section_header = False
            detected_name = None

            for pattern in cls.SECTION_MARKERS:
                if re.match(pattern, line.strip()):
                    is_section_header = True
                    detected_name = re.sub(r'[^a-z_]', '', line.strip().lower().replace(' ', '_'))[:30]
                    break

            if is_section_header and current_section:
                sections.append(('\n'.join(current_section), current_name))
                current_section = [line]
                current_name = detected_name
            else:
                current_section.append(line)
                if is_section_header:
                    current_name = detected_name

        if current_section:
            sections.append(('\n'.join(current_section), current_name))

        return sections if sections else [(text, None)]

    @classmethod
    def _split_with_overlap(
        cls, text: str, chunk_size: int, overlap: int
    ) -> List[Dict[str, Any]]:
        """Divide texto em chunks com sobreposicao"""
        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = start + chunk_size

            if end < text_len:
                for sep in ['. ', '.\n', '\n\n', '\n', '; ', ', ']:
                    last_sep = text.rfind(sep, start + chunk_size // 2, end)
                    if last_sep > start:
                        end = last_sep + len(sep)
                        break

            chunk_text = text[start:end].strip()

            if chunk_text:
                chunks.append({
                    "content": chunk_text,
                    "metadata": {
                        "has_overlap": start > 0,
                        "start_pos": start,
                        "end_pos": end,
                    }
                })

            start = end - overlap
            if start >= text_len:
                break

        return chunks


class EmbeddingService:
    """
    Servico para geracao de embeddings e busca vetorial.

    Suporta dois modos de vetorizacao:
    - API: Usa OpenAI ou outro provedor de API (custo por token)
    - CODE: Usa sentence-transformers local (custo zero de API)

    O modo e definido por settings.embedding_mode.
    Usa VectorStore para armazenamento e busca.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.openai_api_key
        self.model = settings.embedding_model
        self._client: Optional[AsyncOpenAI] = None
        self._local_service = None

    @property
    def is_local_mode(self) -> bool:
        """Verifica se esta no modo de vetorizacao local (code)"""
        return settings.embedding_mode == EmbeddingMode.CODE

    @property
    def active_model_name(self) -> str:
        """Retorna o nome do modelo ativo baseado no modo"""
        if self.is_local_mode:
            return settings.embedding_local_model
        return self.model

    @property
    def local_service(self):
        """Lazy-load do servico local"""
        if self._local_service is None:
            from app.services.local_embedding_service import LocalEmbeddingService
            self._local_service = LocalEmbeddingService()
        return self._local_service

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            if not self.api_key:
                raise ValueError("OpenAI API key nao configurada. Use EMBEDDING_MODE=code para vetorizacao local.")
            kwargs = {"api_key": self.api_key}
            if settings.openai_base_url:
                kwargs["base_url"] = settings.openai_base_url
            if settings.openai_organization:
                kwargs["organization"] = settings.openai_organization
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    @staticmethod
    def preprocess_for_embedding(text: str) -> str:
        """Preprocessa texto para melhorar qualidade do embedding"""
        text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', text)
        text = re.sub(r'[-=_]{3,}', '\n', text)
        text = re.sub(r'[|]{2,}', ' | ', text)

        lines = text.split('\n')
        deduped_lines = []
        prev_line = None
        for line in lines:
            stripped = line.strip()
            if stripped != prev_line:
                deduped_lines.append(stripped)
                prev_line = stripped
        text = '\n'.join(deduped_lines)

        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        return text.strip()

    @staticmethod
    def content_hash(text: str) -> str:
        """Gera hash do conteudo para deduplicacao"""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]

    async def generate_embedding(self, text: str) -> List[float]:
        """Gera embedding para um texto com preprocessamento (API ou local)"""
        text = self.preprocess_for_embedding(text)

        if self.is_local_mode:
            return self.local_service.generate_embedding(text)

        if not self.api_key:
            raise ValueError("OpenAI API key nao configurada. Use EMBEDDING_MODE=code para vetorizacao local.")

        max_chars = settings.embedding_max_chars
        if len(text) > max_chars:
            text = text[:max_chars]

        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            raise ValueError(f"Erro ao gerar embedding: {str(e)}")

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: Optional[int] = None,
    ) -> List[List[float]]:
        """Gera embeddings em lote (API ou local)"""
        _batch_size = batch_size or settings.embedding_batch_size

        processed = [
            self.preprocess_for_embedding(t)[:settings.embedding_max_chars]
            for t in texts
        ]

        if self.is_local_mode:
            return self.local_service.generate_embeddings_batch(processed, _batch_size)

        all_embeddings = []

        for i in range(0, len(processed), _batch_size):
            batch = processed[i:i + _batch_size]

            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=batch
                )
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
            except Exception as e:
                logger.error(f"Erro no batch de embeddings: {e}")
                for t in batch:
                    try:
                        resp = await self.client.embeddings.create(
                            model=self.model, input=t
                        )
                        all_embeddings.append(resp.data[0].embedding)
                    except Exception:
                        all_embeddings.append([0.0] * settings.active_embedding_dimensions)

        return all_embeddings

    # ================================================================
    # VectorStore-backed operations
    # ================================================================

    async def store_embedding(
        self,
        chunk_id: int,
        vector: List[float],
        metadata: Optional[Dict[str, Any]] = None,
        content: Optional[str] = None,
    ) -> None:
        """Armazena embedding em TODOS os VectorStores habilitados (fan-out)"""
        from app.vectorstore.factory import get_all_enabled_stores

        stores = get_all_enabled_stores()
        meta = metadata or {}
        meta["model"] = self.model

        errors = []
        for name, store in stores.items():
            try:
                await store.upsert(
                    id=str(chunk_id),
                    vector=vector,
                    metadata=meta,
                    content=content,
                )
            except Exception as e:
                logger.error(f"Erro ao gravar embedding em '{name}': {e}")
                errors.append((name, str(e)))

        if errors and len(errors) == len(stores):
            raise RuntimeError(f"Todos os stores falharam ao gravar: {errors}")

    async def store_embeddings_batch(
        self,
        chunk_ids: List[int],
        vectors: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        contents: Optional[List[str]] = None,
    ) -> None:
        """Armazena embeddings em lote em TODOS os VectorStores habilitados (fan-out)"""
        from app.vectorstore.factory import get_all_enabled_stores

        stores = get_all_enabled_stores()
        ids = [str(cid) for cid in chunk_ids]
        metas = metadatas or [{"model": self.model} for _ in chunk_ids]

        errors = []
        for name, store in stores.items():
            try:
                await store.upsert_batch(ids, vectors, metas, contents)
            except Exception as e:
                logger.error(f"Erro ao gravar embeddings batch em '{name}': {e}")
                errors.append((name, str(e)))

        if errors and len(errors) == len(stores):
            raise RuntimeError(f"Todos os stores falharam ao gravar batch: {errors}")

    async def search_vectors(
        self,
        query: str,
        limit: Optional[int] = None,
        threshold: Optional[float] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Busca vetorial usando o VectorStore configurado

        Returns:
            Lista de dicts com id, score, metadata, content
        """
        query_vector = await self.generate_embedding(query)
        store = get_vector_store()

        results = await store.search(
            query_vector=query_vector,
            limit=limit or settings.vector_search_limit,
            threshold=threshold or settings.vector_search_threshold,
            filters=filters,
        )

        return [
            {
                "id": r.id,
                "score": r.score,
                "metadata": r.metadata,
                "content": r.content,
            }
            for r in results
        ]

    # ================================================================
    # Legacy compatibility (used by existing code)
    # ================================================================

    async def generate_embeddings_for_chunk(
        self, db: Session, chunk_id: int
    ) -> Embedding:
        """Gera embedding para um chunk especifico (compatibilidade)"""
        chunk = db.query(Chunk).filter(Chunk.id == chunk_id).first()
        if not chunk:
            raise ValueError(f"Chunk {chunk_id} nao encontrado")

        vector = await self.generate_embedding(chunk.content)

        # Salvar no banco relacional
        embedding = Embedding(
            chunk_id=chunk.id,
            model=self.model,
            vector=vector
        )
        db.add(embedding)
        db.commit()
        db.refresh(embedding)

        # Salvar no VectorStore
        await self.store_embedding(
            chunk_id=chunk.id,
            vector=vector,
            metadata={
                "candidate_id": chunk.candidate_id,
                "document_id": chunk.document_id,
                "section": chunk.section,
            },
            content=chunk.content,
        )

        return embedding

    async def generate_embeddings_for_document(
        self, db: Session, document_id: int
    ) -> List[Embedding]:
        """Gera embeddings para todos os chunks de um documento"""
        chunks = db.query(Chunk).filter(Chunk.document_id == document_id).all()

        chunks_needing_embedding = []
        existing_embeddings = []

        for chunk in chunks:
            existing = db.query(Embedding).filter(
                Embedding.chunk_id == chunk.id
            ).first()
            if existing:
                existing_embeddings.append(existing)
            else:
                chunks_needing_embedding.append(chunk)

        if not chunks_needing_embedding:
            return existing_embeddings

        texts = [c.content for c in chunks_needing_embedding]
        vectors = await self.generate_embeddings_batch(texts)

        new_embeddings = []
        chunk_ids = []
        metadatas = []
        contents = []

        for chunk, vector in zip(chunks_needing_embedding, vectors):
            embedding = Embedding(
                chunk_id=chunk.id,
                model=self.model,
                vector=vector
            )
            db.add(embedding)
            new_embeddings.append(embedding)

            chunk_ids.append(chunk.id)
            metadatas.append({
                "candidate_id": chunk.candidate_id,
                "document_id": chunk.document_id,
                "section": chunk.section,
                "model": self.model,
            })
            contents.append(chunk.content)

        db.commit()
        for emb in new_embeddings:
            db.refresh(emb)

        # Salvar no VectorStore
        if chunk_ids:
            await self.store_embeddings_batch(
                chunk_ids, vectors, metadatas, contents
            )

        return existing_embeddings + new_embeddings

    async def semantic_search(
        self,
        db: Session,
        query: str,
        limit: int = 10,
        threshold: Optional[float] = None,
    ) -> List[Tuple[Chunk, float]]:
        """Busca semantica (compatibilidade com API existente)"""
        _threshold = threshold if threshold is not None else settings.vector_search_threshold

        vector_results = await self.search_vectors(
            query=query, limit=limit, threshold=_threshold
        )

        results = []
        for vr in vector_results:
            try:
                chunk_id = int(vr["id"])
            except (ValueError, TypeError):
                continue

            chunk = db.query(Chunk).filter(Chunk.id == chunk_id).first()
            if chunk:
                results.append((chunk, vr["score"]))

        return results

    async def hybrid_search(
        self,
        db: Session,
        query: str,
        filters: Optional[dict] = None,
        limit: int = 10,
    ) -> List[Tuple[Candidate, float]]:
        """
        Busca hibrida combinando multiplas estrategias.
        Pesos configurados via settings.
        """
        query_embedding = await self.generate_embedding(query)
        dist_op = settings.pgvector_distance_operator
        similarity_expr = settings.get_similarity_expression("e.vector", ":query_vector")
        pre_threshold = settings.vector_search_pre_filter_threshold

        filter_clauses = ""
        filter_params = {}

        if filters:
            if filters.get("city"):
                filter_clauses += " AND LOWER(cand.city) = LOWER(:filter_city)"
                filter_params["filter_city"] = filters["city"]
            if filters.get("state"):
                filter_clauses += " AND LOWER(cand.state) = LOWER(:filter_state)"
                filter_params["filter_state"] = filters["state"]

        # Whitelist de idiomas validos para prevenir SQL injection
        _VALID_FTS_LANGS = {
            "portuguese", "english", "spanish", "french", "german",
            "italian", "dutch", "russian", "simple",
        }
        fts_lang = settings.fts_language
        if fts_lang not in _VALID_FTS_LANGS:
            logger.warning(f"fts_language invalido: {fts_lang}, usando 'portuguese'")
            fts_lang = "portuguese"

        sql = text(f"""
            WITH vector_scores AS (
                SELECT
                    c.candidate_id,
                    AVG({similarity_expr}) * :vector_w as vector_score
                FROM chunks c
                JOIN embeddings e ON e.chunk_id = c.id
                WHERE {similarity_expr} >= :pre_threshold
                GROUP BY c.candidate_id
            ),
            text_scores AS (
                SELECT
                    c.candidate_id,
                    MAX(
                        ts_rank_cd(
                            to_tsvector('{fts_lang}', c.content),
                            plainto_tsquery('{fts_lang}', :query_text)
                        )
                    ) * :text_w as text_score
                FROM chunks c
                WHERE to_tsvector('{fts_lang}', c.content)
                    @@ plainto_tsquery('{fts_lang}', :query_text)
                GROUP BY c.candidate_id
            ),
            domain_scores AS (
                SELECT
                    c.candidate_id,
                    CASE
                        WHEN c.meta_json->>'candidate_profile_type' IS NOT NULL
                        THEN :domain_w * :domain_multiplier
                        ELSE 0
                    END as domain_score
                FROM chunks c
                WHERE c.section = 'full_text'
            )
            SELECT
                cand.id,
                cand.full_name,
                cand.email,
                cand.city,
                cand.state,
                COALESCE(vs.vector_score, 0)
                    + COALESCE(ts.text_score, 0)
                    + COALESCE(ds.domain_score, 0) as total_score
            FROM candidates cand
            LEFT JOIN vector_scores vs ON vs.candidate_id = cand.id
            LEFT JOIN text_scores ts ON ts.candidate_id = cand.id
            LEFT JOIN domain_scores ds ON ds.candidate_id = cand.id
            WHERE (COALESCE(vs.vector_score, 0) + COALESCE(ts.text_score, 0)
                   + COALESCE(ds.domain_score, 0)) > 0
            {filter_clauses}
            ORDER BY total_score DESC
            LIMIT :limit
        """)

        params = {
            "query_vector": str(query_embedding),
            "query_text": query,
            "vector_w": settings.hybrid_vector_weight,
            "text_w": settings.hybrid_text_weight,
            "domain_w": settings.hybrid_domain_weight,
            "domain_multiplier": settings.llm_domain_score_multiplier,
            "pre_threshold": pre_threshold,
            "limit": limit,
            **filter_params,
        }

        result = db.execute(sql, params)
        results = []

        for row in result:
            candidate = db.query(Candidate).filter(Candidate.id == row.id).first()
            if candidate:
                results.append((candidate, row.total_score))

        return results


# Instancia global
embedding_service = EmbeddingService()
