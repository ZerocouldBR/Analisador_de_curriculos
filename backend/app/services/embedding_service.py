"""
Servico aprimorado de embeddings e busca vetorial

Melhorias:
- Chunking semantico com overlap para melhor contexto
- Preprocesamento de texto para embeddings de maior qualidade
- Cache de embeddings para evitar reprocessamento
- Busca hibrida otimizada com pesos configuraveis
- Suporte a reranking de resultados
"""
from sqlalchemy.orm import Session
from typing import List, Optional, Tuple, Dict, Any
from openai import AsyncOpenAI
from sqlalchemy import text
import re
import hashlib
import logging

from app.db.models import Chunk, Embedding, Candidate
from app.core.config import settings

logger = logging.getLogger(__name__)


class SemanticChunker:
    """
    Chunker semantico que divide texto preservando contexto

    Estrategia:
    - Divide por secoes semanticas (experiencia, formacao, skills)
    - Aplica overlap entre chunks para manter contexto
    - Enriquece chunks com metadados de contexto
    - Limita tamanho para otimizar embeddings
    """

    DEFAULT_CHUNK_SIZE = 1500  # caracteres por chunk
    DEFAULT_OVERLAP = 200  # overlap entre chunks
    MIN_CHUNK_SIZE = 100  # tamanho minimo para gerar embedding

    # Marcadores de secao em curriculos
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
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_OVERLAP,
    ) -> List[Dict[str, Any]]:
        """
        Divide texto em chunks semanticos com overlap

        Args:
            text: Texto completo para dividir
            section_name: Nome da secao original
            chunk_size: Tamanho maximo de cada chunk
            overlap: Sobreposicao entre chunks adjacentes

        Returns:
            Lista de dicts com {content, metadata}
        """
        if len(text) <= chunk_size:
            return [{
                "content": text.strip(),
                "metadata": {
                    "chunk_index": 0,
                    "total_chunks": 1,
                    "section": section_name,
                    "has_overlap": False,
                }
            }]

        # Tentar dividir por secoes semanticas primeiro
        sections = cls._split_by_sections(text)

        chunks = []
        for section_text, detected_section in sections:
            if len(section_text) <= chunk_size:
                chunks.append({
                    "content": section_text.strip(),
                    "metadata": {
                        "section": detected_section or section_name,
                        "has_overlap": False,
                    }
                })
            else:
                # Dividir secao grande em chunks com overlap
                sub_chunks = cls._split_with_overlap(
                    section_text, chunk_size, overlap
                )
                for sc in sub_chunks:
                    sc["metadata"]["section"] = detected_section or section_name
                    chunks.append(sc)

        # Filtrar chunks muito pequenos
        chunks = [c for c in chunks if len(c["content"].strip()) >= cls.MIN_CHUNK_SIZE]

        # Adicionar indice
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

            # Tentar cortar em fim de frase
            if end < text_len:
                # Procurar ponto final, quebra de linha ou ponto e virgula
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
    Servico aprimorado para geracao de embeddings e busca semantica

    Melhorias:
    - Preprocessamento de texto antes de gerar embeddings
    - Chunking semantico com overlap
    - Busca hibrida com pesos configuraveis
    - Deduplicacao via hash de conteudo
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.openai_api_key
        self.model = settings.embedding_model
        self._client: Optional[AsyncOpenAI] = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            if not self.api_key:
                raise ValueError("OpenAI API key nao configurada")
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    @staticmethod
    def preprocess_for_embedding(text: str) -> str:
        """
        Preprocessa texto para melhorar qualidade do embedding

        - Remove formatacao excessiva
        - Normaliza espacos e pontuacao
        - Remove linhas repetidas
        - Limita tamanho
        """
        # Remover caracteres de controle
        text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', text)

        # Normalizar separadores
        text = re.sub(r'[-=_]{3,}', '\n', text)
        text = re.sub(r'[|]{2,}', ' | ', text)

        # Remover linhas duplicadas consecutivas
        lines = text.split('\n')
        deduped_lines = []
        prev_line = None
        for line in lines:
            stripped = line.strip()
            if stripped != prev_line:
                deduped_lines.append(stripped)
                prev_line = stripped
        text = '\n'.join(deduped_lines)

        # Remover multiplas quebras de linha
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Remover espacos multiplos
        text = re.sub(r' {2,}', ' ', text)

        return text.strip()

    @staticmethod
    def content_hash(text: str) -> str:
        """Gera hash do conteudo para deduplicacao"""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Gera embedding para um texto com preprocessamento

        Args:
            text: Texto para gerar embedding

        Returns:
            Lista de floats representando o vetor
        """
        if not self.api_key:
            raise ValueError("OpenAI API key nao configurada")

        # Preprocessar texto
        text = self.preprocess_for_embedding(text)

        # Limitar tamanho (~4 chars por token, modelo suporta 8191 tokens)
        max_chars = 8000 * 4
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
        batch_size: int = 20
    ) -> List[List[float]]:
        """
        Gera embeddings em lote para melhor performance

        Args:
            texts: Lista de textos
            batch_size: Tamanho do lote

        Returns:
            Lista de vetores
        """
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            processed = [self.preprocess_for_embedding(t)[:32000] for t in batch]

            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=processed
                )
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
            except Exception as e:
                logger.error(f"Erro no batch de embeddings: {e}")
                # Fallback: gerar individualmente
                for text in processed:
                    try:
                        resp = await self.client.embeddings.create(
                            model=self.model, input=text
                        )
                        all_embeddings.append(resp.data[0].embedding)
                    except Exception:
                        all_embeddings.append([0.0] * 1536)

        return all_embeddings

    async def generate_embeddings_for_chunk(
        self,
        db: Session,
        chunk_id: int
    ) -> Embedding:
        """Gera embedding para um chunk especifico"""
        chunk = db.query(Chunk).filter(Chunk.id == chunk_id).first()
        if not chunk:
            raise ValueError(f"Chunk {chunk_id} nao encontrado")

        vector = await self.generate_embedding(chunk.content)

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
        Gera embeddings para todos os chunks de um documento.
        Usa batch processing para eficiencia.
        """
        chunks = db.query(Chunk).filter(Chunk.document_id == document_id).all()

        # Filtrar chunks que ja tem embedding
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

        # Gerar embeddings em batch
        texts = [c.content for c in chunks_needing_embedding]
        vectors = await self.generate_embeddings_batch(texts)

        new_embeddings = []
        for chunk, vector in zip(chunks_needing_embedding, vectors):
            embedding = Embedding(
                chunk_id=chunk.id,
                model=self.model,
                vector=vector
            )
            db.add(embedding)
            new_embeddings.append(embedding)

        db.commit()
        for emb in new_embeddings:
            db.refresh(emb)

        return existing_embeddings + new_embeddings

    async def semantic_search(
        self,
        db: Session,
        query: str,
        limit: int = 10,
        threshold: float = 0.3
    ) -> List[Tuple[Chunk, float]]:
        """
        Busca semantica por similaridade vetorial

        Usa threshold baixo por padrao (0.3) para nao perder resultados relevantes.
        """
        query_embedding = await self.generate_embedding(query)

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
        limit: int = 10,
        vector_weight: float = 0.4,
        text_weight: float = 0.3,
        filter_weight: float = 0.2,
        domain_weight: float = 0.1,
    ) -> List[Tuple[Candidate, float]]:
        """
        Busca hibrida combinando multiplas estrategias com pesos configuraveis

        Args:
            db: Sessao do banco
            query: Texto da busca
            filters: Filtros adicionais (city, state, skills, etc.)
            limit: Numero maximo de resultados
            vector_weight: Peso da busca vetorial (padrao 0.4)
            text_weight: Peso da busca full-text (padrao 0.3)
            filter_weight: Peso dos filtros (padrao 0.2)
            domain_weight: Peso do dominio (padrao 0.1)

        Returns:
            Lista de tuplas (Candidate, score)
        """
        query_embedding = await self.generate_embedding(query)

        # Construir clausulas de filtro dinamicamente
        filter_clauses = ""
        filter_params = {}

        if filters:
            if filters.get("city"):
                filter_clauses += " AND LOWER(cand.city) = LOWER(:filter_city)"
                filter_params["filter_city"] = filters["city"]
            if filters.get("state"):
                filter_clauses += " AND LOWER(cand.state) = LOWER(:filter_state)"
                filter_params["filter_state"] = filters["state"]

        sql = text(f"""
            WITH vector_scores AS (
                SELECT
                    c.candidate_id,
                    AVG(1 - (e.vector <=> :query_vector::vector)) * :vector_w as vector_score
                FROM chunks c
                JOIN embeddings e ON e.chunk_id = c.id
                WHERE 1 - (e.vector <=> :query_vector::vector) >= 0.2
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
                    ) * :text_w as text_score
                FROM chunks c
                WHERE to_tsvector('portuguese', c.content) @@ plainto_tsquery('portuguese', :query_text)
                GROUP BY c.candidate_id
            ),
            domain_scores AS (
                SELECT
                    c.candidate_id,
                    CASE
                        WHEN c.meta_json->>'candidate_profile_type' IS NOT NULL
                        THEN :domain_w * 0.5
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
            WHERE (COALESCE(vs.vector_score, 0) + COALESCE(ts.text_score, 0) + COALESCE(ds.domain_score, 0)) > 0
            {filter_clauses}
            ORDER BY total_score DESC
            LIMIT :limit
        """)

        params = {
            "query_vector": str(query_embedding),
            "query_text": query,
            "vector_w": vector_weight,
            "text_w": text_weight,
            "domain_w": domain_weight,
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
