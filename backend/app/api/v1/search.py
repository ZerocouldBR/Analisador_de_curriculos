from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from app.db.database import get_db
from app.schemas.candidate import CandidateResponse
from app.services.embedding_service import embedding_service
from app.services.llm_query_service import llm_query_service, QueryStatus
from app.services.keyword_extraction_service import KeywordExtractionService
from app.core.dependencies import get_current_user, require_permission
from app.db.models import User, Chunk


router = APIRouter(prefix="/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Texto da busca")
    limit: int = Field(default=10, ge=1, le=100, description="Número máximo de resultados")
    threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Similaridade mínima")


class SearchResult(BaseModel):
    candidate_id: int
    candidate_name: str
    email: Optional[str]
    city: Optional[str]
    state: Optional[str]
    score: float
    highlight: str  # Trecho relevante do currículo


class HybridSearchRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Texto da busca")
    filters: Optional[dict] = Field(default=None, description="Filtros adicionais")
    limit: int = Field(default=10, ge=1, le=100)


@router.post("/semantic", response_model=List[SearchResult])
async def semantic_search(
    search_request: SearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Busca semântica usando embeddings vetoriais

    Encontra currículos semanticamente similares à query, mesmo que não contenham
    as palavras exatas.

    Exemplo:
    - Query: "desenvolvedor python experiente"
    - Pode encontrar: "programador sênior em Django com 5 anos de experiência"

    **Requer:** Autenticação
    """
    try:
        results = await embedding_service.semantic_search(
            db,
            search_request.query,
            search_request.limit,
            search_request.threshold
        )

        search_results = []

        for chunk, similarity in results:
            search_results.append(SearchResult(
                candidate_id=chunk.candidate_id,
                candidate_name=chunk.candidate.full_name,
                email=chunk.candidate.email,
                city=chunk.candidate.city,
                state=chunk.candidate.state,
                score=similarity,
                highlight=chunk.content[:200] + "..."
            ))

        return search_results

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na busca: {str(e)}"
        )


@router.post("/hybrid", response_model=List[SearchResult])
async def hybrid_search(
    search_request: HybridSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("search.advanced"))
):
    """
    Busca híbrida combinando múltiplas estratégias

    Combina:
    - **40%** Similaridade vetorial (semântica)
    - **30%** Busca full-text (palavras-chave)
    - **20%** Filtros (cidade, skills, experiência)
    - **10%** Experiência no domínio

    **Requer permissão:** search.advanced
    """
    try:
        results = await embedding_service.hybrid_search(
            db,
            search_request.query,
            search_request.filters,
            search_request.limit
        )

        search_results = []

        for candidate, score in results:
            # Encontrar chunk mais relevante para highlight
            from app.db.models import Chunk
            top_chunk = db.query(Chunk).filter(
                Chunk.candidate_id == candidate.id
            ).first()

            highlight = ""
            if top_chunk:
                highlight = top_chunk.content[:200] + "..."

            search_results.append(SearchResult(
                candidate_id=candidate.id,
                candidate_name=candidate.full_name,
                email=candidate.email,
                city=candidate.city,
                state=candidate.state,
                score=score,
                highlight=highlight
            ))

        return search_results

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na busca: {str(e)}"
        )


@router.get("/candidates/by-skill")
def search_by_skill(
    skill: str = Query(..., min_length=2, description="Skill para buscar"),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Busca candidatos por skill específica

    Busca full-text simples nos chunks de skills.

    **Requer:** Autenticação
    """
    from app.db.models import Chunk, Candidate
    from sqlalchemy import func

    results = db.query(
        Candidate.id,
        Candidate.full_name,
        Candidate.email,
        Candidate.city,
        Candidate.state
    ).join(
        Chunk, Chunk.candidate_id == Candidate.id
    ).filter(
        Chunk.section == "skills",
        func.lower(Chunk.content).contains(skill.lower())
    ).limit(limit).all()

    return [
        {
            "candidate_id": r.id,
            "candidate_name": r.full_name,
            "email": r.email,
            "city": r.city,
            "state": r.state
        }
        for r in results
    ]


# ============================================
# NOVOS ENDPOINTS: LLM Query com Retry
# ============================================

class LLMQueryRequest(BaseModel):
    """Requisição para consulta ao LLM"""
    question: str = Field(..., min_length=5, description="Pergunta sobre os currículos")
    candidate_id: Optional[int] = Field(None, description="ID do candidato específico (opcional)")
    filters: Optional[Dict[str, Any]] = Field(None, description="Filtros adicionais")
    max_retries: int = Field(default=5, ge=1, le=5, description="Máximo de tentativas (1-5)")
    include_sources: bool = Field(default=True, description="Incluir fontes na resposta")


class LLMQueryResponse(BaseModel):
    """Resposta da consulta ao LLM"""
    status: str
    answer: str
    chunks_used: int
    total_chunks_available: int
    tokens_used: int
    retries: int
    confidence_score: float
    sources: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None


class LLMRefinedQueryRequest(BaseModel):
    """Requisição para consulta com refinamento"""
    question: str = Field(..., min_length=5)
    refinement_questions: Optional[List[str]] = Field(
        None,
        max_length=3,
        description="Perguntas de follow-up (máx 3)"
    )
    candidate_id: Optional[int] = None
    filters: Optional[Dict[str, Any]] = None


@router.post("/llm/query", response_model=LLMQueryResponse)
async def llm_query(
    request: LLMQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("search.advanced"))
):
    """
    Consulta inteligente ao LLM sobre currículos

    Características:
    - **Busca semântica** para encontrar currículos relevantes
    - **Retry automático** quando atinge limite de caracteres da API
    - **Até 5 tentativas** com filtro progressivo de contexto
    - **Palavras-chave indexadas** para melhor localização

    O sistema automaticamente:
    1. Busca os chunks mais relevantes
    2. Envia para o LLM com contexto otimizado
    3. Se atingir limite de tokens, filtra e tenta novamente
    4. Retorna resposta mais completa possível

    **Requer permissão:** search.advanced
    """
    try:
        filters = request.filters or {}
        if request.candidate_id:
            filters["candidate_id"] = request.candidate_id

        result = await llm_query_service.query(
            db=db,
            question=request.question,
            filters=filters if filters else None,
            max_retries=request.max_retries,
            include_sources=request.include_sources
        )

        return LLMQueryResponse(
            status=result.status.value,
            answer=result.answer,
            chunks_used=result.chunks_used,
            total_chunks_available=result.total_chunks_available,
            tokens_used=result.tokens_used,
            retries=result.retries,
            confidence_score=result.confidence_score,
            sources=result.sources if request.include_sources else None,
            metadata=result.metadata
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na consulta LLM: {str(e)}"
        )


