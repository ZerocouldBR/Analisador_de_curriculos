"""
Schemas do portal do candidato para aplicar em vagas com o perfil existente.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class PortalJobListItem(BaseModel):
    """Vaga listada no portal do candidato, com indicador se ja foi aplicada."""
    slug: str
    title: str
    location: Optional[str] = None
    employment_type: Optional[str] = None
    seniority_level: Optional[str] = None
    work_mode: Optional[str] = None
    salary_display: Optional[str] = None
    published_at: Optional[datetime] = None
    already_applied: bool = False
    my_application_id: Optional[int] = None
    my_application_stage: Optional[str] = None


class PortalJobsListResponse(BaseModel):
    total: int
    jobs: List[PortalJobListItem]


class PortalMyApplication(BaseModel):
    id: int
    job_slug: str
    job_title: str
    stage: str
    fit_status: str
    fit_score: Optional[int] = None
    fit_summary: Optional[str] = None
    fit_recommendation: Optional[str] = None
    created_at: datetime


class PortalApplicationsListResponse(BaseModel):
    total: int
    applications: List[PortalMyApplication]


class PortalApplyRequest(BaseModel):
    """Aplicar usando o perfil existente (nao precisa reenviar curriculo)."""
    cover_letter: Optional[str] = None


class PortalApplyResponse(BaseModel):
    id: int
    message: str
    fit_status: str
    already_existed: bool = False
