"""
Schemas (Pydantic) para Vagas e Aplicacoes.
"""
from datetime import datetime
from typing import Optional, List, Any, Dict

from pydantic import BaseModel, EmailStr, Field


class JobBase(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10)
    requirements: Optional[str] = None
    responsibilities: Optional[str] = None
    benefits: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None  # CLT, PJ, Estagio, Temporario
    seniority_level: Optional[str] = None  # Junior, Pleno, Senior, Lead
    work_mode: Optional[str] = None  # presencial, remoto, hibrido
    salary_range_min: Optional[float] = None
    salary_range_max: Optional[float] = None
    salary_currency: Optional[str] = "BRL"
    salary_visible: Optional[bool] = False
    skills_required: Optional[List[str]] = []
    skills_desired: Optional[List[str]] = []
    closes_at: Optional[datetime] = None


class JobCreate(JobBase):
    is_active: Optional[bool] = True


class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    responsibilities: Optional[str] = None
    benefits: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    seniority_level: Optional[str] = None
    work_mode: Optional[str] = None
    salary_range_min: Optional[float] = None
    salary_range_max: Optional[float] = None
    salary_currency: Optional[str] = None
    salary_visible: Optional[bool] = None
    skills_required: Optional[List[str]] = None
    skills_desired: Optional[List[str]] = None
    is_active: Optional[bool] = None
    closes_at: Optional[datetime] = None


class JobResponse(JobBase):
    id: int
    company_id: int
    slug: str
    is_active: bool
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    applications_count: Optional[int] = 0

    class Config:
        from_attributes = True


class PublicCompanyBrand(BaseModel):
    """Dados publicos da empresa para branding da pagina de vagas."""
    name: str
    slug: str
    logo_url: Optional[str] = None
    website: Optional[str] = None
    brand_color: Optional[str] = None  # hex color (#RRGGBB) vindo de settings_json
    about: Optional[str] = None  # descricao curta


class PublicJobResponse(BaseModel):
    """Dados publicos de uma vaga (sem campos internos)."""
    id: int
    slug: str
    title: str
    description: str
    requirements: Optional[str] = None
    responsibilities: Optional[str] = None
    benefits: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    seniority_level: Optional[str] = None
    work_mode: Optional[str] = None
    salary_display: Optional[str] = None  # formatado se visible
    skills_required: List[str] = []
    skills_desired: List[str] = []
    published_at: Optional[datetime] = None
    closes_at: Optional[datetime] = None
    company: PublicCompanyBrand

    class Config:
        from_attributes = True


class PublicJobListItem(BaseModel):
    """Versao resumida para listagem publica."""
    slug: str
    title: str
    location: Optional[str] = None
    employment_type: Optional[str] = None
    seniority_level: Optional[str] = None
    work_mode: Optional[str] = None
    salary_display: Optional[str] = None
    published_at: Optional[datetime] = None


class PublicJobsPageResponse(BaseModel):
    """Pagina publica da empresa com branding e lista de vagas."""
    company: PublicCompanyBrand
    jobs: List[PublicJobListItem]
    total: int


class JobApplicationCreate(BaseModel):
    """Aplicacao a uma vaga (publica)."""
    applicant_name: str = Field(min_length=2, max_length=200)
    applicant_email: EmailStr
    applicant_phone: Optional[str] = None
    cover_letter: Optional[str] = None
    consent_given: bool = Field(
        description="Consentimento LGPD para processamento dos dados"
    )


class JobFitAnalysis(BaseModel):
    """Resultado da analise de fit por IA."""
    score: int  # 0-100
    summary: str
    strengths: List[str] = []
    gaps: List[str] = []
    matched_skills: List[str] = []
    missing_skills: List[str] = []
    experience_match: Optional[str] = None
    recommendation: Optional[str] = None  # "strong_match", "good_match", "weak_match", "no_match"


class JobApplicationResponse(BaseModel):
    id: int
    job_id: int
    candidate_id: int
    document_id: Optional[int] = None
    applicant_name: str
    applicant_email: str
    applicant_phone: Optional[str] = None
    cover_letter: Optional[str] = None
    fit_score: Optional[int] = None
    fit_analysis: Optional[Dict[str, Any]] = None
    fit_status: str
    stage: str
    stage_notes: Optional[str] = None
    source: str
    consent_given: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class JobApplicationStageUpdate(BaseModel):
    stage: str  # received, screening, interview, technical, offer, hired, rejected
    stage_notes: Optional[str] = None


class JobApplicationPublicResponse(BaseModel):
    """Resposta publica ao candidato apos aplicacao."""
    id: int
    message: str
    fit_status: str
    fit_score: Optional[int] = None
    fit_summary: Optional[str] = None