@router.post("/llm/query-refined")
async def llm_query_refined(
    request: LLMRefinedQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("search.advanced"))
):
    """
    Consulta ao LLM com refinamento iterativo

    Permite fazer perguntas de follow-up automaticamente
    para obter respostas mais completas e detalhadas.

    Exemplo:
    ```json
    {
        "question": "Quais candidatos têm experiência com Python?",
        "refinement_questions": [
            "Qual o nível de experiência de cada um?",
            "Algum tem certificações relacionadas?"
        ]
    }
    ```

    **Requer permissão:** search.advanced
    """
    try:
        filters = request.filters or {}
        if request.candidate_id:
            filters["candidate_id"] = request.candidate_id

        result = await llm_query_service.query_with_refinement(
            db=db,
            question=request.question,
            filters=filters if filters else None,
            refinement_questions=request.refinement_questions
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na consulta refinada: {str(e)}"
        )


# ============================================
# ENDPOINTS: Extração de Keywords
# ============================================

class KeywordExtractionRequest(BaseModel):
    """Requisição para extração de keywords"""
    text: str = Field(..., min_length=10, description="Texto para extrair keywords")


@router.post("/keywords/extract")
async def extract_keywords(
    request: KeywordExtractionRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Extrai palavras-chave estruturadas de um texto

    Retorna:
    - **keywords**: Lista de todas as palavras-chave
    - **technical_skills**: Skills técnicas (linguagens, frameworks)
    - **soft_skills**: Habilidades comportamentais
    - **tools_and_frameworks**: Ferramentas e frameworks
    - **domains**: Domínios de conhecimento
    - **tfidf_terms**: Termos com maior relevância TF-IDF
    - **ngrams**: N-gramas mais frequentes
    - **search_index**: Índice otimizado para busca LLM

    **Requer:** Autenticação
    """
    try:
        keywords = KeywordExtractionService.extract_keywords(request.text)
        return keywords

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na extração de keywords: {str(e)}"
        )


@router.get("/keywords/candidate/{candidate_id}")
async def get_candidate_keywords(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retorna as palavras-chave indexadas de um candidato

    Obtém keywords do chunk de índice ou extrai do texto completo.

    **Requer:** Autenticação
    """
    try:
        # Buscar chunk de keyword_index
        keyword_chunk = db.query(Chunk).filter(
            Chunk.candidate_id == candidate_id,
            Chunk.section == "keyword_index"
        ).first()

        if keyword_chunk and keyword_chunk.meta_json:
            return {
                "candidate_id": candidate_id,
                "keywords": keyword_chunk.meta_json,
                "search_index": keyword_chunk.content
            }

        # Se não tem chunk de keywords, buscar do full_text
        full_text_chunk = db.query(Chunk).filter(
            Chunk.candidate_id == candidate_id,
            Chunk.section == "full_text"
        ).first()

        if not full_text_chunk:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Candidato {candidate_id} não encontrado ou sem currículo"
            )

        # Extrair keywords do texto
        keywords = KeywordExtractionService.extract_keywords(full_text_chunk.content)

        return {
            "candidate_id": candidate_id,
            "keywords": keywords,
            "note": "Keywords extraídas em tempo real (não indexadas)"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao obter keywords: {str(e)}"
        )


