from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Any, Dict
from pydantic import BaseModel
import mimetypes

from app.db.database import get_db
from app.schemas.candidate import (
    CandidateResponse,
    CandidateCreate,
    CandidateUpdate,
    DocumentResponse
)
from app.services.candidate_service import CandidateService
from app.services.storage_service import storage_service
from app.core.config import settings
from app.core.dependencies import get_current_user, require_permission
from app.db.models import User, Candidate, Experience, CandidateProfile, Chunk


class ExperienceResponse(BaseModel):
    id: int
    candidate_id: int
    company_name: Optional[str] = None
    role_title: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    is_current: bool = False

    class Config:
        from_attributes = True


class CandidateProfileResponse(BaseModel):
    id: int
    candidate_id: int
    snapshot_data: dict = {}
    version: int = 1
    created_at: Optional[str] = None

    class Config:
        from_attributes = True

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.get("/", response_model=List[CandidateResponse])
def list_candidates(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    city: Optional[str] = Query(None, description="Filtrar por cidade"),
    state: Optional[str] = Query(None, description="Filtrar por estado"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("candidates.read"))
):
    """
    Lista candidatos com filtros opcionais.
    Multi-tenant: cada usuario ve apenas candidatos da sua empresa.

    **Requer permissão:** candidates.read
    """
    company_id = current_user.company_id if settings.multi_tenant_enabled and not current_user.is_superuser else None
    candidates = CandidateService.get_candidates(
        db,
        skip=skip,
        limit=limit,
        city=city,
        state=state,
        company_id=company_id,
    )
    return candidates


@router.get("/{candidate_id}", response_model=CandidateResponse)
def get_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("candidates.read"))
):
    """
    Obtém um candidato específico por ID

    **Requer permissão:** candidates.read
    """
    candidate = CandidateService.get_candidate(db, candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidato {candidate_id} não encontrado"
        )
    # Multi-tenant: verificar que candidato pertence a empresa do usuario
    if settings.multi_tenant_enabled and not current_user.is_superuser and current_user.company_id:
        if candidate.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Candidato {candidate_id} não encontrado"
            )
    return candidate


@router.post("/", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
def create_candidate(
    candidate: CandidateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("candidates.create"))
):
    """
    Cria um novo candidato

    **Requer permissão:** candidates.create
    """
    return CandidateService.create_candidate(
        db, candidate, user_id=current_user.id, company_id=current_user.company_id
    )


@router.put("/{candidate_id}", response_model=CandidateResponse)
def update_candidate(
    candidate_id: int,
    candidate_update: CandidateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("candidates.update"))
):
    """
    Atualiza um candidato existente

    **Requer permissão:** candidates.update
    """
    updated = CandidateService.update_candidate(db, candidate_id, candidate_update, user_id=current_user.id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidato {candidate_id} não encontrado"
        )
    return updated


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("candidates.delete"))
):
    """
    Remove um candidato e todos os seus dados relacionados (currículos, experiências, etc.)

    ATENÇÃO: Esta operação é irreversível e remove:
    - Dados pessoais do candidato
    - Todos os currículos e documentos
    - Chunks e embeddings gerados
    - Experiências profissionais
    - Dados de enriquecimento (LinkedIn, etc.)

    Conforme LGPD, um log de auditoria é criado antes da remoção.

    **Requer permissão:** candidates.delete
    """
    deleted = CandidateService.delete_candidate(db, candidate_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidato {candidate_id} não encontrado"
        )


@router.get("/{candidate_id}/photo")
def get_candidate_photo(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("candidates.read")),
):
    """
    Retorna a foto de perfil do candidato (extraida automaticamente do curriculo).

    Retorna 404 se o candidato nao tem foto armazenada.

    **Requer permissao:** candidates.read
    """
    candidate = CandidateService.get_candidate(db, candidate_id)
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidato nao encontrado")

    if settings.multi_tenant_enabled and not current_user.is_superuser and current_user.company_id:
        if candidate.company_id != current_user.company_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidato nao encontrado")

    photo_rel = getattr(candidate, "photo_url", None)
    if not photo_rel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foto nao disponivel")

    try:
        absolute = storage_service.get_absolute_path(photo_rel)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foto nao disponivel")

    if not absolute.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foto nao disponivel")

    mime, _ = mimetypes.guess_type(str(absolute))
    return FileResponse(absolute, media_type=mime or "image/jpeg")


