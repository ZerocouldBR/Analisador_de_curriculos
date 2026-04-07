"""
API de integracao com LinkedIn

Endpoints:
- Extracao de perfil publico
- Busca de profissionais por criterios
- Enriquecimento de candidatos
- Historico de buscas
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.db.database import get_db
from app.schemas.candidate import (
    LinkedInProfile,
    ExternalEnrichmentResponse,
    CandidateResponse
)
from app.services.linkedin_service import LinkedInService
from app.services.candidate_service import CandidateService
from app.core.dependencies import require_permission, get_current_user
from app.db.models import User

router = APIRouter(prefix="/linkedin", tags=["linkedin"])


# ================================================================
# Schemas
# ================================================================

class ProfessionalSearchRequest(BaseModel):
    """Criterios de busca de profissionais"""
    title: Optional[str] = Field(None, description="Cargo desejado (ex: Operador CNC)")
    skills: Optional[List[str]] = Field(None, description="Lista de skills requeridas")
    location: Optional[str] = Field(None, description="Cidade ou estado")
    experience_years: Optional[int] = Field(None, ge=0, description="Anos minimos de experiencia")
    keywords: Optional[List[str]] = Field(None, description="Palavras-chave gerais")
    industry: Optional[str] = Field(None, description="Setor/industria")


class SearchResultResponse(BaseModel):
    search_id: int
    criteria: Dict[str, Any]
    results: List[Dict[str, Any]]
    total_found: int
    sources: Dict[str, int]
    note: str


# ================================================================
# Profile Extraction
# ================================================================

@router.post("/extract", response_model=Dict[str, Any])
async def extract_linkedin_profile(
    profile_url: str = Body(..., embed=True, description="URL do perfil do LinkedIn"),
    current_user: User = Depends(require_permission("linkedin.enrich"))
):
    """
    Extrai dados de um perfil publico do LinkedIn

    **Requer permissao:** linkedin.enrich
    """
    try:
        profile_data = await LinkedInService.extract_profile_data(profile_url)

        if not profile_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nao foi possivel extrair dados do perfil. Verifique a URL."
            )

        return profile_data

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar perfil: {str(e)}"
        )


# ================================================================
# Professional Search
# ================================================================

@router.post("/search", response_model=SearchResultResponse)
def search_professionals(
    criteria: ProfessionalSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("linkedin.enrich")),
):
    """
    Busca profissionais por criterios

    Busca na base interna de candidatos e em dados do LinkedIn ja coletados.
    Retorna candidatos ranqueados por aderencia aos criterios.

    **Criterios disponiveis:**
    - `title`: Cargo desejado
    - `skills`: Lista de habilidades
    - `location`: Cidade ou estado
    - `experience_years`: Anos de experiencia
    - `keywords`: Palavras-chave
    - `industry`: Setor

    **Requer permissao:** linkedin.enrich
    """
    try:
        criteria_dict = criteria.model_dump(exclude_none=True)

        if not criteria_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Informe ao menos um criterio de busca"
            )

        result = LinkedInService.search_professionals(
            db=db,
            user_id=current_user.id,
            criteria=criteria_dict,
        )

        return SearchResultResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na busca: {str(e)}"
        )


@router.get("/search/history")
def get_search_history(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtem historico de buscas de profissionais

    **Requer:** Autenticacao
    """
    return LinkedInService.get_search_history(db, current_user.id, limit)


@router.get("/search/{search_id}")
def get_search_results(
    search_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtem resultados de uma busca especifica

    **Requer:** Autenticacao
    """
    result = LinkedInService.get_search_results(db, search_id, current_user.id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Busca nao encontrada"
        )

    return result


# ================================================================
# Enrichment Endpoints
# ================================================================

@router.post("/candidates/{candidate_id}/enrich", response_model=ExternalEnrichmentResponse)
def enrich_candidate_with_linkedin(
    candidate_id: int,
    linkedin_data: LinkedInProfile,
    update_candidate: bool = Body(
        default=True,
        description="Se True, atualiza informacoes do candidato com dados do LinkedIn"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("linkedin.enrich"))
):
    """
    Enriquece um candidato com dados do LinkedIn

    **Requer permissao:** linkedin.enrich
    """
    candidate = CandidateService.get_candidate(db, candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidato {candidate_id} nao encontrado"
        )

    enrichment = LinkedInService.create_enrichment_from_linkedin(
        db, candidate_id, linkedin_data, user_id=current_user.id
    )

    if update_candidate:
        LinkedInService.update_candidate_from_linkedin(
            db, candidate_id, linkedin_data, user_id=current_user.id
        )

    return enrichment


@router.post("/candidates/{candidate_id}/manual", response_model=ExternalEnrichmentResponse)
def add_manual_linkedin_data(
    candidate_id: int,
    linkedin_data: Dict[str, Any] = Body(..., description="Dados do LinkedIn inseridos manualmente"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("linkedin.enrich"))
):
    """
    Adiciona dados do LinkedIn manualmente

    **Requer permissao:** linkedin.enrich
    """
    candidate = CandidateService.get_candidate(db, candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidato {candidate_id} nao encontrado"
        )

    if "profile_url" not in linkedin_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O campo 'profile_url' e obrigatorio"
        )

    enrichment = LinkedInService.manual_linkedin_input(
        db, candidate_id, linkedin_data, user_id=current_user.id
    )

    return enrichment


@router.get("/candidates/{candidate_id}/linkedin", response_model=ExternalEnrichmentResponse)
def get_candidate_linkedin_data(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("candidates.read"))
):
    """
    Obtem os dados do LinkedIn de um candidato

    **Requer permissao:** candidates.read
    """
    candidate = CandidateService.get_candidate(db, candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidato {candidate_id} nao encontrado"
        )

    linkedin_data = LinkedInService.get_candidate_linkedin_data(db, candidate_id)

    if not linkedin_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nenhum dado do LinkedIn encontrado para o candidato {candidate_id}"
        )

    return linkedin_data


@router.put("/candidates/{candidate_id}/sync-from-linkedin", response_model=CandidateResponse)
def sync_candidate_from_linkedin(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("linkedin.enrich"))
):
    """
    Sincroniza informacoes do candidato com dados do LinkedIn

    **Requer permissao:** linkedin.enrich
    """
    candidate = CandidateService.get_candidate(db, candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidato {candidate_id} nao encontrado"
        )

    linkedin_enrichment = LinkedInService.get_candidate_linkedin_data(db, candidate_id)
    if not linkedin_enrichment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nenhum dado do LinkedIn encontrado para sincronizar"
        )

    linkedin_profile = LinkedInProfile(**linkedin_enrichment.data_json)

    updated_candidate = LinkedInService.update_candidate_from_linkedin(
        db, candidate_id, linkedin_profile, user_id=current_user.id
    )

    return updated_candidate
