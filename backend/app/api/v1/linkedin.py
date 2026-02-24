from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.db.database import get_db
from app.schemas.candidate import (
    LinkedInProfile,
    ExternalEnrichmentResponse,
    CandidateResponse
)
from app.services.linkedin_service import LinkedInService
from app.services.candidate_service import CandidateService
from app.core.dependencies import require_permission
from app.db.models import User

router = APIRouter(prefix="/linkedin", tags=["linkedin"])


@router.post("/extract", response_model=Dict[str, Any])
async def extract_linkedin_profile(
    profile_url: str = Body(..., embed=True, description="URL do perfil do LinkedIn"),
    current_user: User = Depends(require_permission("linkedin.enrich"))
):
    """
    Extrai dados de um perfil público do LinkedIn

    IMPORTANTE: Esta é uma funcionalidade de demonstração.
    Em produção, você deve:
    - Usar a API oficial do LinkedIn
    - Ou serviços terceirizados autorizados
    - Garantir conformidade com termos de serviço e LGPD

    **Requer permissão:** linkedin.enrich
    """
    try:
        profile_data = await LinkedInService.extract_profile_data(profile_url)

        if not profile_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Não foi possível extrair dados do perfil. Verifique a URL."
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


@router.post("/candidates/{candidate_id}/enrich", response_model=ExternalEnrichmentResponse)
def enrich_candidate_with_linkedin(
    candidate_id: int,
    linkedin_data: LinkedInProfile,
    update_candidate: bool = Body(
        default=True,
        description="Se True, atualiza informações do candidato com dados do LinkedIn"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("linkedin.enrich"))
):
    """
    Enriquece um candidato com dados do LinkedIn

    - Armazena os dados do LinkedIn como enriquecimento externo
    - Opcionalmente atualiza informações do candidato (nome, localização)

    **Requer permissão:** linkedin.enrich
    """
    # Verificar se candidato existe
    candidate = CandidateService.get_candidate(db, candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidato {candidate_id} não encontrado"
        )

    # Criar registro de enriquecimento
    enrichment = LinkedInService.create_enrichment_from_linkedin(
        db,
        candidate_id,
        linkedin_data,
        user_id=current_user.id
    )

    # Atualizar dados do candidato se solicitado
    if update_candidate:
        LinkedInService.update_candidate_from_linkedin(
            db,
            candidate_id,
            linkedin_data,
            user_id=current_user.id
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
    Adiciona dados do LinkedIn manualmente para um candidato

    Útil quando:
    - A extração automática não está disponível
    - Você já possui os dados do LinkedIn
    - Precisa inserir informações específicas

    **Requer permissão:** linkedin.enrich
    """
    # Verificar se candidato existe
    candidate = CandidateService.get_candidate(db, candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidato {candidate_id} não encontrado"
        )

    # Validar que pelo menos a URL do perfil está presente
    if "profile_url" not in linkedin_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O campo 'profile_url' é obrigatório"
        )

    enrichment = LinkedInService.manual_linkedin_input(
        db,
        candidate_id,
        linkedin_data,
        user_id=current_user.id
    )

    return enrichment


@router.get("/candidates/{candidate_id}/linkedin", response_model=ExternalEnrichmentResponse)
def get_candidate_linkedin_data(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("candidates.read"))
):
    """
    Obtém os dados do LinkedIn de um candidato

    **Requer permissão:** candidates.read
    """
    # Verificar se candidato existe
    candidate = CandidateService.get_candidate(db, candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidato {candidate_id} não encontrado"
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
    Sincroniza informações do candidato com dados do LinkedIn já armazenados

    Atualiza nome, localização e outras informações baseadas nos dados
    do LinkedIn previamente coletados.

    **Requer permissão:** linkedin.enrich
    """
    # Verificar se candidato existe
    candidate = CandidateService.get_candidate(db, candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidato {candidate_id} não encontrado"
        )

    # Obter dados do LinkedIn
    linkedin_enrichment = LinkedInService.get_candidate_linkedin_data(db, candidate_id)
    if not linkedin_enrichment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nenhum dado do LinkedIn encontrado para sincronizar"
        )

    # Converter para LinkedInProfile
    linkedin_profile = LinkedInProfile(**linkedin_enrichment.data_json)

    # Atualizar candidato
    updated_candidate = LinkedInService.update_candidate_from_linkedin(
        db,
        candidate_id,
        linkedin_profile,
        user_id=current_user.id
    )

    return updated_candidate