# Endpoints para gerenciar documentos/currículos

@router.get("/{candidate_id}/documents", response_model=List[DocumentResponse])
def list_candidate_documents(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("candidates.read"))
):
    """
    Lista todos os documentos/currículos de um candidato

    **Requer permissão:** candidates.read
    """
    candidate = CandidateService.get_candidate(db, candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidato {candidate_id} não encontrado"
        )

    documents = CandidateService.get_candidate_documents(db, candidate_id)
    return documents


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("documents.delete"))
):
    """
    Remove um currículo/documento específico

    Esta operação remove:
    - O documento do sistema
    - Todos os chunks extraídos do documento
    - Todos os embeddings gerados a partir dos chunks

    Um log de auditoria é criado antes da remoção.

    **Requer permissão:** documents.delete
    """
    deleted = CandidateService.delete_document(db, document_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento {document_id} não encontrado"
        )
    return


# Endpoints para experiencias profissionais

@router.get("/{candidate_id}/experiences", response_model=List[ExperienceResponse])
def list_candidate_experiences(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("candidates.read"))
):
    """
    Lista experiencias profissionais de um candidato

    **Requer permissao:** candidates.read
    """
    candidate = CandidateService.get_candidate(db, candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidato {candidate_id} nao encontrado"
        )

    experiences = db.query(Experience).filter(
        Experience.candidate_id == candidate_id
    ).order_by(Experience.start_date.desc()).all()

    return [
        ExperienceResponse(
            id=exp.id,
            candidate_id=exp.candidate_id,
            company_name=exp.company_name,
            role_title=exp.title,
            start_date=str(exp.start_date) if exp.start_date else None,
            end_date=str(exp.end_date) if exp.end_date else None,
            description=exp.description,
            location=exp.industry,
            is_current=exp.end_date is None
        )
        for exp in experiences
    ]


# Endpoints para perfis/snapshots de candidatos

@router.get("/{candidate_id}/profiles", response_model=List[CandidateProfileResponse])
def list_candidate_profiles(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("candidates.read"))
):
    """
    Lista perfis/snapshots de um candidato (versionados)

    **Requer permissao:** candidates.read
    """
    candidate = CandidateService.get_candidate(db, candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidato {candidate_id} nao encontrado"
        )

    profiles = db.query(CandidateProfile).filter(
        CandidateProfile.candidate_id == candidate_id
    ).order_by(CandidateProfile.version.desc()).all()

    return [
        CandidateProfileResponse(
            id=prof.id,
            candidate_id=prof.candidate_id,
            snapshot_data=prof.profile_json or {},
            version=prof.version,
            created_at=str(prof.created_at) if prof.created_at else None
        )
        for prof in profiles
    ]


# ================================================================
# Endpoints para dados enriquecidos do curriculo
# ================================================================


class EnrichedResumeResponse(BaseModel):
    """Resposta enriquecida com todos os dados do curriculo"""
    candidate_id: int
    extraction_method: str = "regex"
    ai_enhanced: bool = False
    personal_info: Dict[str, Any] = {}
    professional_objective: Dict[str, Any] = {}
    experiences: list = []
    education: list = []
    skills: Dict[str, Any] = {}
    languages: list = []
    certifications: list = []
    licenses: list = []
    additional_info: Dict[str, Any] = {}
    validation: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}

    class Config:
        from_attributes = True


class CareerAdvisoryResponse(BaseModel):
    """Resposta do modulo de consultoria de carreira"""
    candidate_id: int
    available: bool = False
    advisory: Optional[Dict[str, Any]] = None
    quick_tips: list = []
    error: Optional[str] = None


