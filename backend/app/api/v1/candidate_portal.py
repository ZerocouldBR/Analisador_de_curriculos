"""
Endpoints publicos do portal do candidato (magic link).

Rotas:
- GET /public/me/{token}                   -> ver o proprio perfil
- PATCH /public/me/{token}                 -> atualizar campos editaveis
- POST /public/me/{token}/improve          -> pedir sugestao de melhoria via IA
- POST /public/me/{token}/apply-suggestion -> aplicar uma sugestao aprovada
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db.database import get_db
from app.db.models import (
    AuditLog,
    Candidate,
    CandidateProfile,
    Company,
    Job,
    JobApplication,
)
from app.schemas.candidate_portal import (
    ApplySuggestionRequest,
    ImproveRequest,
    ImproveResponse,
    PortalCompanyBrand,
    PortalEducation,
    PortalExperience,
    PortalPatchRequest,
    PortalProfile,
)
from app.schemas.candidate_portal_jobs import (
    PortalApplicationsListResponse,
    PortalApplyRequest,
    PortalApplyResponse,
    PortalJobListItem,
    PortalJobsListResponse,
    PortalMyApplication,
)
from app.services.candidate_access_token_service import CandidateAccessTokenService
from app.services.job_service import JobService
from app.services.profile_improvement_service import ProfileImprovementService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/public/me", tags=["candidate-portal"])


def _validate_token(db: Session, token_raw: str) -> Candidate:
    token = CandidateAccessTokenService.validate(db, token_raw)
    if not token:
        raise HTTPException(status_code=404, detail="Token invalido ou expirado")
    candidate = db.query(Candidate).filter(Candidate.id == token.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidato nao encontrado")
    candidate._access_token = token  # type: ignore[attr-defined]
    return candidate


def _latest_profile(db: Session, candidate_id: int) -> Optional[CandidateProfile]:
    return db.query(CandidateProfile).filter(
        CandidateProfile.candidate_id == candidate_id
    ).order_by(CandidateProfile.version.desc()).first()


def _profile_payload(profile: Optional[CandidateProfile]) -> Dict[str, Any]:
    if not profile or not profile.profile_json:
        return {}
    pj = profile.profile_json
    # Formato enriquecido pode vir embrulhado em "data"
    if isinstance(pj, dict) and "data" in pj and "validation" in pj:
        pj = pj["data"]
    return pj or {}


def _build_company_brand(company: Optional[Company]) -> Optional[PortalCompanyBrand]:
    if not company:
        return None
    settings_json = company.settings_json or {}
    return PortalCompanyBrand(
        name=company.name,
        slug=company.slug,
        logo_url=company.logo_url,
        brand_color=settings_json.get("brand_color"),
    )


def _load_portal_profile(
    candidate: Candidate,
    profile_data: Dict[str, Any],
) -> PortalProfile:
    personal = profile_data.get("personal_info") or {}
    objective = profile_data.get("professional_objective") or {}
    skills = profile_data.get("skills") or {}
    experiences_raw = profile_data.get("experiences") or []
    education_raw = profile_data.get("education") or []

    experiences = [
        PortalExperience(**{k: v for k, v in e.items() if k in PortalExperience.model_fields})
        for e in experiences_raw if isinstance(e, dict)
    ]
    education = [
        PortalEducation(**{k: v for k, v in e.items() if k in PortalEducation.model_fields})
        for e in education_raw if isinstance(e, dict)
    ]

    return PortalProfile(
        candidate_id=candidate.id,
        full_name=candidate.full_name,
        email=personal.get("email") or candidate.email,
        phone=personal.get("phone") or candidate.phone,
        location=personal.get("location"),
        linkedin=personal.get("linkedin"),
        github=personal.get("github"),
        portfolio=personal.get("portfolio"),
        photo_url=personal.get("photo_url"),
        headline=objective.get("title"),
        summary=objective.get("summary"),
        experiences=experiences,
        education=education,
        skills_technical=list(skills.get("technical") or []) if isinstance(skills, dict) else (skills or []),
        skills_soft=list(skills.get("soft") or []) if isinstance(skills, dict) else [],
        languages=list(profile_data.get("languages") or []),
        certifications=list(profile_data.get("certifications") or []),
        company=None,  # preenchido no endpoint
        token_expires_at=None,
    )


def _save_edits_to_profile(
    db: Session,
    candidate: Candidate,
    profile: Optional[CandidateProfile],
    changes: Dict[str, Any],
) -> CandidateProfile:
    """
    Cria uma nova versao do CandidateProfile com as alteracoes mescladas.
    Preserva o formato enriquecido quando houver.
    """
    base = {}
    is_enriched_wrapper = False
    if profile and profile.profile_json:
        raw = profile.profile_json
        if isinstance(raw, dict) and "data" in raw and "validation" in raw:
            is_enriched_wrapper = True
            base = dict(raw["data"]) if isinstance(raw["data"], dict) else {}
        else:
            base = dict(raw) if isinstance(raw, dict) else {}

    personal = dict(base.get("personal_info") or {})
    objective = dict(base.get("professional_objective") or {})
    skills = base.get("skills") or {}
    if isinstance(skills, list):
        skills = {"technical": skills, "soft": [], "tools": [], "frameworks": []}
    elif not isinstance(skills, dict):
        skills = {"technical": [], "soft": [], "tools": [], "frameworks": []}

    # Aplicar mudancas
    if "full_name" in changes and changes["full_name"] is not None:
        candidate.full_name = changes["full_name"][:200]
    if "email" in changes and changes["email"] is not None:
        candidate.email = changes["email"]
        personal["email"] = changes["email"]
    if "phone" in changes and changes["phone"] is not None:
        candidate.phone = changes["phone"]
        personal["phone"] = changes["phone"]
    if "location" in changes and changes["location"] is not None:
        personal["location"] = changes["location"]
    if "linkedin" in changes and changes["linkedin"] is not None:
        personal["linkedin"] = changes["linkedin"]
    if "github" in changes and changes["github"] is not None:
        personal["github"] = changes["github"]
    if "portfolio" in changes and changes["portfolio"] is not None:
        personal["portfolio"] = changes["portfolio"]

    if "headline" in changes and changes["headline"] is not None:
        objective["title"] = changes["headline"]
    if "summary" in changes and changes["summary"] is not None:
        objective["summary"] = changes["summary"]

    if "experiences" in changes and changes["experiences"] is not None:
        base["experiences"] = changes["experiences"]
    if "skills_technical" in changes and changes["skills_technical"] is not None:
        skills = {**skills, "technical": changes["skills_technical"]}

    base["personal_info"] = personal
    base["professional_objective"] = objective
    base["skills"] = skills

    # Criar nova versao
    next_version = (profile.version + 1) if profile else 1
    new_data: Any
    if is_enriched_wrapper and profile and profile.profile_json:
        wrapper = dict(profile.profile_json)
        wrapper["data"] = base
        # metadata extra para rastreabilidade
        wrapper.setdefault("metadata", {})
        if isinstance(wrapper["metadata"], dict):
            wrapper["metadata"]["last_self_edit_at"] = None
        new_data = wrapper
    else:
        new_data = base

    new_profile = CandidateProfile(
        candidate_id=candidate.id,
        version=next_version,
        profile_json=new_data,
    )
    db.add(new_profile)
    db.commit()
    db.refresh(new_profile)
    return new_profile


# ============================================================
# Endpoints
# ============================================================


@router.get("/{token}", response_model=PortalProfile)
def get_my_profile(token: str, db: Session = Depends(get_db)):
    candidate = _validate_token(db, token)
    profile = _latest_profile(db, candidate.id)
    pj = _profile_payload(profile)

    portal = _load_portal_profile(candidate, pj)
    company = db.query(Company).filter(Company.id == candidate.company_id).first() if candidate.company_id else None
    portal.company = _build_company_brand(company)
    access = getattr(candidate, "_access_token", None)
    if access:
        portal.token_expires_at = access.expires_at
    return portal


@router.patch("/{token}", response_model=PortalProfile)
def patch_my_profile(
    token: str,
    data: PortalPatchRequest,
    db: Session = Depends(get_db),
):
    candidate = _validate_token(db, token)
    profile = _latest_profile(db, candidate.id)

    changes = data.model_dump(exclude_unset=True)
    # Serializar experiencias se vierem
    if "experiences" in changes and changes["experiences"] is not None:
        changes["experiences"] = [
            exp.model_dump(exclude_none=True) if hasattr(exp, "model_dump") else exp
            for exp in changes["experiences"]
        ]

    new_profile = _save_edits_to_profile(db, candidate, profile, changes)
    pj = _profile_payload(new_profile)
    portal = _load_portal_profile(candidate, pj)
    company = db.query(Company).filter(Company.id == candidate.company_id).first() if candidate.company_id else None
    portal.company = _build_company_brand(company)
    return portal


@router.post("/{token}/improve", response_model=ImproveResponse)
async def improve_field(
    token: str,
    data: ImproveRequest,
    db: Session = Depends(get_db),
):
    candidate = _validate_token(db, token)
    profile = _latest_profile(db, candidate.id)
    pj = _profile_payload(profile)

    objective = pj.get("professional_objective") or {}
    skills = pj.get("skills") or {}
    skills_technical = []
    if isinstance(skills, dict):
        skills_technical = list(skills.get("technical") or [])
    elif isinstance(skills, list):
        skills_technical = list(skills)
    experiences = pj.get("experiences") or []

    if data.field == "summary":
        original = objective.get("summary") or ""
        result = await ProfileImprovementService.improve_summary(
            name=candidate.full_name,
            headline=objective.get("title"),
            summary=original,
            skills=skills_technical,
            experiences=experiences,
        )
        if not result.get("ai_available"):
            return ImproveResponse(
                field="summary", original=original, ai_available=False,
                error="IA indisponivel",
            )
        if not result.get("data"):
            return ImproveResponse(
                field="summary", original=original, error=result.get("error"),
            )
        suggestion = result["data"]
        return ImproveResponse(
            field="summary",
            original=original,
            suggestion=suggestion,
            rationale=suggestion.get("rationale"),
        )

    if data.field == "headline":
        original = objective.get("title") or ""
        result = await ProfileImprovementService.improve_headline(
            headline=original,
            summary=objective.get("summary"),
            skills=skills_technical,
        )
        if not result.get("ai_available"):
            return ImproveResponse(field="headline", original=original, ai_available=False,
                                   error="IA indisponivel")
        if not result.get("data"):
            return ImproveResponse(field="headline", original=original, error=result.get("error"))
        suggestion = result["data"]
        return ImproveResponse(
            field="headline",
            original=original,
            suggestion=suggestion,
            rationale=suggestion.get("rationale"),
        )

    if data.field == "experience":
        if data.experience_index is None:
            raise HTTPException(status_code=400, detail="experience_index obrigatorio")
        if data.experience_index < 0 or data.experience_index >= len(experiences):
            raise HTTPException(status_code=400, detail="experience_index fora do intervalo")
        exp = experiences[data.experience_index] or {}
        original_desc = exp.get("description") or ""
        period = f"{exp.get('start_date','?')} - {exp.get('end_date','?')}"
        result = await ProfileImprovementService.improve_experience(
            company=exp.get("company") or "",
            title=exp.get("title") or "",
            period=period,
            description=original_desc,
        )
        if not result.get("ai_available"):
            return ImproveResponse(
                field="experience", experience_index=data.experience_index,
                original=original_desc, ai_available=False, error="IA indisponivel",
            )
        if not result.get("data"):
            return ImproveResponse(
                field="experience", experience_index=data.experience_index,
                original=original_desc, error=result.get("error"),
            )
        suggestion = result["data"]
        return ImproveResponse(
            field="experience",
            experience_index=data.experience_index,
            original=original_desc,
            suggestion=suggestion,
            rationale=suggestion.get("rationale"),
        )

    raise HTTPException(status_code=400, detail=f"Campo nao suportado: {data.field}")


@router.post("/{token}/apply-suggestion", response_model=PortalProfile)
def apply_suggestion(
    token: str,
    data: ApplySuggestionRequest,
    db: Session = Depends(get_db),
):
    """
    Aplica uma sugestao aprovada pelo candidato.
    - summary / headline: `value` e string
    - experience: `value` e objeto com os campos atualizados (description, etc.)
      e `experience_index` identifica qual experiencia
    """
    candidate = _validate_token(db, token)
    profile = _latest_profile(db, candidate.id)

    if data.field == "summary":
        if not isinstance(data.value, str):
            raise HTTPException(status_code=400, detail="value deve ser string para summary")
        changes = {"summary": data.value}
    elif data.field == "headline":
        if not isinstance(data.value, str):
            raise HTTPException(status_code=400, detail="value deve ser string para headline")
        changes = {"headline": data.value}
    elif data.field == "experience":
        if data.experience_index is None:
            raise HTTPException(status_code=400, detail="experience_index obrigatorio")
        if not isinstance(data.value, dict):
            raise HTTPException(status_code=400, detail="value deve ser objeto para experience")
        pj = _profile_payload(profile)
        experiences = list(pj.get("experiences") or [])
        if data.experience_index < 0 or data.experience_index >= len(experiences):
            raise HTTPException(status_code=400, detail="experience_index fora do intervalo")
        experiences[data.experience_index] = {
            **(experiences[data.experience_index] or {}),
            **data.value,
        }
        changes = {"experiences": experiences}
    else:
        raise HTTPException(status_code=400, detail=f"Campo nao suportado: {data.field}")

    new_profile = _save_edits_to_profile(db, candidate, profile, changes)
    pj = _profile_payload(new_profile)
    portal = _load_portal_profile(candidate, pj)
    company = db.query(Company).filter(Company.id == candidate.company_id).first() if candidate.company_id else None
    portal.company = _build_company_brand(company)
    return portal


# ============================================================
# Portal + Vagas: candidato ve vagas da empresa dele e aplica
# ============================================================


def _format_salary(job: Job) -> Optional[str]:
    if not job.salary_visible:
        return None
    if job.salary_range_min is None and job.salary_range_max is None:
        return None
    currency = job.salary_currency or "BRL"
    if job.salary_range_min is not None and job.salary_range_max is not None:
        return f"{currency} {job.salary_range_min:,.0f} - {job.salary_range_max:,.0f}"
    if job.salary_range_min is not None:
        return f"A partir de {currency} {job.salary_range_min:,.0f}"
    return f"Ate {currency} {job.salary_range_max:,.0f}"


@router.get("/{token}/jobs", response_model=PortalJobsListResponse)
def list_company_jobs(token: str, db: Session = Depends(get_db)):
    """
    Lista vagas ativas da empresa do candidato.
    Marca quais ele ja aplicou (e em que estagio estao).
    """
    candidate = _validate_token(db, token)
    if not candidate.company_id:
        return PortalJobsListResponse(total=0, jobs=[])

    jobs = JobService.list_public_jobs(db, candidate.company_id)

    # Aplicacoes existentes do candidato
    apps = db.query(JobApplication).filter(
        JobApplication.candidate_id == candidate.id,
        JobApplication.job_id.in_([j.id for j in jobs]) if jobs else False,
    ).all()
    apps_by_job: Dict[int, JobApplication] = {a.job_id: a for a in apps}

    items: List[PortalJobListItem] = []
    for job in jobs:
        app = apps_by_job.get(job.id)
        items.append(PortalJobListItem(
            slug=job.slug,
            title=job.title,
            location=job.location,
            employment_type=job.employment_type,
            seniority_level=job.seniority_level,
            work_mode=job.work_mode,
            salary_display=_format_salary(job),
            published_at=job.published_at,
            already_applied=app is not None,
            my_application_id=app.id if app else None,
            my_application_stage=app.stage if app else None,
        ))

    return PortalJobsListResponse(total=len(items), jobs=items)


@router.get(
    "/{token}/applications",
    response_model=PortalApplicationsListResponse,
)
def list_my_applications(token: str, db: Session = Depends(get_db)):
    """Lista as candidaturas do candidato (com score de fit)."""
    candidate = _validate_token(db, token)

    apps = db.query(JobApplication).filter(
        JobApplication.candidate_id == candidate.id,
    ).order_by(JobApplication.created_at.desc()).all()

    # Resolver titulo / slug da vaga
    job_ids = list({a.job_id for a in apps})
    jobs_map: Dict[int, Job] = {}
    if job_ids:
        jobs = db.query(Job).filter(Job.id.in_(job_ids)).all()
        jobs_map = {j.id: j for j in jobs}

    items: List[PortalMyApplication] = []
    for app in apps:
        job = jobs_map.get(app.job_id)
        analysis = app.fit_analysis or {}
        items.append(PortalMyApplication(
            id=app.id,
            job_slug=job.slug if job else "",
            job_title=job.title if job else "(vaga removida)",
            stage=app.stage,
            fit_status=app.fit_status,
            fit_score=app.fit_score,
            fit_summary=analysis.get("summary") if isinstance(analysis, dict) else None,
            fit_recommendation=analysis.get("recommendation") if isinstance(analysis, dict) else None,
            created_at=app.created_at,
        ))
    return PortalApplicationsListResponse(total=len(items), applications=items)


@router.post(
    "/{token}/apply/{job_slug}",
    response_model=PortalApplyResponse,
    status_code=status.HTTP_201_CREATED,
)
def apply_with_existing_profile(
    token: str,
    job_slug: str,
    data: PortalApplyRequest,
    db: Session = Depends(get_db),
):
    """
    Aplicar a uma vaga usando o perfil ja existente (sem reenvio de curriculo).
    Reutiliza o ultimo Document do candidato para vincular a JobApplication.
    """
    candidate = _validate_token(db, token)
    if not candidate.company_id:
        raise HTTPException(status_code=404, detail="Empresa nao encontrada")

    job = db.query(Job).filter(
        Job.company_id == candidate.company_id,
        Job.slug == job_slug,
        Job.is_active.is_(True),
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Vaga nao encontrada ou inativa")

    # Dedup: uma candidatura ativa por (candidato, vaga)
    existing = db.query(JobApplication).filter(
        JobApplication.candidate_id == candidate.id,
        JobApplication.job_id == job.id,
    ).first()
    if existing:
        return PortalApplyResponse(
            id=existing.id,
            message="Voce ja aplicou a esta vaga.",
            fit_status=existing.fit_status,
            already_existed=True,
        )

    # Reutilizar ultimo documento do candidato
    from app.db.models import Document
    document = db.query(Document).filter(
        Document.candidate_id == candidate.id
    ).order_by(Document.uploaded_at.desc()).first()

    application = JobService.create_application(
        db=db,
        job=job,
        candidate=candidate,
        document=document,
        applicant_name=candidate.full_name,
        applicant_email=candidate.email or "",
        applicant_phone=candidate.phone,
        cover_letter=data.cover_letter,
        consent_given=True,  # acesso via magic link implica consentimento
    )

    # Audit log
    try:
        audit = AuditLog(
            user_id=None,
            action="portal_job_apply",
            entity="job_application",
            entity_id=application.id,
            metadata_json={
                "job_id": job.id,
                "job_slug": job.slug,
                "candidate_id": candidate.id,
                "via": "portal_magic_link",
            },
        )
        db.add(audit)
        db.commit()
    except Exception:
        pass

    # Enfileirar analise de fit (o perfil ja existe; a task nao precisa esperar processamento)
    try:
        from app.tasks.job_fit_tasks import analyze_application_fit_task
        analyze_application_fit_task.delay(application.id, wait_for_profile_seconds=5)
    except Exception as e:
        logger.warning(f"Falha ao enfileirar analise de fit: {e}")

    return PortalApplyResponse(
        id=application.id,
        message="Candidatura registrada. A analise de fit sera processada em instantes.",
        fit_status=application.fit_status,
        already_existed=False,
    )
