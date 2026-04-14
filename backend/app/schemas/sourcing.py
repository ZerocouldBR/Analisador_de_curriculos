"""
Schemas Pydantic para o modulo de sourcing hibrido.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ================================================================
# Provider Schemas
# ================================================================

class ProviderInfoResponse(BaseModel):
    """Informacoes de um provider registrado."""
    name: str
    type: str
    is_configured: bool = False
    is_enabled: bool = False
    last_sync_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProviderStatusResponse(BaseModel):
    """Status de saude de um provider."""
    provider_name: str
    healthy: bool
    message: str
    remaining_quota: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class ProviderConfigCreate(BaseModel):
    """Criar ou atualizar configuracao de provider."""
    provider_name: str
    is_enabled: bool = False
    config_json: Dict[str, Any] = Field(default_factory=dict)
    schedule_cron: Optional[str] = "0 2 */5 * *"
    rate_limit_rpm: int = 60
    rate_limit_daily: int = 1000


class ProviderConfigResponse(BaseModel):
    """Configuracao de provider (sem dados sensiveis)."""
    id: int
    provider_name: str
    is_enabled: bool
    schedule_cron: Optional[str]
    rate_limit_rpm: int
    rate_limit_daily: int
    config_keys: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProviderTestRequest(BaseModel):
    """Request para testar conexao de provider."""
    config_json: Optional[Dict[str, Any]] = None


class ProviderTestResponse(BaseModel):
    """Response do teste de conexao."""
    healthy: bool
    message: str
    remaining_quota: Optional[int] = None


class ProviderSyncRequest(BaseModel):
    """Request para disparar sync manual."""
    criteria: Optional[Dict[str, Any]] = None


# ================================================================
# Sync Run Schemas
# ================================================================

class SyncRunResponse(BaseModel):
    """Resumo de uma execucao de sync."""
    id: int
    provider_name: str
    run_type: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    total_scanned: int = 0
    total_created: int = 0
    total_updated: int = 0
    total_unchanged: int = 0
    total_failed: int = 0
    error_detail: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


# ================================================================
# Candidate Source Schemas
# ================================================================

class CandidateSourceResponse(BaseModel):
    """Fonte de dados de um candidato."""
    id: int
    provider_name: str
    provider_type: str
    external_id: Optional[str] = None
    external_url: Optional[str] = None
    sync_enabled: bool
    consent_status: str
    source_priority: int
    source_confidence: float
    last_sync_at: Optional[datetime] = None
    last_status: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ================================================================
# Snapshot Schemas
# ================================================================

class SnapshotSummaryResponse(BaseModel):
    """Resumo de um snapshot."""
    id: int
    snapshot_hash: str
    source_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SnapshotDiffResponse(BaseModel):
    """Diferenca entre dois snapshots."""
    from_snapshot_id: Optional[int] = None
    to_snapshot_id: int
    changed_fields: Dict[str, Any]
    diff_summary: str
    created_at: datetime

    class Config:
        from_attributes = True


class SnapshotDiffRequest(BaseModel):
    """Request para obter diff entre dois snapshots."""
    from_id: int
    to_id: int


# ================================================================
# Hybrid Search Schemas
# ================================================================

class HybridSourcingSearchRequest(BaseModel):
    """Request para busca hibrida."""
    query: str
    providers: Optional[List[str]] = None
    filters: Optional[Dict[str, Any]] = None
    limit: int = 20


class HybridSourcingSearchResult(BaseModel):
    """Resultado de busca hibrida."""
    candidate_id: Optional[int] = None
    name: str
    score: float
    source: str
    external_url: Optional[str] = None
    matched_details: List[str] = Field(default_factory=list)


# ================================================================
# Merge Suggestion Schemas
# ================================================================

class MergeSuggestionResponse(BaseModel):
    """Sugestao de merge entre candidatos."""
    candidate_id_a: int
    candidate_id_b: int
    name_a: str
    name_b: str
    similarity_score: float
    matched_fields: List[str]


class MergeExecuteRequest(BaseModel):
    """Request para executar merge."""
    primary_candidate_id: int
    secondary_candidate_id: int