@router.get("/{candidate_id}/enriched-profile", response_model=EnrichedResumeResponse)
def get_enriched_profile(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("candidates.read"))
):
    """
    Retorna perfil enriquecido do candidato com dados completos.

    Inclui:
    - Dados pessoais com nivel de confianca por campo
    - Objetivo/resumo profissional
    - Experiencias detalhadas
    - Formacao academica
    - Skills categorizadas (tecnicas, soft, tools, frameworks)
    - Idiomas com nivel
    - Certificacoes
    - Habilitacoes e licencas
    - Informacoes adicionais (disponibilidade, equipamentos, ERP)
    - Validacao com alertas e score de confianca
    - Metadados da extracao

    **Requer permissao:** candidates.read
    """
    candidate = CandidateService.get_candidate(db, candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidato {candidate_id} nao encontrado"
        )

    # Get latest profile with enriched data
    latest_profile = db.query(CandidateProfile).filter(
        CandidateProfile.candidate_id == candidate_id
    ).order_by(CandidateProfile.version.desc()).first()

    if not latest_profile or not latest_profile.profile_json:
        # No enriched data yet - return basic info from candidate record
        return EnrichedResumeResponse(
            candidate_id=candidate_id,
            extraction_method="none",
            personal_info={
                "name": candidate.full_name,
                "name_confidence": 0.5,
                "email": candidate.email,
                "phone": candidate.phone,
                "location": f"{candidate.city}, {candidate.state}" if candidate.city else None,
                "cpf": candidate.doc_id,
                "linkedin": getattr(candidate, "linkedin_url", None),
                "photo_url": getattr(candidate, "photo_url", None),
                "has_photo": bool(getattr(candidate, "photo_url", None)),
            },
            professional_objective={
                "title": getattr(candidate, "professional_title", None),
                "summary": getattr(candidate, "professional_summary", None),
            },
            validation={
                "overall_confidence": 0.3,
                "quality_label": "baixa",
                "alerts": [{"field": "general", "type": "no_enriched_data", "severity": "medium",
                           "message": "Dados enriquecidos nao disponiveis. Reprocesse o documento."}],
            },
        )

    profile_data = latest_profile.profile_json

    # Check if this is enriched format (has "data" key) or legacy format
    if "data" in profile_data and "validation" in profile_data:
        # Enriched pipeline format
        enriched = profile_data.get("data", {})
        personal_info = dict(enriched.get("personal_info", {}))
        # Enriquecer com photo_url salvo no Candidate (se houver)
        photo_rel = getattr(candidate, "photo_url", None)
        if photo_rel:
            personal_info["photo_url"] = photo_rel
            personal_info["has_photo"] = True
        # Fallback para linkedin vindo do Candidate
        if not personal_info.get("linkedin") and getattr(candidate, "linkedin_url", None):
            personal_info["linkedin"] = candidate.linkedin_url
        return EnrichedResumeResponse(
            candidate_id=candidate_id,
            extraction_method=profile_data.get("extraction_method", "unknown"),
            ai_enhanced=profile_data.get("ai_enhanced", False),
            personal_info=personal_info,
            professional_objective=enriched.get("professional_objective", {}),
            experiences=enriched.get("experiences", []),
            education=enriched.get("education", []),
            skills=enriched.get("skills", {}),
            languages=enriched.get("languages", []),
            certifications=enriched.get("certifications", []),
            licenses=enriched.get("licenses", []),
            additional_info=enriched.get("additional_info", {}),
            validation=profile_data.get("validation", {}),
            metadata=profile_data.get("metadata", {}),
        )
    else:
        # Legacy format - convert to enriched response
        personal = profile_data.get("personal_info", {})
        photo_rel = getattr(candidate, "photo_url", None)
        return EnrichedResumeResponse(
            candidate_id=candidate_id,
            extraction_method="regex_legacy",
            personal_info={
                "name": personal.get("name") or candidate.full_name,
                "email": personal.get("email") or candidate.email,
                "phone": personal.get("phone") or candidate.phone,
                "location": personal.get("location"),
                "linkedin": personal.get("linkedin") or getattr(candidate, "linkedin_url", None),
                "github": personal.get("github"),
                "cpf": personal.get("cpf") or candidate.doc_id,
                "rg": personal.get("rg"),
                "birth_date": personal.get("birth_date"),
                "photo_url": photo_rel,
                "has_photo": bool(photo_rel),
            },
            professional_objective={
                "title": getattr(candidate, "professional_title", None),
                "summary": getattr(candidate, "professional_summary", None) or profile_data.get("summary"),
            },
            experiences=profile_data.get("experiences", []),
            education=profile_data.get("education", []),
            skills={"technical": profile_data.get("skills", [])},
            languages=profile_data.get("languages", []),
            certifications=[
                {"name": c} if isinstance(c, str) else c
                for c in profile_data.get("certifications", [])
            ],
            licenses=profile_data.get("licenses", []),
            additional_info={
                "availability": profile_data.get("availability", {}),
                "equipment": profile_data.get("equipment", []),
                "erp_systems": profile_data.get("erp_systems", []),
                "safety_certifications": profile_data.get("safety_certs", []),
            },
        )


