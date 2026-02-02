"""
Serviço de consulta ao LLM com retry inteligente

Implementa:
- Consulta iterativa à API do LLM
- Retry automático com filtro de contexto quando atinge limite de caracteres
- Até 5 tentativas para obter resposta completa
- Ranqueamento e seleção inteligente de chunks relevantes
"""
import asyncio
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import openai
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.models import Chunk, Candidate, Embedding
from app.core.config import settings
from app.services.keyword_extraction_service import KeywordExtractionService


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
    """Chunk com score de relevância"""
    chunk: Chunk
    semantic_score: float
    keyword_score: float
    combined_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class LLMQueryService:
    """
    Serviço para consultas ao LLM com retry inteligente

    Características:
    - Busca semântica de chunks relevantes
    - Ranqueamento por relevância
    - Retry automático com filtro progressivo
    - Máximo de 5 tentativas por consulta
    """

    # Configurações padrão
    DEFAULT_MAX_RETRIES = 5
    DEFAULT_MAX_TOKENS = 4096
    DEFAULT_TEMPERATURE = 0.7
    DEFAULT_MODEL = "gpt-4-turbo-preview"

    # Limites de caracteres por tentativa (progressivamente menores)
    CHARACTER_LIMITS = [
        32000,  # 1ª tentativa: contexto completo
        24000,  # 2ª tentativa: contexto reduzido
        16000,  # 3ª tentativa: contexto moderado
        10000,  # 4ª tentativa: contexto mínimo
        6000,   # 5ª tentativa: apenas essencial
    ]

    # Número de chunks por tentativa (progressivamente menos)
    CHUNKS_PER_RETRY = [15, 12, 8, 5, 3]

    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializa o serviço

        Args:
            api_key: Chave da API OpenAI (usa config se não fornecida)
        """
        self.api_key = api_key or getattr(settings, 'openai_api_key', None)
        self.embedding_model = getattr(settings, 'embedding_model', 'text-embedding-3-small')
        self.chat_model = getattr(settings, 'chat_model', self.DEFAULT_MODEL)

        if self.api_key:
            openai.api_key = self.api_key

    async def query(
        self,
        db: Session,
        question: str,
        filters: Optional[Dict[str, Any]] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        include_sources: bool = True
    ) -> QueryResult:
        """
        Executa consulta ao LLM com retry inteligente

        Args:
            db: Sessão do banco de dados
            question: Pergunta do usuário
            filters: Filtros opcionais (candidate_id, skills, etc.)
            max_retries: Número máximo de tentativas (padrão: 5)
            include_sources: Incluir fontes na resposta

        Returns:
            QueryResult com resposta e metadados
        """
        if not self.api_key:
            return QueryResult(
                status=QueryStatus.ERROR,
                answer="API key do OpenAI não configurada",
                chunks_used=0,
                total_chunks_available=0,
                tokens_used=0,
                retries=0,
                confidence_score=0.0
            )

        # Buscar chunks relevantes
        all_chunks = await self._search_relevant_chunks(db, question, filters)
        total_available = len(all_chunks)

        if not all_chunks:
            return QueryResult(
                status=QueryStatus.SUCCESS,
                answer="Não encontrei currículos relevantes para sua pergunta.",
                chunks_used=0,
                total_chunks_available=0,
                tokens_used=0,
                retries=0,
                confidence_score=0.0
            )

        # Tentar consultar com retry progressivo
        retries = 0
        last_error = None
        accumulated_answer = ""

        while retries < min(max_retries, len(self.CHARACTER_LIMITS)):
            try:
                # Selecionar chunks para esta tentativa
                max_chunks = self.CHUNKS_PER_RETRY[retries]
                char_limit = self.CHARACTER_LIMITS[retries]

                selected_chunks = self._select_chunks_for_attempt(
                    all_chunks, max_chunks, char_limit
                )

                # Construir contexto
                context = self._build_context(selected_chunks, char_limit)

                # Construir prompt
                prompt = self._build_prompt(
                    question, context, retries, accumulated_answer
                )

                # Chamar LLM
                response = await self._call_llm(prompt, retries)

                # Verificar se resposta está completa
                is_complete, answer = self._check_response_completeness(
                    response, accumulated_answer
                )

                if is_complete:
                    # Resposta completa obtida
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
                            "model": self.chat_model
                        }
                    )

                # Resposta parcial - acumular e continuar
                accumulated_answer = answer
                retries += 1

            except openai.error.InvalidRequestError as e:
                # Token limit exceeded - tentar com menos contexto
                error_msg = str(e)
                if "maximum context length" in error_msg or "token" in error_msg.lower():
                    retries += 1
                    last_error = e
                    continue
                else:
                    return QueryResult(
                        status=QueryStatus.ERROR,
                        answer=f"Erro na API: {error_msg}",
                        chunks_used=0,
                        total_chunks_available=total_available,
                        tokens_used=0,
                        retries=retries + 1,
                        confidence_score=0.0
                    )

            except Exception as e:
                last_error = e
                retries += 1

        # Máximo de retries atingido
        if accumulated_answer:
            return QueryResult(
                status=QueryStatus.PARTIAL,
                answer=accumulated_answer,
                chunks_used=len(selected_chunks) if selected_chunks else 0,
                total_chunks_available=total_available,
                tokens_used=0,
                retries=retries,
                confidence_score=self._calculate_confidence(selected_chunks) * 0.7,
                metadata={"warning": "Resposta pode estar incompleta após máximo de tentativas"}
            )

        return QueryResult(
            status=QueryStatus.MAX_RETRIES_REACHED,
            answer=f"Não foi possível obter resposta após {retries} tentativas. Erro: {last_error}",
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
        """
        Busca chunks relevantes usando busca híbrida

        Combina:
        - Similaridade semântica (embeddings)
        - Match de palavras-chave
        - Filtros opcionais
        """
        # Gerar embedding da query
        query_embedding = await self._generate_embedding(query)

        # Extrair keywords da query
        query_keywords = KeywordExtractionService.extract_keywords(query)
        keyword_terms = query_keywords.get("keywords", [])

        # Construir query SQL híbrida
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
                WHERE 1 - (e.vector <=> :query_vector::vector) >= 0.3
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

        params = {"query_vector": str(query_embedding)}

        # Aplicar filtros se existirem
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

            # Calcular score de keywords
            keyword_score = self._calculate_keyword_score(chunk.content, keyword_terms)

            # Score combinado
            combined_score = (
                row.semantic_score * 0.6 +
                keyword_score * 0.4
            )

            chunks_with_scores.append(ChunkWithScore(
                chunk=chunk,
                semantic_score=row.semantic_score,
                keyword_score=keyword_score,
                combined_score=combined_score,
                metadata=row.meta_json or {}
            ))

        # Ordenar por score combinado
        chunks_with_scores.sort(key=lambda x: x.combined_score, reverse=True)

        return chunks_with_scores

    async def _generate_embedding(self, text: str) -> List[float]:
        """Gera embedding para um texto"""
        if len(text) > 32000:
            text = text[:32000]

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
        """
        Seleciona chunks para uma tentativa específica

        Prioriza:
        1. Chunks com maior score combinado
        2. Variedade de seções (não repetir mesma seção demais)
        3. Respeitar limite de caracteres
        """
        selected = []
        total_chars = 0
        section_counts = {}

        for chunk in chunks:
            if len(selected) >= max_chunks:
                break

            chunk_chars = len(chunk.chunk.content)

            # Verificar limite de caracteres
            if total_chars + chunk_chars > char_limit:
                # Se já temos alguns chunks, parar
                if selected:
                    break
                # Senão, truncar este chunk
                chunk_chars = char_limit - total_chars

            # Limitar repetição de seções
            section = chunk.chunk.section
            if section_counts.get(section, 0) >= 3:
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
        """Constrói contexto a partir dos chunks selecionados"""
        context_parts = []
        total_chars = 0

        for i, chunk_with_score in enumerate(chunks):
            chunk = chunk_with_score.chunk

            # Obter informações do candidato
            candidate_info = ""
            if chunk.candidate:
                candidate_info = f"Candidato: {chunk.candidate.full_name or 'N/A'}"
                if chunk.candidate.email:
                    candidate_info += f" | Email: {chunk.candidate.email}"

            # Construir bloco do chunk
            chunk_header = f"[CHUNK {i+1} - Seção: {chunk.section.upper()}]"
            if candidate_info:
                chunk_header += f"\n{candidate_info}"

            # Adicionar índice de keywords se disponível no metadata
            meta = chunk_with_score.metadata or {}
            if meta.get("search_index"):
                chunk_header += f"\n{meta['search_index'][:500]}"

            content = chunk.content

            # Truncar se necessário
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
        accumulated_answer: str
    ) -> List[Dict[str, str]]:
        """Constrói o prompt para o LLM"""
        system_prompt = """Você é um assistente especializado em análise de currículos para RH.

