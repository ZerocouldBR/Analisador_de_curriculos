from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Any
from datetime import datetime, date


class CandidateBase(BaseModel):
    full_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    doc_id: Optional[str] = None
    birth_date: Optional[date] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "Brasil"
    professional_title: Optional[str] = None
    professional_summary: Optional[str] = None
    linkedin_url: Optional[str] = None
    photo_url: Optional[str] = None


class CandidateCreate(CandidateBase):
    pass


class CandidateUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    doc_id: Optional[str] = None
    birth_date: Optional[date] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    professional_title: Optional[str] = None
    professional_summary: Optional[str] = None
    linkedin_url: Optional[str] = None
    photo_url: Optional[str] = None


class CandidateResponse(CandidateBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentBase(BaseModel):
    original_filename: str
    mime_type: Optional[str] = None


class DocumentCreate(DocumentBase):
    candidate_id: int
    source_path: str
    sha256_hash: str


class DocumentResponse(DocumentBase):
    id: int
    candidate_id: int
    source_path: str
    sha256_hash: str
    uploaded_at: datetime
    processing_status: Optional[str] = "pending"
    processing_progress: Optional[int] = 0
    processing_message: Optional[str] = None
    processing_error: Optional[str] = None

    class Config:
        from_attributes = True


class DocumentStatusResponse(BaseModel):
    id: int
    processing_status: str
    processing_progress: int
    processing_message: Optional[str] = None
    processing_error: Optional[str] = None

    class Config:
        from_attributes = True


class ExternalEnrichmentBase(BaseModel):
    source: str
    source_url: Optional[str] = None
    data_json: Any
    retention_policy: Optional[str] = None
    notes: Optional[str] = None


class ExternalEnrichmentCreate(ExternalEnrichmentBase):
    candidate_id: int


class ExternalEnrichmentResponse(ExternalEnrichmentBase):
    id: int
    candidate_id: int
    fetched_at: datetime

    class Config:
        from_attributes = True


class LinkedInProfile(BaseModel):
    """Schema para dados extraídos do LinkedIn"""
    profile_url: str
    full_name: Optional[str] = None
    headline: Optional[str] = None
    location: Optional[str] = None
    about: Optional[str] = None
    experiences: Optional[list[dict]] = None
    education: Optional[list[dict]] = None
    skills: Optional[list[str]] = None
    certifications: Optional[list[dict]] = None
    languages: Optional[list[dict]] = None