@router.post("/{candidate_id}/career-advisory", response_model=CareerAdvisoryResponse)
async def get_career_advisory(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("candidates.read"))
):
    """
    Gera analise e recomendacoes de carreira para o candidato.

    Modulo OPCIONAL que fornece:
    - Pontuacao geral do curriculo (0-100)
    - Pontos fortes e fracos
    - Sugestoes de melhoria
    - Resumo profissional reescrito
    - Palavras-chave sugeridas
    - Gaps de apresentacao
    - Recomendacoes para RH
    - Dicas para o candidato
    - Areas mais adequadas

    Requer API OpenAI configurada para analise completa.
    Sem API, retorna dicas rapidas baseadas em heuristicas.

    **Requer permissao:** candidates.read
    """
    candidate = CandidateService.get_candidate(db, candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidato {candidate_id} nao encontrado"
        )

    # Get latest enriched profile
    latest_profile = db.query(CandidateProfile).filter(
        CandidateProfile.candidate_id == candidate_id
    ).order_by(CandidateProfile.version.desc()).first()

    if not latest_profile or not latest_profile.profile_json:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Candidato nao possui perfil processado. Faca upload de um curriculo primeiro."
        )

    profile_data = latest_profile.profile_json

    # Extract enriched data
    if "data" in profile_data:
        resume_data = profile_data["data"]
    else:
        # Legacy format - convert
        from app.services.resume_enrichment_pipeline import ResumeEnrichmentPipeline
        resume_data = ResumeEnrichmentPipeline._convert_regex_to_enriched(profile_data)

    # Get raw text from chunks
    raw_text = ""
    full_text_chunk = db.query(Chunk).filter(
        Chunk.candidate_id == candidate_id,
        Chunk.section == "full_text"
    ).first()
    if full_text_chunk:
        raw_text = full_text_chunk.content or ""

    # Generate advisory
    from app.services.career_advisory_service import CareerAdvisoryService

    try:
        advisory_result = await CareerAdvisoryService.generate_advisory(
            resume_data, raw_text
        )

        if advisory_result.get("available") and advisory_result.get("data"):
            return CareerAdvisoryResponse(
                candidate_id=candidate_id,
                available=True,
                advisory=advisory_result["data"],
            )
        else:
            # Fallback to quick tips
            quick_tips = CareerAdvisoryService.generate_quick_tips(resume_data)
            return CareerAdvisoryResponse(
                candidate_id=candidate_id,
                available=False,
                quick_tips=quick_tips,
                error=advisory_result.get("error"),
            )
    except Exception as e:
        quick_tips = CareerAdvisoryService.generate_quick_tips(resume_data)
        return CareerAdvisoryResponse(
            candidate_id=candidate_id,
            available=False,
            quick_tips=quick_tips,
            error=str(e),
        )
