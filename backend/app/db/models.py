from datetime import datetime, timezone


def _utcnow():
    """Returns timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Boolean,
    Date,
    Float,
    Index,
    Table,
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.db.database import Base


# Tabela de associação User-Role (many-to-many)
user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('role_id', Integer, ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
    Column('assigned_at', DateTime, default=_utcnow)
)


class Role(Base):
    """Roles para RBAC (Role-Based Access Control)"""
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    description = Column(Text)
    permissions = Column(JSONB, default={})  # Armazena permissões granulares
    created_at = Column(DateTime, default=_utcnow)

    # Relacionamentos
    users = relationship("User", secondary=user_roles, back_populates="roles")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=False)
    status = Column(String, default="active")  # active, inactive, suspended
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)
    last_login = Column(DateTime, nullable=True)

    # Relacionamentos
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    audit_logs = relationship("AuditLog", back_populates="user")


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, index=True)
    phone = Column(String)
    doc_id = Column(String)  # CPF ou outro documento
    birth_date = Column(Date, nullable=True)
    address = Column(Text)
    city = Column(String, index=True)
    state = Column(String, index=True)
    country = Column(String, default="Brasil")
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relacionamentos
    profiles = relationship("CandidateProfile", back_populates="candidate", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="candidate", cascade="all, delete-orphan")
    chunks = relationship("Chunk", back_populates="candidate", cascade="all, delete-orphan")
    experiences = relationship("Experience", back_populates="candidate", cascade="all, delete-orphan")
    consents = relationship("Consent", back_populates="candidate", cascade="all, delete-orphan")
    external_enrichments = relationship("ExternalEnrichment", back_populates="candidate", cascade="all, delete-orphan")


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, default=1)
    profile_json = Column(JSONB, nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    # Relacionamentos
    candidate = relationship("Candidate", back_populates="profiles")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    original_filename = Column(String, nullable=False)
    mime_type = Column(String)
    source_path = Column(String)  # Caminho no NAS/MinIO
    sha256_hash = Column(String, unique=True, index=True)  # Para deduplicação
    uploaded_at = Column(DateTime, default=_utcnow)

    # Relacionamentos
    candidate = relationship("Candidate", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    section = Column(String, index=True)  # experiência, formação, skills, etc.
    content = Column(Text, nullable=False)
    meta_json = Column(JSONB)
    created_at = Column(DateTime, default=_utcnow)

    # Relacionamentos
    document = relationship("Document", back_populates="chunks")
    candidate = relationship("Candidate", back_populates="chunks")
    embeddings = relationship("Embedding", back_populates="chunk", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_chunk_section_candidate", "section", "candidate_id"),
    )


class Embedding(Base):
    __tablename__ = "embeddings"

    id = Column(Integer, primary_key=True, index=True)
    chunk_id = Column(Integer, ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False)
    model = Column(String, default="text-embedding-3-small")
    vector = Column(Vector(1536))  # Dimensão padrão do OpenAI embedding
    created_at = Column(DateTime, default=_utcnow)

    # Relacionamentos
    chunk = relationship("Chunk", back_populates="embeddings")


class Experience(Base):
    __tablename__ = "experiences"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    company_name = Column(String)
    title = Column(String)
    start_date = Column(Date)
    end_date = Column(Date, nullable=True)
    industry = Column(String)
    description = Column(Text)
    created_at = Column(DateTime, default=_utcnow)

    # Relacionamentos
    candidate = relationship("Candidate", back_populates="experiences")


class Consent(Base):
    __tablename__ = "consents"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    consent_type = Column(String, nullable=False)
    legal_basis = Column(String)
    granted_at = Column(DateTime, default=_utcnow)
    expires_at = Column(DateTime, nullable=True)

    # Relacionamentos
    candidate = relationship("Candidate", back_populates="consents")


class ExternalEnrichment(Base):
    """Armazena dados de enriquecimento externo, como LinkedIn"""
    __tablename__ = "external_enrichments"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    source = Column(String, nullable=False)  # "linkedin", "github", etc.
    source_url = Column(String)
    data_json = Column(JSONB)  # Dados extraídos do LinkedIn
    fetched_at = Column(DateTime, default=_utcnow)
    retention_policy = Column(String)
    notes = Column(Text)

    # Relacionamentos
    candidate = relationship("Candidate", back_populates="external_enrichments")

    __table_args__ = (
        Index("idx_enrichment_source_candidate", "source", "candidate_id"),
    )


class ServerSettings(Base):
    """Configurações do servidor, incluindo prompts do chat LLM"""
    __tablename__ = "server_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    value_json = Column(JSONB, nullable=False)
    description = Column(Text)
    version = Column(Integer, default=1)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class AuditLog(Base):
    """Log de auditoria para compliance LGPD"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)
    entity = Column(String, nullable=False)
    entity_id = Column(Integer)
    metadata_json = Column(JSONB)
    created_at = Column(DateTime, default=_utcnow, index=True)

    # Relacionamentos
    user = relationship("User", back_populates="audit_logs")
