from datetime import datetime, timezone

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
from app.core.config import settings


def _utcnow():
    """Returns timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class Company(Base):
    """Empresa/Tenant - cada empresa ve apenas seus proprios curriculos"""
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    cnpj = Column(String, unique=True, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    logo_url = Column(String, nullable=True)  # Caminho do logo
    website = Column(String, nullable=True)
    plan = Column(String, default="free")  # free, basic, pro, enterprise
    is_active = Column(Boolean, default=True)
    settings_json = Column(JSONB, default=dict)  # Config personalizada da empresa
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relacionamentos
    users = relationship("User", back_populates="company")
    candidates = relationship("Candidate", back_populates="company")
    ai_usage_logs = relationship("AIUsageLog", back_populates="company", cascade="all, delete-orphan")
    sourcing_configs = relationship("ProviderConfig", back_populates="company", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_company_active", "is_active"),
    )


class AIUsageLog(Base):
    """Registro de uso e custos de IA por empresa/usuario"""
    __tablename__ = "ai_usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    operation = Column(String, nullable=False)  # embedding, chat, llm_query, job_analysis
    model = Column(String, nullable=True)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    cost_local = Column(Float, default=0.0)  # Custo em moeda local
    currency = Column(String, default="USD")
    metadata_json = Column(JSONB, nullable=True)  # detalhes adicionais
    created_at = Column(DateTime, default=_utcnow)

    # Relacionamentos
    company = relationship("Company", back_populates="ai_usage_logs")
    user = relationship("User", back_populates="ai_usage_logs")

    __table_args__ = (
        Index("idx_ai_usage_company_date", "company_id", "created_at"),
        Index("idx_ai_usage_operation", "operation"),
    )


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
    permissions = Column(JSONB, default=dict)  # Armazena permissões granulares
    created_at = Column(DateTime, default=_utcnow)

    # Relacionamentos
    users = relationship("User", secondary=user_roles, back_populates="roles")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=False)
    status = Column(String, default="active")  # active, inactive, suspended
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)
    last_login = Column(DateTime, nullable=True)

    # Relacionamentos
    company = relationship("Company", back_populates="users")
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    audit_logs = relationship("AuditLog", back_populates="user")
    conversations = relationship("ChatConversation", back_populates="user", cascade="all, delete-orphan")
    ai_usage_logs = relationship("AIUsageLog", back_populates="user")


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
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
    company = relationship("Company", back_populates="candidates")
    profiles = relationship("CandidateProfile", back_populates="candidate", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="candidate", cascade="all, delete-orphan")
    chunks = relationship("Chunk", back_populates="candidate", cascade="all, delete-orphan")
    experiences = relationship("Experience", back_populates="candidate", cascade="all, delete-orphan")
    consents = relationship("Consent", back_populates="candidate", cascade="all, delete-orphan")
    external_enrichments = relationship("ExternalEnrichment", back_populates="candidate", cascade="all, delete-orphan")
    encrypted_pii = relationship("EncryptedPII", back_populates="candidate", uselist=False, cascade="all, delete-orphan")
    sources = relationship("CandidateSource", back_populates="candidate", cascade="all, delete-orphan")


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
    sha256_hash = Column(String, index=True)  # Indexado para deduplicação (não unique: mesmo arquivo pode ser associado a candidatos diferentes)
    uploaded_at = Column(DateTime, default=_utcnow)

    # Processing status tracking
    processing_status = Column(String, default="pending", index=True)  # pending, processing, completed, error
    processing_progress = Column(Integer, default=0)  # 0-100
    processing_message = Column(String, nullable=True)
    processing_error = Column(Text, nullable=True)
    processing_started_at = Column(DateTime, nullable=True)
    processing_completed_at = Column(DateTime, nullable=True)

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
    model = Column(String)
    vector = Column(Vector(settings.active_embedding_dimensions))  # Dimensao configurada via EMBEDDING_DIMENSIONS/EMBEDDING_MODE
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


class ChatConversation(Base):
    """Conversas do chat de analise de curriculos"""
    __tablename__ = "chat_conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, default="Nova Conversa")
    job_description = Column(Text, nullable=True)
    job_title = Column(String, nullable=True)
    domain = Column(String, default="general")  # production, logistics, quality, general
    status = Column(String, default="active")  # active, archived
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relacionamentos
    user = relationship("User", back_populates="conversations")
    messages = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan",
                          order_by="ChatMessage.created_at")

    __table_args__ = (
        Index("idx_chat_conversation_user", "user_id", "status"),
    )


class ChatMessage(Base):
    """Mensagens individuais do chat"""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    metadata_json = Column(JSONB, nullable=True)  # sources, candidates_mentioned, confidence, etc.
    tokens_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)

    # Relacionamentos
    conversation = relationship("ChatConversation", back_populates="messages")

    __table_args__ = (
        Index("idx_chat_message_conversation", "conversation_id", "created_at"),
    )


class LinkedInSearch(Base):
    """Historico de buscas no LinkedIn"""
    __tablename__ = "linkedin_searches"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    search_criteria = Column(JSONB, nullable=False)  # keywords, location, title, skills, etc.
    results_count = Column(Integer, default=0)
    results_json = Column(JSONB, nullable=True)
    status = Column(String, default="pending")  # pending, completed, failed
    created_at = Column(DateTime, default=_utcnow)

    __table_args__ = (
        Index("idx_linkedin_search_user", "user_id", "created_at"),
    )


class EncryptedPII(Base):
    """Dados pessoais sensíveis criptografados (LGPD)"""
    __tablename__ = "encrypted_pii"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, unique=True)
    cpf_encrypted = Column(Text, nullable=True)
    rg_encrypted = Column(Text, nullable=True)
    birth_date_encrypted = Column(Text, nullable=True)
    address_encrypted = Column(Text, nullable=True)
    phone_encrypted = Column(Text, nullable=True)
    extra_pii_json = Column(Text, nullable=True)  # JSONB criptografado como texto
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relacionamentos
    candidate = relationship("Candidate", back_populates="encrypted_pii")


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


# ================================================================
# Sourcing Hibrido - Modelos para multi-source candidate management
# ================================================================

class CandidateSource(Base):
    """Registro de cada fonte de dados de um candidato"""
    __tablename__ = "candidate_sources"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    provider_name = Column(String, nullable=False)
    provider_type = Column(String, nullable=False)  # api, file, manual, webhook
    external_id = Column(String, nullable=True)
    external_url = Column(String, nullable=True)
    sync_enabled = Column(Boolean, default=True)
    consent_status = Column(String, default="pending")  # pending, granted, revoked
    source_priority = Column(Integer, default=50)  # 0-100, maior = mais prioritario
    source_confidence = Column(Float, default=0.5)  # 0.0-1.0
    last_sync_at = Column(DateTime, nullable=True)
    last_status = Column(String, nullable=True)  # success, error, skipped
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relacionamentos
    candidate = relationship("Candidate", back_populates="sources")
    company = relationship("Company")
    snapshots = relationship("CandidateSnapshot", back_populates="source", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_source_company_provider", "company_id", "provider_name"),
        Index("idx_source_company_candidate", "company_id", "candidate_id"),
        Index("idx_source_unique_external", "company_id", "provider_name", "external_id", unique=True),
    )


class CandidateSnapshot(Base):
    """Snapshot versionado do perfil canonico do candidato"""
    __tablename__ = "candidate_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    source_id = Column(Integer, ForeignKey("candidate_sources.id", ondelete="SET NULL"), nullable=True)
    snapshot_hash = Column(String, index=True, nullable=False)
    canonical_json = Column(JSONB, nullable=False)
    extracted_text = Column(Text, nullable=True)
    embedding_version = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    # Relacionamentos
    source = relationship("CandidateSource", back_populates="snapshots")
    candidate = relationship("Candidate")
    company = relationship("Company")

    __table_args__ = (
        Index("idx_snapshot_company_candidate", "company_id", "candidate_id"),
    )


class CandidateChangeLog(Base):
    """Registro de diferencas entre snapshots"""
    __tablename__ = "candidate_change_logs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    snapshot_from_id = Column(Integer, ForeignKey("candidate_snapshots.id", ondelete="SET NULL"), nullable=True)
    snapshot_to_id = Column(Integer, ForeignKey("candidate_snapshots.id", ondelete="SET NULL"), nullable=False)
    changed_fields_json = Column(JSONB, nullable=False)
    diff_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    # Relacionamentos
    candidate = relationship("Candidate")
    snapshot_from = relationship("CandidateSnapshot", foreign_keys=[snapshot_from_id])
    snapshot_to = relationship("CandidateSnapshot", foreign_keys=[snapshot_to_id])

    __table_args__ = (
        Index("idx_changelog_candidate", "company_id", "candidate_id"),
        Index("idx_changelog_snapshot_to", "snapshot_to_id"),
    )


class SourcingSyncRun(Base):
    """Registro de cada execucao de sincronizacao"""
    __tablename__ = "sourcing_sync_runs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    provider_name = Column(String, nullable=False)
    run_type = Column(String, nullable=False)  # manual, scheduled, webhook
    status = Column(String, default="pending")  # pending, running, completed, failed
    started_at = Column(DateTime, default=_utcnow)
    finished_at = Column(DateTime, nullable=True)
    total_scanned = Column(Integer, default=0)
    total_created = Column(Integer, default=0)
    total_updated = Column(Integer, default=0)
    total_unchanged = Column(Integer, default=0)
    total_failed = Column(Integer, default=0)
    metadata_json = Column(JSONB, nullable=True)
    error_detail = Column(Text, nullable=True)

    # Relacionamentos
    company = relationship("Company")

    __table_args__ = (
        Index("idx_syncrun_company_provider", "company_id", "provider_name", "started_at"),
    )


class ProviderConfig(Base):
    """Configuracao de provider de sourcing por tenant"""
    __tablename__ = "provider_configs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    provider_name = Column(String, nullable=False)
    is_enabled = Column(Boolean, default=False)
    config_json_encrypted = Column(Text, nullable=True)
    schedule_cron = Column(String, nullable=True, default="0 2 */5 * *")
    rate_limit_rpm = Column(Integer, default=60)
    rate_limit_daily = Column(Integer, default=1000)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relacionamentos
    company = relationship("Company", back_populates="sourcing_configs")


# ================================================================
# Portal do Candidato (Magic Link) - PR2
# ================================================================

class CandidateAccessToken(Base):
    """
    Token de acesso do candidato (magic link).

    O candidato recebe um link com este token e pode ver/editar seu
    proprio perfil sem precisar criar conta. Cada token tem validade
    limitada e pode ser revogado pelo RH.
    """
    __tablename__ = "candidate_access_tokens"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(
        Integer,
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=_utcnow)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    use_count = Column(Integer, default=0)
    revoked_at = Column(DateTime, nullable=True)
    purpose = Column(String, default="self_edit")  # self_edit, apply_with_profile

    candidate = relationship("Candidate")

    __table_args__ = (
        Index("idx_access_token_candidate", "candidate_id"),
    )


# ================================================================
# Vagas publicas (Job Board) - PR1
# ================================================================

class Job(Base):
    """Vaga publicada pela empresa, acessivel via link publico."""
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    slug = Column(String, unique=True, nullable=False, index=True)  # slug publico gerado
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)  # descricao completa (markdown permitido)
    requirements = Column(Text, nullable=True)  # requisitos principais
    responsibilities = Column(Text, nullable=True)  # responsabilidades
    benefits = Column(Text, nullable=True)
    location = Column(String, nullable=True)  # Cidade, UF ou "Remoto"
    employment_type = Column(String, nullable=True)  # CLT, PJ, Estagio, Temporario
    seniority_level = Column(String, nullable=True)  # Junior, Pleno, Senior, Lead
    work_mode = Column(String, nullable=True)  # presencial, remoto, hibrido
    salary_range_min = Column(Float, nullable=True)
    salary_range_max = Column(Float, nullable=True)
    salary_currency = Column(String, default="BRL")
    salary_visible = Column(Boolean, default=False)
    skills_required = Column(JSONB, default=list)  # ["python", "aws"]
    skills_desired = Column(JSONB, default=list)
    is_active = Column(Boolean, default=True, index=True)
    published_at = Column(DateTime, nullable=True)
    closes_at = Column(DateTime, nullable=True)  # data limite
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relacionamentos
    company = relationship("Company")
    applications = relationship("JobApplication", back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_job_company_active", "company_id", "is_active"),
    )


class JobApplication(Base):
    """Aplicacao de um candidato para uma vaga."""
    __tablename__ = "job_applications"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)

    # Dados informados no momento da aplicacao (publica)
    applicant_name = Column(String, nullable=False)
    applicant_email = Column(String, nullable=False, index=True)
    applicant_phone = Column(String, nullable=True)
    cover_letter = Column(Text, nullable=True)

    # Resultado da analise de fit pela IA
    fit_score = Column(Integer, nullable=True)  # 0-100
    fit_analysis = Column(JSONB, nullable=True)  # detalhes estruturados
    fit_status = Column(String, default="pending")  # pending, analyzed, failed

    # Pipeline da vaga (RH gerencia)
    stage = Column(String, default="received", index=True)
    # received, screening, interview, technical, offer, hired, rejected
    stage_notes = Column(Text, nullable=True)

    # Origem
    source = Column(String, default="public_form")  # public_form, manual, import
    consent_given = Column(Boolean, default=False)  # LGPD

    created_at = Column(DateTime, default=_utcnow, index=True)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relacionamentos
    job = relationship("Job", back_populates="applications")
    candidate = relationship("Candidate")
    document = relationship("Document")

    __table_args__ = (
        Index("idx_application_job_stage", "job_id", "stage"),
        Index("idx_application_email_job", "applicant_email", "job_id"),
    )

    __table_args__ = (
        Index("idx_provider_config_unique", "company_id", "provider_name", unique=True),
    )
