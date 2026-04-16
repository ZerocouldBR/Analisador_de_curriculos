"""
Endpoints de gestao de vagas para a area autenticada (RH).

Inclui:
- CRUD de vagas
- Listagem de aplicacoes com score de fit
- Atualizacao de estagio do candidato no pipeline
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import require_permission
from app.db.database import get_db
from app.db.models import User
from app.schemas.job import (
    JobCreate,
    JobUpdate,
    JobResponse,
    JobApplicationResponse,
    JobApplicationStageUpdate,
)
from app.services.job_service import JobService


router = APIRouter(prefix="/jobs", tags=["jobs"])


def _ensure_company(user: User) -> int:
    if not user.company_id and not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario sem empresa associada",
        )
    return user.company_id


def _job_response(job, applications_count: int = 0) -> JobResponse:
    return JobResponse(
        id=job.id,
        company_id=job.company_id,
        slug=job.slug,
        title=job.title,
        description=job.description,
        requirements=job.requirements,
        responsibilities=job.responsibilities,
        benefits=job.benefits,
        location=job.location,
        employment_type=job.employment_type,
        seniority_level=job.seniority_level,
        work_mode=job.work_mode,
        salary_range_min=job.salary_range_min,
        salary_range_max=job.salary_range_max,
        salary_currency=job.salary_currency,
        salary_visible=job.salary_visible,
        skills_required=job.skills_required or [],
        skills_desired=job.skills_desired or [],
        is_active=job.is_active,
        published_at=job.published_at,
        closes_at=job.closes_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
        applications_count=applications_count,
    )


@router.post("/", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    data: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("jobs.create")),
):
    """Cria uma nova vaga. Requer permissao `jobs.create`."""
    company_id = _ensure_company(current_user)
    job = JobService.create_job(
        db=db,
        company_id=company_id,
        user_id=current_user.id,
        data=data.model_dump(),
    )
    return _job_response(job)


@router.get("/", response_model=List[JobResponse])
def list_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    include_inactive: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("jobs.read")),
):
    """Lista vagas da empresa do usuario."""
    company_id = _ensure_company(current_user)
    jobs = JobService.list_jobs(
        db=db,
        company_id=company_id,
        skip=skip,
        limit=limit,
        include_inactive=include_inactive,
    )
    return [
        _job_response(j, JobService.count_applications(db, j.id))
        for j in jobs
    ]


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("jobs.read")),
):
    company_id = _ensure_company(current_user)
    job = JobService.get_job(db, job_id, company_id)
    if not job:
        raise HTTPException(status_code=404, detail="Vaga nao encontrada")
    return _job_response(job, JobService.count_applications(db, job.id))


@router.put("/{job_id}", response_model=JobResponse)
def update_job(
    job_id: int,
    data: JobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("jobs.update")),
):
    company_id = _ensure_company(current_user)
    job = JobService.update_job(
        db=db,
        job_id=job_id,
        company_id=company_id,
        changes=data.model_dump(exclude_unset=True),
    )
    if not job:
        raise HTTPException(status_code=404, detail="Vaga nao encontrada")
    return _job_response(job, JobService.count_applications(db, job.id))


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("jobs.delete")),
):
    company_id = _ensure_company(current_user)
    ok = JobService.delete_job(db, job_id, company_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Vaga nao encontrada")


@router.get("/{job_id}/applications", response_model=List[JobApplicationResponse])
def list_job_applications(
    job_id: int,
    stage: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("jobs.read")),
):
    """Lista aplicacoes de uma vaga, ordenadas por score de fit descendente."""
    company_id = _ensure_company(current_user)
    job = JobService.get_job(db, job_id, company_id)
    if not job:
        raise HTTPException(status_code=404, detail="Vaga nao encontrada")

    apps = JobService.list_applications(db, job_id=job.id, stage=stage, skip=skip, limit=limit)
    return [JobApplicationResponse.model_validate(a) for a in apps]


@router.patch("/{job_id}/applications/{application_id}/stage",
              response_model=JobApplicationResponse)
def update_application_stage(
    job_id: int,
    application_id: int,
    data: JobApplicationStageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("jobs.update")),
):
    company_id = _ensure_company(current_user)
    job = JobService.get_job(db, job_id, company_id)
    if not job:
        raise HTTPException(status_code=404, detail="Vaga nao encontrada")

    app = JobService.update_application_stage(
        db=db,
        application_id=application_id,
        job_id=job.id,
        stage=data.stage,
        notes=data.stage_notes,
    )
    if not app:
        raise HTTPException(status_code=404, detail="Aplicacao nao encontrada")
    return JobApplicationResponse.model_validate(app)
