from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from app.db.database import get_db
from app.schemas.candidate import CandidateResponse
from app.services.embedding_service import embedding_service
from app.services.llm_query_service import llm_query_service, QueryStatus
from app.services.keyword_extraction_service import KeywordExtractionService
from app.services.job_matching_service import JobMatchingService, JobCategory
from app.core.dependencies import get_current_user, require_permission
from app.core.config import settings
from app.db.models import User, Chunk


router = APIRouter(prefix="/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Texto da busca")
    limit: int = Field(default=10, ge=1, le=100, description="Numero maximo de resultados")
    threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Similaridade minima (padrao: configuracao do sistema)")


class SearchResult(BaseModel):
    candidate_id: int
    candidate_name: str
    email: Optional[str]
    city: Optional[str]
    state: Optional[str]
    score: float
    highlight: str


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
    Busca semantica usando embeddings vetoriais

    Encontra curriculos semanticamente similares a query, mesmo que nao contenham
    as palavras exatas.

    **Requer:** Autenticacao
    """
    try:
        threshold = search_request.threshold if search_request.threshold is not None else settings.vector_search_threshold
        results = await embedding_service.semantic_search(
            db,
            search_request.query,
            search_request.limit,
            threshold
        )

        search_results = []
        company_id = current_user.company_id if settings.multi_tenant_enabled and not current_user.is_superuser else None

        for chunk, similarity in results:
            # Filtrar por empresa do usuario (multi-tenant)
            if company_id and chunk.candidate and chunk.candidate.company_id != company_id:
                continue

            search_results.append(SearchResult(
                candidate_id=chunk.candidate_id,
                candidate_name=chunk.candidate.full_name,
                email=chunk.candidate.email,
                city=chunk.candidate.city,
                state=chunk.candidate.state,
                score=similarity,
                highlight=chunk.content[:settings.search_result_highlight_chars] + "..."
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
    Busca hibrida combinando multiplas estrategias

    Combina:
    - **40%** Similaridade vetorial (semantica)
    - **30%** Busca full-text (palavras-chave)
    - **20%** Filtros (cidade, skills, experiencia)
    - **10%** Experiencia no dominio

    **Requer permissao:** search.advanced
    """
    try:
        results = await embedding_service.hybrid_search(
            db,
            search_request.query,
            search_request.filters,
            search_request.limit
        )

        search_results = []
        company_id = current_user.company_id if settings.multi_tenant_enabled and not current_user.is_superuser else None

        for candidate, score in results:
            # Filtrar por empresa (multi-tenant)
            if company_id and candidate.company_id != company_id:
                continue

            top_chunk = db.query(Chunk).filter(
                Chunk.candidate_id == candidate.id
            ).first()

            highlight = ""
            if top_chunk:
                highlight = top_chunk.content[:settings.search_result_highlight_chars] + "..."

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
    Busca candidatos por skill especifica

    **Requer:** Autenticacao
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
# LLM Query com Retry
# ============================================

class LLMQueryRequest(BaseModel):
    question: str = Field(..., min_length=5, description="Pergunta sobre os curriculos")
    candidate_id: Optional[int] = Field(None, description="ID do candidato especifico (opcional)")
    filters: Optional[Dict[str, Any]] = Field(None, description="Filtros adicionais")
    max_retries: int = Field(default=5, ge=1, le=5, description="Maximo de tentativas (1-5)")
    include_sources: bool = Field(default=True, description="Incluir fontes na resposta")
    domain: Optional[str] = Field(
        None,
        description="Dominio especializado: production, logistics, quality, general (auto-detectado se nao informado)"
    )


class LLMQueryResponse(BaseModel):
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
    question: str = Field(..., min_length=5)
    refinement_questions: Optional[List[str]] = Field(
        None,
        max_length=3,
        description="Perguntas de follow-up (max 3)"
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
    Consulta inteligente ao LLM sobre curriculos

    O sistema detecta automaticamente o dominio da pergunta (producao, logistica,
    qualidade ou geral) e usa prompts especializados.

    **Dominios disponiveis:**
    - `production` - Producao industrial, manufatura, PCP, manutencao
    - `logistics` - Logistica, armazem, supply chain, transporte
    - `quality` - Qualidade, metrologia, ISO, Lean Six Sigma
    - `general` - Geral (auto-detectado)

    **Requer permissao:** search.advanced
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
            include_sources=request.include_sources,
            domain=request.domain
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

    **Requer permissao:** search.advanced
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
# LLM: Analise Candidato x Vaga
# ============================================

class CandidateJobAnalysisRequest(BaseModel):
    candidate_id: int = Field(..., description="ID do candidato")
    job_description: str = Field(..., min_length=10, description="Descricao da vaga")
    domain: Optional[str] = Field(
        None, description="Dominio: production, logistics, quality, general"
    )


@router.post("/llm/analyze-fit")
async def analyze_candidate_job_fit(
    request: CandidateJobAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("search.advanced"))
):
    """
    Analisa a aderencia de um candidato a uma vaga usando LLM

    Retorna analise detalhada com:
    - Aderencia geral (0-100%)
    - Pontos fortes
    - Gaps
    - Certificacoes relevantes
    - Recomendacao final

    **Requer permissao:** search.advanced
    """
    try:
        result = await llm_query_service.analyze_candidate_for_job(
            db=db,
            candidate_id=request.candidate_id,
            job_description=request.job_description,
            domain=request.domain
        )

        return {
            "status": result.status.value,
            "analysis": result.answer,
            "confidence": result.confidence_score,
            "chunks_used": result.chunks_used,
            "domain": result.metadata.get("domain", "general"),
            "sources": result.sources
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na analise: {str(e)}"
        )


