from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field

from app.db.database import get_db
from app.schemas.candidate import CandidateResponse
from app.services.embedding_service import embedding_service
from app.core.dependencies import get_current_user, require_permission
from app.db.models import User


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
