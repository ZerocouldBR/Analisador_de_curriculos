"""
Schemas do portal do candidato (magic link).
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr


class GenerateTokenRequest(BaseModel):
    expires_in_hours: Optional[int] = 72
    purpose: Optional[str] = "self_edit"


class AccessTokenResponse(BaseModel):
    id: int
    candidate_id: int
    token: str
    url: str
    expires_at: datetime
    created_at: datetime
    revoked_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    use_count: int = 0
    purpose: str = "self_edit"

    class Config:
        from_attributes = True


class AccessTokenListItem(BaseModel):
    id: int
    expires_at: datetime
    created_at: datetime
    revoked_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    use_count: int = 0
    purpose: str = "self_edit"

    class Config:
        from_attributes = True


# ========== Portal publico do candidato ==========

class PortalCompanyBrand(BaseModel):
    name: str
    slug: Optional[str] = None
    logo_url: Optional[str] = None
    brand_color: Optional[str] = None


class PortalExperience(BaseModel):
    company: Optional[str] = None
    title: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    achievements: Optional[List[str]] = None


class PortalEducation(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    field: Optional[str] = None
    start_year: Optional[str] = None
    end_year: Optional[str] = None
    status: Optional[str] = None


class PortalProfile(BaseModel):
    candidate_id: int
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    photo_url: Optional[str] = None
    headline: Optional[str] = None
    summary: Optional[str] = None
    experiences: List[PortalExperience] = []
    education: List[PortalEducation] = []
    skills_technical: List[str] = []
    skills_soft: List[str] = []
    languages: List[Dict[str, str]] = []
    certifications: List[Dict[str, Any]] = []
    company: Optional[PortalCompanyBrand] = None
    token_expires_at: Optional[datetime] = None


class PortalPatchRequest(BaseModel):
    """Campos editaveis pelo candidato via portal publico."""
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    headline: Optional[str] = None
    summary: Optional[str] = None
    experiences: Optional[List[PortalExperience]] = None
    skills_technical: Optional[List[str]] = None


class ImproveRequest(BaseModel):
    field: str  # summary, headline, experience
    experience_index: Optional[int] = None  # necessario se field=experience


class ImproveResponse(BaseModel):
    field: str
    experience_index: Optional[int] = None
    original: Optional[str] = None
    suggestion: Optional[Dict[str, Any]] = None
    rationale: Optional[str] = None
    ai_available: bool = True
    error: Optional[str] = None


class ApplySuggestionRequest(BaseModel):
    field: str  # summary, headline, experience
    experience_index: Optional[int] = None
    value: Any  # string para summary/headline; objeto para experience