# ============================================
# Job Matching - Producao e Logistica
# ============================================

class JobMatchRequest(BaseModel):
    profile_key: Optional[str] = Field(
        None,
        description="Chave do perfil pre-definido (ex: operador_producao, auxiliar_logistica)"
    )
    custom_profile: Optional[Dict[str, Any]] = Field(
        None,
        description="Perfil customizado com title, category, description, requirements"
    )
    limit: int = Field(default=20, ge=1, le=100)
    min_score: float = Field(default=30.0, ge=0, le=100, description="Score minimo (0-100)")


class JobMatchResult(BaseModel):
    candidate_id: int
    candidate_name: str
    total_score: float
    requirement_scores: Dict[str, float]
    matched_keywords: List[str]
    missing_requirements: List[str]
    strengths: List[str]
    gaps: List[str]
    profile_type: str
    metadata: Optional[Dict[str, Any]] = None


@router.get("/job-profiles")
async def list_job_profiles(
    current_user: User = Depends(get_current_user)
):
    """
    Lista perfis de vagas pre-definidos disponiveis

    Perfis disponiveis para producao, logistica, qualidade e manutencao.

    **Requer:** Autenticacao
    """
    profiles = JobMatchingService.get_preset_profiles()

    return {
        "profiles": {
            key: {
                "title": profile.title,
                "category": profile.category.value,
                "description": profile.description,
                "requirements_count": len(profile.requirements),
                "min_experience_years": profile.min_experience_years,
                "requires_cnh": profile.requires_cnh,
            }
            for key, profile in profiles.items()
        },
        "categories": [c.value for c in JobCategory]
    }


@router.post("/job-match", response_model=List[JobMatchResult])
async def match_candidates_to_job(
    request: JobMatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("search.advanced"))
):
    """
    Busca candidatos que se enquadram em um perfil de vaga

    Pode usar perfis pre-definidos ou customizados.

    **Perfis pre-definidos:**
    - `operador_producao` - Operador de Producao
    - `lider_producao` - Lider de Producao
    - `operador_empilhadeira` - Operador de Empilhadeira
    - `auxiliar_logistica` - Auxiliar de Logistica
    - `analista_logistica` - Analista de Logistica
    - `inspetor_qualidade` - Inspetor de Qualidade
    - `mecanico_manutencao` - Mecanico de Manutencao
    - `analista_pcp` - Analista de PCP

    **Requer permissao:** search.advanced
    """
    try:
        # Obter perfil
        if request.profile_key:
            profile = JobMatchingService.get_profile(request.profile_key)
            if not profile:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Perfil '{request.profile_key}' nao encontrado. "
                           f"Use GET /search/job-profiles para ver perfis disponiveis."
                )
        elif request.custom_profile:
            profile = JobMatchingService.create_custom_profile(**request.custom_profile)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Informe profile_key ou custom_profile"
            )

        # Executar matching
        matches = JobMatchingService.match_candidates(
            db=db,
            job_profile=profile,
            limit=request.limit,
            min_score=request.min_score
        )

        return [
            JobMatchResult(
                candidate_id=m.candidate_id,
                candidate_name=m.candidate_name,
                total_score=m.total_score,
                requirement_scores=m.requirement_scores,
                matched_keywords=m.matched_keywords,
                missing_requirements=m.missing_requirements,
                strengths=m.strengths,
                gaps=m.gaps,
                profile_type=m.profile_type,
                metadata=m.metadata
            )
            for m in matches
        ]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro no matching: {str(e)}"
        )


