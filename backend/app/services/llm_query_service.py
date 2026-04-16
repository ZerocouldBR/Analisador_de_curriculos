"""
Servico de consulta ao LLM com retry inteligente

Implementa:
- Consulta iterativa a API do LLM
- Retry automatico com filtro de contexto quando atinge limite de caracteres
- Ate 5 tentativas para obter resposta completa
- Ranqueamento e selecao inteligente de chunks relevantes
- Sistema de prompts especializado para producao e logistica
"""
import asyncio
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.models import Chunk, Candidate, Embedding
from app.core.config import settings
from app.services.llm_client import llm_client
from app.services.keyword_extraction_service import KeywordExtractionService
from app.services.prompt_service import PromptService


class QueryStatus(Enum):
    """Status da consulta"""
    SUCCESS = "success"
    PARTIAL = "partial"
    TOKEN_LIMIT_REACHED = "token_limit_reached"
    ERROR = "error"
    MAX_RETRIES_REACHED = "max_retries_reached"


@dataclass
class QueryResult:
    """Resultado de uma consulta ao LLM"""
    status: QueryStatus
    answer: str
    chunks_used: int
    total_chunks_available: int
    tokens_used: int
    retries: int
    confidence_score: float
    sources: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChunkWithScore:
    """Chunk com score de relevancia"""
    chunk: Chunk
    semantic_score: float
    keyword_score: float
    combined_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class LLMQueryService:
    """
    Servico para consultas ao LLM com retry inteligente

    Todas as configuracoes vem de settings:
    - Modelo, temperatura, tokens
    - Limites de caracteres e chunks por retry
    - Pesos de scoring
    """

    # Prompts agora sao carregados dinamicamente via PromptService
    # Os defaults estao em config.py e podem ser editados via DB/API

    def __init__(self):
        pass

    @property
    def chat_model(self) -> str:
        return settings.chat_model

    def _detect_query_domain(self, question: str, db: Session = None) -> str:
        """Detecta o dominio da pergunta para selecionar prompt adequado.

        Keywords de dominio sao carregadas do DB/config via PromptService.
        """
        question_lower = question.lower()

        # Carregar keywords dinamicamente (DB override > config.py defaults)
        if db:
            keywords = PromptService.get_domain_keywords(db)
        else:
            keywords = {
                "production": settings.domain_keywords_production,
                "logistics": settings.domain_keywords_logistics,
                "quality": settings.domain_keywords_quality,
            }

        prod_score = sum(1 for t in keywords.get("production", []) if t in question_lower)
        log_score = sum(1 for t in keywords.get("logistics", []) if t in question_lower)
        qual_score = sum(1 for t in keywords.get("quality", []) if t in question_lower)

        max_score = max(prod_score, log_score, qual_score)

        if max_score == 0:
            return "general"
        if prod_score == max_score:
            return "production"
        if log_score == max_score:
            return "logistics"
        return "quality"

    async def query(
        self,
        db: Session,
        question: str,
        filters: Optional[Dict[str, Any]] = None,
        max_retries: Optional[int] = None,
        include_sources: bool = True,
        domain: Optional[str] = None
    ) -> QueryResult:
        """
        Executa consulta ao LLM com retry inteligente

        Args:
            db: Sessao do banco de dados
            question: Pergunta do usuario
            filters: Filtros opcionais (candidate_id, skills, etc.)
            max_retries: Numero maximo de tentativas (padrao: 5)
            include_sources: Incluir fontes na resposta
            domain: Dominio forçado (production, logistics, quality, general)

        Returns:
            QueryResult com resposta e metadados
        """
        if not settings.active_llm_api_key:
            return QueryResult(
                status=QueryStatus.ERROR,
                answer=f"API key do {settings.llm_provider.value} nao configurada",
                chunks_used=0,
                total_chunks_available=0,
                tokens_used=0,
                retries=0,
                confidence_score=0.0
            )

        # Detectar dominio da pergunta (usa keywords do DB/config)
        query_domain = domain or self._detect_query_domain(question, db)

        # Buscar chunks relevantes
        all_chunks = await self._search_relevant_chunks(db, question, filters)
        total_available = len(all_chunks)

        if not all_chunks:
            return QueryResult(
                status=QueryStatus.SUCCESS,
                answer="Nao encontrei curriculos relevantes para sua pergunta.",
                chunks_used=0,
                total_chunks_available=0,
                tokens_used=0,
                retries=0,
                confidence_score=0.0
            )

        _max_retries = max_retries if max_retries is not None else settings.llm_max_retries
        retries = 0
        last_error = None
        accumulated_answer = ""
        selected_chunks = []
        character_limits = settings.llm_character_limits
        chunks_per_retry = settings.llm_chunks_per_retry

        while retries < min(_max_retries, len(character_limits)):
            try:
                max_chunks = chunks_per_retry[retries] if retries < len(chunks_per_retry) else settings.llm_chunks_per_retry_fallback
                char_limit = character_limits[retries] if retries < len(character_limits) else settings.llm_character_limit_fallback

                selected_chunks = self._select_chunks_for_attempt(
                    all_chunks, max_chunks, char_limit
                )

                context = self._build_context(selected_chunks, char_limit)

                prompt = self._build_prompt(
                    question, context, retries, accumulated_answer, query_domain, db
                )

                response = await self._call_llm(prompt, retries)

                is_complete, answer = self._check_response_completeness(
                    response, accumulated_answer
                )

                if is_complete:
                    sources = []
                    if include_sources:
                        sources = self._extract_sources(selected_chunks)

                    return QueryResult(
                        status=QueryStatus.SUCCESS,
                        answer=answer,
                        chunks_used=len(selected_chunks),
                        total_chunks_available=total_available,
                        tokens_used=response.get("usage", {}).get("total_tokens", 0),
                        retries=retries + 1,
                        confidence_score=self._calculate_confidence(selected_chunks),
                        sources=sources,
                        metadata={
                            "char_limit_used": char_limit,
                            "chunks_limit_used": max_chunks,
                            "model": self.chat_model,
                            "domain": query_domain
                        }
                    )

                accumulated_answer = answer
                retries += 1

            except Exception as e:
                error_msg = str(e)
                if "maximum context length" in error_msg or "token" in error_msg.lower():
                    retries += 1
                    last_error = e
                    continue
                else:
                    last_error = e
                    retries += 1

        # Maximo de retries atingido
        if accumulated_answer:
            return QueryResult(
                status=QueryStatus.PARTIAL,
                answer=accumulated_answer,
                chunks_used=len(selected_chunks) if selected_chunks else 0,
                total_chunks_available=total_available,
                tokens_used=0,
                retries=retries,
                confidence_score=self._calculate_confidence(selected_chunks) * 0.7 if selected_chunks else 0,
                metadata={
                    "warning": "Resposta pode estar incompleta apos maximo de tentativas",
                    "domain": domain or "general"
                }
            )

        return QueryResult(
            status=QueryStatus.MAX_RETRIES_REACHED,
            answer=f"Nao foi possivel obter resposta apos {retries} tentativas. Erro: {last_error}",
            chunks_used=0,
            total_chunks_available=total_available,
            tokens_used=0,
            retries=retries,
            confidence_score=0.0
        )

    async def _search_relevant_chunks(
        self,
        db: Session,
        query: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ChunkWithScore]:
        """Busca chunks relevantes usando busca hibrida"""
        query_embedding = await self._generate_embedding(query)

        query_keywords = KeywordExtractionService.extract_keywords(query)
        keyword_terms = query_keywords.get("keywords", [])

        sql = text("""
            WITH semantic_scores AS (
                SELECT
                    c.id as chunk_id,
                    c.candidate_id,
                    c.section,
                    c.content,
                    c.meta_json,
                    1 - (e.vector <=> :query_vector::vector) as semantic_score
                FROM chunks c
                JOIN embeddings e ON e.chunk_id = c.id
                WHERE 1 - (e.vector <=> :query_vector::vector) >= :threshold
            )
            SELECT
                chunk_id,
                candidate_id,
                section,
                content,
                meta_json,
                semantic_score
            FROM semantic_scores
            ORDER BY semantic_score DESC
            LIMIT 50
        """)

        params = {
            "query_vector": str(query_embedding),
            "threshold": settings.vector_search_threshold,
        }

        if filters:
            if filters.get("candidate_id"):
                sql = text(sql.text.replace(
                    "WHERE 1 - (e.vector",
                    f"WHERE c.candidate_id = {filters['candidate_id']} AND 1 - (e.vector"
                ))

        result = db.execute(sql, params)
        rows = result.fetchall()

        chunks_with_scores = []

        for row in rows:
            chunk = db.query(Chunk).filter(Chunk.id == row.chunk_id).first()
            if not chunk:
                continue

            keyword_score = self._calculate_keyword_score(chunk.content, keyword_terms)

            # Bonus para chunks de keyword_index (contem resumo estruturado)
            section_bonus = 0.0
            if chunk.section == "keyword_index":
                section_bonus = 0.05
            elif chunk.section == "full_text":
                section_bonus = 0.03

            combined_score = (
                row.semantic_score * settings.llm_semantic_weight +
                keyword_score * settings.llm_keyword_weight +
                section_bonus
            )

            chunks_with_scores.append(ChunkWithScore(
                chunk=chunk,
                semantic_score=row.semantic_score,
                keyword_score=keyword_score,
                combined_score=combined_score,
                metadata=row.meta_json or {}
            ))

        chunks_with_scores.sort(key=lambda x: x.combined_score, reverse=True)

        return chunks_with_scores

    async def _generate_embedding(self, text: str) -> List[float]:
        """Gera embedding para um texto"""
        max_chars = settings.embedding_max_chars
        if len(text) > max_chars:
            text = text[:max_chars]

        response = await openai.Embedding.acreate(
            model=self.embedding_model,
            input=text
        )

        return response['data'][0]['embedding']

    def _calculate_keyword_score(self, content: str, keywords: List[str]) -> float:
        """Calcula score baseado em match de keywords"""
        if not keywords:
            return 0.0

        content_lower = content.lower()
        matches = sum(1 for kw in keywords if kw.lower() in content_lower)

        return min(matches / len(keywords), 1.0)

    def _select_chunks_for_attempt(
        self,
        chunks: List[ChunkWithScore],
        max_chunks: int,
        char_limit: int
    ) -> List[ChunkWithScore]:
        """Seleciona chunks para uma tentativa especifica"""
        selected = []
        total_chars = 0
        section_counts = {}

        for chunk in chunks:
            if len(selected) >= max_chunks:
                break

            chunk_chars = len(chunk.chunk.content)

            if total_chars + chunk_chars > char_limit:
                if selected:
                    break
                chunk_chars = char_limit - total_chars

            section = chunk.chunk.section
            if section_counts.get(section, 0) >= settings.llm_section_max_chunks:
                continue

            selected.append(chunk)
            total_chars += chunk_chars
            section_counts[section] = section_counts.get(section, 0) + 1

        return selected

    def _build_context(
        self,
        chunks: List[ChunkWithScore],
        char_limit: int
    ) -> str:
        """Constroi contexto a partir dos chunks selecionados"""
        context_parts = []
        total_chars = 0

        for i, chunk_with_score in enumerate(chunks):
            chunk = chunk_with_score.chunk

            candidate_info = ""
            if chunk.candidate:
                candidate_info = f"Candidato: {chunk.candidate.full_name or 'N/A'}"
                if chunk.candidate.email:
                    candidate_info += f" | Email: {chunk.candidate.email}"
                if chunk.candidate.city:
                    candidate_info += f" | Cidade: {chunk.candidate.city}"

            chunk_header = f"[CHUNK {i+1} - Secao: {chunk.section.upper()}]"
            if candidate_info:
                chunk_header += f"\n{candidate_info}"

            meta = chunk_with_score.metadata or {}

            # Incluir info de perfil se disponivel
            profile_type = meta.get("chunk_profile_type", "")
            if profile_type and profile_type != "general":
                chunk_header += f"\n[Perfil: {profile_type}]"

            if meta.get("search_index"):
                chunk_header += f"\n{meta['search_index'][:500]}"

            content = chunk.content

            available_chars = char_limit - total_chars - len(chunk_header) - 50
            if len(content) > available_chars:
                content = content[:available_chars] + "..."

            block = f"{chunk_header}\n{content}\n"
            context_parts.append(block)
            total_chars += len(block)

            if total_chars >= char_limit:
                break

        return "\n---\n".join(context_parts)

    def _build_prompt(
        self,
        question: str,
        context: str,
        retry_number: int,
        accumulated_answer: str,
        domain: str = "general",
        db: Session = None
    ) -> List[Dict[str, str]]:
        """Constroi o prompt para o LLM com dominio especializado.

        Prompts sao carregados dinamicamente via PromptService (DB override > config.py).
        """
        if db:
            system_prompt = PromptService.get_llm_prompt(db, domain)
        else:
            system_prompt = getattr(settings, f"prompt_llm_{domain}", settings.prompt_llm_general)

        user_prompt = f"""CONTEXTO DOS CURRICULOS:
{context}

PERGUNTA: {question}"""

        if retry_number > 0 and accumulated_answer:
            user_prompt += f"""

NOTA: Esta e uma continuacao. Resposta anterior (pode estar incompleta):
{accumulated_answer}

Por favor, complete ou refine a resposta se necessario."""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

    async def _call_llm(
        self,
        messages: List[Dict[str, str]],
        retry_number: int
    ) -> Dict[str, Any]:
        """Chama o LLM com os parametros apropriados (via cliente centralizado)"""
        temperature = max(
            settings.llm_min_temperature,
            settings.llm_temperature - (retry_number * settings.llm_temperature_decay)
        )
        max_tokens = max(
            settings.llm_min_tokens,
            settings.llm_max_tokens - (retry_number * settings.llm_token_decay)
        )

        response = await llm_client.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return {
            "content": response.content,
            "finish_reason": response.finish_reason,
            "usage": {
                "prompt_tokens": response.input_tokens,
                "completion_tokens": response.output_tokens,
                "total_tokens": response.tokens_used,
            }
        }

    def _check_response_completeness(
        self,
        response: Dict[str, Any],
        accumulated: str
    ) -> Tuple[bool, str]:
        """Verifica se a resposta esta completa"""
        content = response.get("content", "")
        finish_reason = response.get("finish_reason", "")

        if accumulated:
            content = accumulated + "\n" + content

        if finish_reason == "length":
            return False, content

        incomplete_patterns = [
            r'\.\.\.$',
            r'continua[rá]?$',
            r'e também$',
            r'além disso$',
        ]

        for pattern in incomplete_patterns:
            if re.search(pattern, content.strip(), re.IGNORECASE):
                return False, content

        return True, content

    def _calculate_confidence(self, chunks: List[ChunkWithScore]) -> float:
        """Calcula score de confianca baseado nos chunks usados"""
        if not chunks:
            return 0.0

        avg_score = sum(c.combined_score for c in chunks) / len(chunks)
        coverage = min(len(chunks) / 5, 1.0)

        return (
            avg_score * settings.confidence_score_weight
            + coverage * settings.confidence_coverage_weight
        )

    def _extract_sources(self, chunks: List[ChunkWithScore]) -> List[Dict[str, Any]]:
        """Extrai informacoes de fonte dos chunks"""
        sources = []

        for chunk_with_score in chunks:
            chunk = chunk_with_score.chunk
            source = {
                "chunk_id": chunk.id,
                "section": chunk.section,
                "relevance_score": round(chunk_with_score.combined_score, 3)
            }

            if chunk.candidate:
                source["candidate_name"] = chunk.candidate.full_name
                source["candidate_id"] = chunk.candidate.id

            sources.append(source)

        return sources

    async def query_with_refinement(
        self,
        db: Session,
        question: str,
        filters: Optional[Dict[str, Any]] = None,
        refinement_questions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Consulta com refinamento iterativo"""
        results = []

        main_result = await self.query(db, question, filters)
        results.append({
            "question": question,
            "result": main_result
        })

        if refinement_questions and main_result.status == QueryStatus.SUCCESS:
            for ref_question in refinement_questions[:3]:
                ref_result = await self.query(
                    db,
                    f"{ref_question} (Contexto: {question})",
                    filters,
                    max_retries=3
                )
                results.append({
                    "question": ref_question,
                    "result": ref_result
                })

        return {
            "primary_answer": main_result.answer,
            "primary_status": main_result.status.value,
            "all_results": [
                {
                    "question": r["question"],
                    "answer": r["result"].answer,
                    "status": r["result"].status.value,
                    "retries": r["result"].retries
                }
                for r in results
            ],
            "total_retries": sum(r["result"].retries for r in results),
            "sources": main_result.sources
        }

    async def analyze_candidate_for_job(
        self,
        db: Session,
        candidate_id: int,
        job_description: str,
        domain: Optional[str] = None
    ) -> QueryResult:
        """
        Analisa um candidato especifico para uma vaga

        Args:
            db: Sessao do banco
            candidate_id: ID do candidato
            job_description: Descricao da vaga
            domain: Dominio (production, logistics, quality, general)

        Returns:
            QueryResult com analise detalhada
        """
        question = f"""Analise o curriculo deste candidato para a seguinte vaga:

DESCRICAO DA VAGA:
{job_description}

Por favor, avalie:
1. Aderencia geral do candidato a vaga (0-100%)
2. Pontos fortes do candidato para esta vaga
3. Gaps ou pontos de atencao
4. Certificacoes e habilitacoes relevantes
5. Experiencia especifica que se encaixa
6. Recomendacao final (Recomendado / Parcialmente Recomendado / Nao Recomendado)"""

        return await self.query(
            db=db,
            question=question,
            filters={"candidate_id": candidate_id},
            domain=domain or self._detect_query_domain(job_description)
        )


# Instancia global
llm_query_service = LLMQueryService()