Suas responsabilidades:
1. Analisar currículos e responder perguntas sobre candidatos
2. Identificar habilidades, experiências e qualificações relevantes
3. Comparar candidatos quando solicitado
4. Fornecer respostas objetivas e baseadas nos dados disponíveis

Diretrizes:
- Baseie suas respostas APENAS no contexto fornecido
- Se a informação não estiver disponível, informe claramente
- Use os índices de palavras-chave para localizar informações rapidamente
- Estruture respostas longas com tópicos ou listas
- Cite a fonte (nome do candidato, seção) quando relevante"""

        user_prompt = f"""CONTEXTO DOS CURRÍCULOS:
{context}

PERGUNTA: {question}"""

        # Se é um retry com resposta acumulada
        if retry_number > 0 and accumulated_answer:
            user_prompt += f"""

NOTA: Esta é uma continuação. Resposta anterior (pode estar incompleta):
{accumulated_answer}

Por favor, complete ou refine a resposta se necessário."""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

    async def _call_llm(
        self,
        messages: List[Dict[str, str]],
        retry_number: int
    ) -> Dict[str, Any]:
        """Chama o LLM com os parâmetros apropriados"""
        # Ajustar temperatura baseado no retry
        temperature = max(0.3, self.DEFAULT_TEMPERATURE - (retry_number * 0.1))

        # Ajustar max_tokens baseado no retry (menos tokens = respostas mais concisas)
        max_tokens = max(1000, self.DEFAULT_MAX_TOKENS - (retry_number * 500))

        response = await openai.ChatCompletion.acreate(
            model=self.chat_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

        return {
            "content": response.choices[0].message.content,
            "finish_reason": response.choices[0].finish_reason,
            "usage": dict(response.usage)
        }

    def _check_response_completeness(
        self,
        response: Dict[str, Any],
        accumulated: str
    ) -> Tuple[bool, str]:
        """
        Verifica se a resposta está completa

        Returns:
            Tuple (is_complete, full_answer)
        """
        content = response.get("content", "")
        finish_reason = response.get("finish_reason", "")

        # Combinar com resposta acumulada se existir
        if accumulated:
            content = accumulated + "\n" + content

        # Verificar se foi cortado por limite de tokens
        if finish_reason == "length":
            return False, content

        # Verificar padrões que indicam resposta incompleta
        incomplete_patterns = [
            r'\.\.\.$',  # Termina com ...
            r'continua[rá]?$',  # Termina com "continua"
            r'e também$',  # Frase incompleta
            r'além disso$',  # Frase incompleta
        ]

        for pattern in incomplete_patterns:
            if re.search(pattern, content.strip(), re.IGNORECASE):
                return False, content

        return True, content

    def _calculate_confidence(self, chunks: List[ChunkWithScore]) -> float:
        """Calcula score de confiança baseado nos chunks usados"""
        if not chunks:
            return 0.0

        avg_score = sum(c.combined_score for c in chunks) / len(chunks)
        coverage = min(len(chunks) / 5, 1.0)  # Ideal: 5+ chunks

        return (avg_score * 0.7 + coverage * 0.3)

    def _extract_sources(self, chunks: List[ChunkWithScore]) -> List[Dict[str, Any]]:
        """Extrai informações de fonte dos chunks"""
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
        """
        Consulta com refinamento iterativo

        Permite fazer perguntas de follow-up automaticamente
        para obter respostas mais completas
        """
        results = []

        # Primeira consulta
        main_result = await self.query(db, question, filters)
        results.append({
            "question": question,
            "result": main_result
        })

        # Se há perguntas de refinamento
        if refinement_questions and main_result.status == QueryStatus.SUCCESS:
            for ref_question in refinement_questions[:3]:  # Max 3 refinamentos
                ref_result = await self.query(
                    db,
                    f"{ref_question} (Contexto: {question})",
                    filters,
                    max_retries=3  # Menos retries para refinamentos
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


# Instância global
llm_query_service = LLMQueryService()
