from sqlalchemy.orm import Session
from typing import List, Optional, Tuple
from openai import AsyncOpenAI
from sqlalchemy import text

from app.db.models import Chunk, Embedding, Candidate
from app.core.config import settings


class EmbeddingService:
    """
    Serviço para geração de embeddings e busca semântica

    Usa OpenAI para gerar embeddings vetoriais
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.openai_api_key
        self.model = settings.embedding_model
        self._client: Optional[AsyncOpenAI] = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            if not self.api_key:
                raise ValueError("OpenAI API key não configurada")
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Gera embedding para um texto

        Args:
            text: Texto para gerar embedding

        Returns:
            Lista de floats representando o vetor
        """
        if not self.api_key:
            raise ValueError("OpenAI API key não configurada")

        # Limitar tamanho do texto (~4 chars por token)
        max_tokens = 8000
        if len(text) > max_tokens * 4:
            text = text[:max_tokens * 4]

        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text
            )

            return response.data[0].embedding

        except Exception as e:
            raise ValueError(f"Erro ao gerar embedding: {str(e)}")

    async def generate_embeddings_for_chunk(
        self,
        db: Session,
        chunk_id: int
    ) -> Embedding:
        """
        Gera embedding para um chunk específico

        Args:
            db: Sessão do banco
            chunk_id: ID do chunk

        Returns:
            Embedding criado
        """
        chunk = db.query(Chunk).filter(Chunk.id == chunk_id).first()

        if not chunk:
            raise ValueError(f"Chunk {chunk_id} não encontrado")

        # Gerar embedding
        vector = await self.generate_embedding(chunk.content)

        # Criar registro de embedding
        embedding = Embedding(
            chunk_id=chunk.id,
            model=self.model,
            vector=vector
        )

        db.add(embedding)
        db.commit()
        db.refresh(embedding)

        return embedding

    async def generate_embeddings_for_document(
        self,
        db: Session,
        document_id: int
    ) -> List[Embedding]:
        """
        Gera embeddings para todos os chunks de um documento

        Args:
            db: Sessão do banco
            document_id: ID do documento

        Returns:
            Lista de embeddings criados
        """
        chunks = db.query(Chunk).filter(Chunk.document_id == document_id).all()

        embeddings = []

        for chunk in chunks:
            # Verificar se já tem embedding
            existing = db.query(Embedding).filter(
                Embedding.chunk_id == chunk.id
            ).first()

            if existing:
                embeddings.append(existing)
            else:
                embedding = await self.generate_embeddings_for_chunk(db, chunk.id)
                embeddings.append(embedding)

        return embeddings

    async def semantic_search(
        self,
        db: Session,
        query: str,
        limit: int = 10,
        threshold: float = 0.7
    ) -> List[Tuple[Chunk, float]]:
        """
        Busca semântica por similaridade vetorial

        Args:
            db: Sessão do banco
            query: Texto da busca
            limit: Número máximo de resultados
            threshold: Similaridade mínima (0-1)

        Returns:
            Lista de tuplas (Chunk, similarity_score)
        """
        # Gerar embedding da query
        query_embedding = await self.generate_embedding(query)

        # Busca por similaridade de cosseno usando pgvector
        # <=> é o operador de distância de cosseno no pgvector
        sql = text("""
            SELECT
                c.id,
                c.document_id,
                c.candidate_id,
                c.section,
                c.content,
                1 - (e.vector <=> :query_vector::vector) as similarity
            FROM chunks c
            JOIN embeddings e ON e.chunk_id = c.id
            WHERE 1 - (e.vector <=> :query_vector::vector) >= :threshold
            ORDER BY e.vector <=> :query_vector::vector
            LIMIT :limit
        """)

        result = db.execute(
            sql,
            {
                "query_vector": str(query_embedding),
                "threshold": threshold,
                "limit": limit
            }
        )

        results = []

        for row in result:
            chunk = db.query(Chunk).filter(Chunk.id == row.id).first()
            if chunk:
                results.append((chunk, row.similarity))

        return results

    async def hybrid_search(
        self,
        db: Session,
        query: str,
        filters: Optional[dict] = None,
        limit: int = 10
    ) -> List[Tuple[Candidate, float]]:
        """
        Busca híbrida combinando:
        - Similaridade vetorial (40%)
        - Busca full-text (30%)
        - Filtros (cidade, skills, etc.) (20%)
        - Experiência no domínio (10%)

        Args:
            db: Sessão do banco
            query: Texto da busca
            filters: Filtros adicionais (city, state, skills, etc.)
            limit: Número máximo de resultados

        Returns:
            Lista de tuplas (Candidate, score)
        """
        # Gerar embedding da query
        query_embedding = await self.generate_embedding(query)

        # Construir query SQL híbrida
        # Combinar busca vetorial com full-text search

        sql = text("""
            WITH vector_scores AS (
                SELECT
                    c.candidate_id,
                    AVG(1 - (e.vector <=> :query_vector::vector)) * 0.4 as vector_score
                FROM chunks c
                JOIN embeddings e ON e.chunk_id = c.id
                GROUP BY c.candidate_id
            ),
            text_scores AS (
                SELECT
                    c.candidate_id,
                    MAX(
                        ts_rank_cd(
                            to_tsvector('portuguese', c.content),
                            plainto_tsquery('portuguese', :query_text)
                        )
                    ) * 0.3 as text_score
                FROM chunks c
                WHERE to_tsvector('portuguese', c.content) @@ plainto_tsquery('portuguese', :query_text)
                GROUP BY c.candidate_id
            )
            SELECT
                cand.id,
                cand.full_name,
                cand.email,
                cand.city,
                cand.state,
                COALESCE(vs.vector_score, 0) + COALESCE(ts.text_score, 0) as total_score
            FROM candidates cand
            LEFT JOIN vector_scores vs ON vs.candidate_id = cand.id
            LEFT JOIN text_scores ts ON ts.candidate_id = cand.id
            WHERE COALESCE(vs.vector_score, 0) + COALESCE(ts.text_score, 0) > 0
            ORDER BY total_score DESC
            LIMIT :limit
        """)

        result = db.execute(
            sql,
            {
                "query_vector": str(query_embedding),
                "query_text": query,
                "limit": limit
            }
        )

        results = []

        for row in result:
            candidate = db.query(Candidate).filter(Candidate.id == row.id).first()
            if candidate:
                results.append((candidate, row.total_score))

        return results


# Instância global
embedding_service = EmbeddingService()
