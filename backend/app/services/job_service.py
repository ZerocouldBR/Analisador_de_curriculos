"""
Servico de gestao de vagas e aplicacoes.

Responsabilidades:
- CRUD de vagas com slug publico unico
- Listagem publica por empresa (via slug da empresa)
- Aplicacao publica: cria candidato + upload do curriculo + aplicacao
- Disparo da analise de fit por IA (background task)
"""
from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import (
    Candidate,
    CandidateProfile,
    Company,
    Document,
    Job,
    JobApplication,
)

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _slugify(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r'[áàâã]', 'a', text)
    text = re.sub(r'[éèê]', 'e', text)
    text = re.sub(r'[íì]', 'i', text)
    text = re.sub(r'[óòôõ]', 'o', text)
    text = re.sub(r'[úù]', 'u', text)
    text = re.sub(r'[ç]', 'c', text)
    text = re.sub(r'[^a-z0-9]+', '-', text)
    text = text.strip('-')
    return text[:80] or 'vaga'


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


class JobService:
    # ==========================================================
    # Slug
    # ==========================================================

    @staticmethod
    def generate_unique_slug(db: Session, company_id: int, title: str) -> str:
        base = _slugify(title)
        candidate = base
        # Evitar colisao global (slug e UNIQUE)
        for _ in range(5):
            existing = db.query(Job).filter(Job.slug == candidate).first()
            if not existing:
                return candidate
            candidate = f"{base}-{secrets.token_hex(3)}"
        # Fallback: incluir timestamp
        return f"{base}-{int(_utcnow().timestamp())}"

    # ==========================================================
    # CRUD - area autenticada
    # ==========================================================

    @staticmethod
    def create_job(
        db: Session,
        company_id: int,
        user_id: Optional[int],
        data: Dict[str, Any],
    ) -> Job:
        slug = JobService.generate_unique_slug(db, company_id, data["title"])

        is_active = data.pop("is_active", True)
        job = Job(
            company_id=company_id,
            slug=slug,
            created_by=user_id,
            is_active=is_active,
            published_at=_utcnow() if is_active else None,
            **{k: v for k, v in data.items() if hasattr(Job, k)},
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def list_jobs(
        db: Session,
        company_id: int,
        skip: int = 0,
        limit: int = 50,
        include_inactive: bool = True,
    ) -> List[Job]:
        query = db.query(Job).filter(Job.company_id == company_id)
        if not include_inactive:
            query = query.filter(Job.is_active.is_(True))
        return query.order_by(Job.created_at.desc()).offset(skip).limit(limit).all()

    @staticmethod
    def get_job(db: Session, job_id: int, company_id: Optional[int] = None) -> Optional[Job]:
        query = db.query(Job).filter(Job.id == job_id)
        if company_id is not None:
            query = query.filter(Job.company_id == company_id)
        return query.first()

    @staticmethod
    def update_job(
        db: Session,
        job_id: int,
        company_id: int,
        changes: Dict[str, Any],
    ) -> Optional[Job]:
        job = JobService.get_job(db, job_id, company_id)
        if not job:
            return None

        for key, value in changes.items():
            if value is None:
                continue
            if hasattr(job, key):
                setattr(job, key, value)

        # Publicar automaticamente ao ativar pela primeira vez
        if changes.get("is_active") is True and not job.published_at:
            job.published_at = _utcnow()

        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def delete_job(db: Session, job_id: int, company_id: int) -> bool:
        job = JobService.get_job(db, job_id, company_id)
        if not job:
            return False
        db.delete(job)
        db.commit()
        return True

    @staticmethod
    def count_applications(db: Session, job_id: int) -> int:
        return db.query(func.count(JobApplication.id)).filter(
            JobApplication.job_id == job_id
        ).scalar() or 0

    @staticmethod
    def list_applications(
        db: Session,
        job_id: int,
        stage: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[JobApplication]:
        query = db.query(JobApplication).filter(JobApplication.job_id == job_id)
        if stage:
            query = query.filter(JobApplication.stage == stage)
        return query.order_by(
            JobApplication.fit_score.desc().nullslast(),
            JobApplication.created_at.desc(),
        ).offset(skip).limit(limit).all()

    @staticmethod
    def update_application_stage(
        db: Session,
        application_id: int,
        job_id: int,
        stage: str,
        notes: Optional[str] = None,
    ) -> Optional[JobApplication]:
        app = db.query(JobApplication).filter(
            JobApplication.id == application_id,
            JobApplication.job_id == job_id,
        ).first()
        if not app:
            return None
        app.stage = stage
        if notes is not None:
            app.stage_notes = notes
        db.commit()
        db.refresh(app)
        return app

    # ==========================================================
    # Publico
    # ==========================================================

    @staticmethod
    def get_public_company(db: Session, company_slug: str) -> Optional[Company]:
        return db.query(Company).filter(
            Company.slug == company_slug,
            Company.is_active.is_(True),
        ).first()

    @staticmethod
    def list_public_jobs(db: Session, company_id: int) -> List[Job]:
        return db.query(Job).filter(
            Job.company_id == company_id,
            Job.is_active.is_(True),
        ).order_by(Job.published_at.desc().nullslast(), Job.created_at.desc()).all()

    @staticmethod
    def get_public_job(db: Session, company_id: int, job_slug: str) -> Optional[Job]:
        return db.query(Job).filter(
            Job.company_id == company_id,
            Job.slug == job_slug,
            Job.is_active.is_(True),
        ).first()

    @staticmethod
    def company_brand_payload(company: Company) -> Dict[str, Any]:
        """Extrai branding publico (logo + cor) do Company."""
        settings = company.settings_json or {}
        return {
            "name": company.name,
            "slug": company.slug,
            "logo_url": company.logo_url,
            "website": company.website,
            "brand_color": settings.get("brand_color"),
            "about": settings.get("public_about"),
        }

    @staticmethod
    def public_job_payload(job: Job, company: Company) -> Dict[str, Any]:
        return {
            "id": job.id,
            "slug": job.slug,
            "title": job.title,
            "description": job.description,
            "requirements": job.requirements,
            "responsibilities": job.responsibilities,
            "benefits": job.benefits,
            "location": job.location,
            "employment_type": job.employment_type,
            "seniority_level": job.seniority_level,
            "work_mode": job.work_mode,
            "salary_display": _format_salary(job),
            "skills_required": job.skills_required or [],
            "skills_desired": job.skills_desired or [],
            "published_at": job.published_at,
            "closes_at": job.closes_at,
            "company": JobService.company_brand_payload(company),
        }

    @staticmethod
    def public_job_list_item(job: Job) -> Dict[str, Any]:
        return {
            "slug": job.slug,
            "title": job.title,
            "location": job.location,
            "employment_type": job.employment_type,
            "seniority_level": job.seniority_level,
            "work_mode": job.work_mode,
            "salary_display": _format_salary(job),
            "published_at": job.published_at,
        }

    # ==========================================================
    # Aplicacao (publico)
    # ==========================================================

    @staticmethod
    def find_or_create_candidate(
        db: Session,
        company_id: int,
        name: str,
        email: str,
        phone: Optional[str] = None,
    ) -> Candidate:
        existing = db.query(Candidate).filter(
            Candidate.company_id == company_id,
            Candidate.email == email,
        ).first()
        if existing:
            return existing

        candidate = Candidate(
            company_id=company_id,
            full_name=name[:200],
            email=email,
            phone=phone,
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        return candidate

    @staticmethod
    def create_application(
        db: Session,
        job: Job,
        candidate: Candidate,
        document: Optional[Document],
        applicant_name: str,
        applicant_email: str,
        applicant_phone: Optional[str],
        cover_letter: Optional[str],
        consent_given: bool,
    ) -> JobApplication:
        application = JobApplication(
            job_id=job.id,
            candidate_id=candidate.id,
            document_id=document.id if document else None,
            applicant_name=applicant_name[:200],
            applicant_email=applicant_email,
            applicant_phone=applicant_phone,
            cover_letter=cover_letter,
            fit_status="pending",
            stage="received",
            source="public_form",
            consent_given=consent_given,
        )
        db.add(application)
        db.commit()
        db.refresh(application)
        return application

    @staticmethod
    def get_candidate_latest_profile(
        db: Session, candidate_id: int
    ) -> Optional[Dict[str, Any]]:
        profile = db.query(CandidateProfile).filter(
            CandidateProfile.candidate_id == candidate_id
        ).order_by(CandidateProfile.version.desc()).first()
        if not profile or not profile.profile_json:
            return None
        return profile.profile_json

    @staticmethod
    def save_fit_analysis(
        db: Session,
        application_id: int,
        fit: Dict[str, Any],
        status: str,
    ) -> Optional[JobApplication]:
        app = db.query(JobApplication).filter(
            JobApplication.id == application_id
        ).first()
        if not app:
            return None
        app.fit_analysis = fit
        app.fit_score = int(fit.get("score", 0) or 0) if fit else None
        app.fit_status = status
        db.commit()
        db.refresh(app)
        return app