@router.get("/job-match/candidate/{candidate_id}/suggestions")
async def suggest_jobs_for_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Sugere vagas para um candidato baseado em seu perfil

    Avalia o curriculo contra todos os perfis pre-definidos e retorna
    as melhores correspondencias.

    **Requer:** Autenticacao
    """
    try:
        suggestions = JobMatchingService.suggest_jobs_for_candidate(db, candidate_id)

        if not suggestions:
            return {
                "candidate_id": candidate_id,
                "suggestions": [],
                "message": "Nenhuma sugestao encontrada. Verifique se o candidato possui curriculo processado."
            }

        return {
            "candidate_id": candidate_id,
            "suggestions": suggestions,
            "total": len(suggestions)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao sugerir vagas: {str(e)}"
        )


# ============================================
# Extracao de Keywords
# ============================================

class KeywordExtractionRequest(BaseModel):
    text: str = Field(..., min_length=10, description="Texto para extrair keywords")


@router.post("/keywords/extract")
async def extract_keywords(
    request: KeywordExtractionRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Extrai palavras-chave estruturadas de um texto

    Retorna keywords categorizadas incluindo:
    - Skills de TI, producao, logistica e qualidade
    - Certificacoes (NRs, ISO, Lean)
    - Sistemas ERP
    - Habilitacoes
    - Perfil do candidato (production, logistics, it, quality, general)

    **Requer:** Autenticacao
    """
    try:
        keywords = KeywordExtractionService.extract_keywords(request.text)
        return keywords

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na extracao de keywords: {str(e)}"
        )


@router.get("/keywords/candidate/{candidate_id}")
async def get_candidate_keywords(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retorna as palavras-chave indexadas de um candidato

    **Requer:** Autenticacao
    """
    try:
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

        full_text_chunk = db.query(Chunk).filter(
            Chunk.candidate_id == candidate_id,
            Chunk.section == "full_text"
        ).first()

        if not full_text_chunk:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Candidato {candidate_id} nao encontrado ou sem curriculo"
            )

        keywords = KeywordExtractionService.extract_keywords(full_text_chunk.content)

        return {
            "candidate_id": candidate_id,
            "keywords": keywords,
            "note": "Keywords extraidas em tempo real (nao indexadas)"
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
    current_user: User = Depends(require_permission("candidates.update"))
):
    """
    Reindexa as palavras-chave de um candidato

    **Requer permissao:** candidates.update
    """
    try:
        chunks = db.query(Chunk).filter(
            Chunk.candidate_id == candidate_id
        ).all()

        if not chunks:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nenhum chunk encontrado para candidato {candidate_id}"
            )

        full_text_chunk = next(
            (c for c in chunks if c.section == "full_text"),
            None
        )

        if not full_text_chunk:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Candidato nao possui chunk de texto completo"
            )

        document_keywords = KeywordExtractionService.extract_keywords(
            full_text_chunk.content
        )

        keyword_chunk = next(
            (c for c in chunks if c.section == "keyword_index"),
            None
        )

        if keyword_chunk:
            keyword_chunk.content = document_keywords["search_index"]
            keyword_chunk.meta_json = {
                "keywords": document_keywords["keywords"][:settings.keyword_max_results],
                "technical_skills": document_keywords["technical_skills"],
                "soft_skills": document_keywords["soft_skills"],
                "production_skills": document_keywords.get("production_skills", []),
                "logistics_skills": document_keywords.get("logistics_skills", []),
                "quality_skills": document_keywords.get("quality_skills", []),
                "safety_certifications": document_keywords.get("safety_certifications", []),
                "maintenance_skills": document_keywords.get("maintenance_skills", []),
                "licenses": document_keywords.get("licenses", []),
                "erp_systems": document_keywords.get("erp_systems", []),
                "improvement_methods": document_keywords.get("improvement_methods", []),
                "industry_sectors": document_keywords.get("industry_sectors", []),
                "candidate_profile_type": document_keywords.get("candidate_profile_type", "general"),
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
                        "keywords": document_keywords["keywords"][:settings.keyword_max_results],
                        "technical_skills": document_keywords["technical_skills"],
                        "soft_skills": document_keywords["soft_skills"],
                        "production_skills": document_keywords.get("production_skills", []),
                        "logistics_skills": document_keywords.get("logistics_skills", []),
                        "quality_skills": document_keywords.get("quality_skills", []),
                        "safety_certifications": document_keywords.get("safety_certifications", []),
                        "candidate_profile_type": document_keywords.get("candidate_profile_type", "general"),
                        "relevance_scores": document_keywords["relevance_scores"]
                    }
                )
                db.add(new_chunk)

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
            "profile_type": document_keywords.get("candidate_profile_type", "general"),
            "technical_skills": document_keywords["technical_skills"],
            "soft_skills": document_keywords["soft_skills"],
            "production_skills": document_keywords.get("production_skills", []),
            "logistics_skills": document_keywords.get("logistics_skills", []),
            "quality_skills": document_keywords.get("quality_skills", []),
            "safety_certifications": document_keywords.get("safety_certifications", []),
            "relevance_scores": document_keywords.get("relevance_scores", {})
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao reindexar: {str(e)}"
        )