@router.post("/candidates/{candidate_id}/reindex")
async def reindex_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("candidates.write"))
):
    """
    Reindexa as palavras-chave de um candidato

    Atualiza os metadados de todos os chunks com
    keywords e índices atualizados.

    **Requer permissão:** candidates.write
    """
    try:
        # Buscar chunks do candidato
        chunks = db.query(Chunk).filter(
            Chunk.candidate_id == candidate_id
        ).all()

        if not chunks:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nenhum chunk encontrado para candidato {candidate_id}"
            )

        # Obter texto completo
        full_text_chunk = next(
            (c for c in chunks if c.section == "full_text"),
            None
        )

        if not full_text_chunk:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Candidato não possui chunk de texto completo"
            )

        # Extrair keywords do documento completo
        document_keywords = KeywordExtractionService.extract_keywords(
            full_text_chunk.content
        )

        # Atualizar ou criar chunk de keyword_index
        keyword_chunk = next(
            (c for c in chunks if c.section == "keyword_index"),
            None
        )

        if keyword_chunk:
            keyword_chunk.content = document_keywords["search_index"]
            keyword_chunk.meta_json = {
                "keywords": document_keywords["keywords"][:50],
                "technical_skills": document_keywords["technical_skills"],
                "soft_skills": document_keywords["soft_skills"],
                "relevance_scores": document_keywords["relevance_scores"]
            }
        else:
            from app.db.models import Document
            doc = db.query(Document).filter(
                Document.candidate_id == candidate_id
            ).first()

            if doc:
                new_chunk = Chunk(
                    document_id=doc.id,
                    candidate_id=candidate_id,
                    section="keyword_index",
                    content=document_keywords["search_index"],
                    meta_json={
                        "keywords": document_keywords["keywords"][:50],
                        "technical_skills": document_keywords["technical_skills"],
                        "soft_skills": document_keywords["soft_skills"],
                        "relevance_scores": document_keywords["relevance_scores"]
                    }
                )
                db.add(new_chunk)

        # Atualizar metadados dos outros chunks
        total_chunks = len([c for c in chunks if c.section != "keyword_index"])
        for i, chunk in enumerate(chunks):
            if chunk.section == "keyword_index":
                continue

            chunk_meta = KeywordExtractionService.create_chunk_metadata(
                section=chunk.section,
                content=chunk.content,
                keywords=document_keywords,
                chunk_index=i,
                total_chunks=total_chunks
            )

            # Merge com metadados existentes
            if chunk.meta_json:
                chunk.meta_json.update(chunk_meta)
            else:
                chunk.meta_json = chunk_meta

        db.commit()

        return {
            "status": "success",
            "candidate_id": candidate_id,
            "chunks_updated": len(chunks),
            "keywords_extracted": len(document_keywords["keywords"]),
            "technical_skills": document_keywords["technical_skills"],
            "soft_skills": document_keywords["soft_skills"]
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao reindexar: {str(e)}"
        )
