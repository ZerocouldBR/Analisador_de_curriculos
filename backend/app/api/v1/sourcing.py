"""
Endpoints REST para o modulo de sourcing hibrido.
"""
import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_permission
from app.db.database import get_db
from app.db.models import (
    AuditLog,
    CandidateSource,
    ProviderConfig,
    User,
)
from app.schemas.sourcing import (
    CandidateSourceResponse,
    HybridSourcingSearchRequest,
    HybridSourcingSearchResult,
    MergeExecuteRequest,
    MergeSuggestionResponse,
    ProviderConfigCreate,
    ProviderConfigResponse,
    ProviderInfoResponse,
    ProviderStatusResponse,
    ProviderSyncRequest,
    ProviderTestResponse,
    SnapshotDiffResponse,
    SnapshotSummaryResponse,
    SyncRunResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sourcing", tags=["sourcing"])


# ================================================================
# Providers
# ================================================================

@router.get("/providers", response_model=List[ProviderInfoResponse])
def list_providers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista todos os providers registrados com status para o tenant."""
    from app.services.sourcing.provider_registry import ProviderRegistry

    company_id = current_user.company_id
    providers = ProviderRegistry.list_all()
    result = []

    for provider in providers:
        config = None
        if company_id:
            config = db.query(ProviderConfig).filter(
                ProviderConfig.company_id == company_id,
                ProviderConfig.provider_name == provider.provider_name,
            ).first()

        result.append(ProviderInfoResponse(
            name=provider.provider_name,
            type=provider.provider_type.value,
            is_configured=config is not None,
            is_enabled=config.is_enabled if config else False,
            last_sync_at=getattr(config, 'updated_at', None) if config else None,
        ))

    return result


@router.get("/providers/{provider_name}/status", response_model=ProviderStatusResponse)
async def get_provider_status(
    provider_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Health check de um provider."""
    from app.services.sourcing.provider_registry import ProviderRegistry

    provider = ProviderRegistry.get(provider_name)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider '{provider_name}' nao encontrado",
        )

    config = {}
    if current_user.company_id:
        provider_config = db.query(ProviderConfig).filter(
            ProviderConfig.company_id == current_user.company_id,
            ProviderConfig.provider_name == provider_name,
        ).first()

        if provider_config and provider_config.config_json_encrypted:
            try:
                config = json.loads(provider_config.config_json_encrypted)
            except Exception:
                config = {}

    health = await provider.health_check(config)

    return ProviderStatusResponse(
        provider_name=provider_name,
        healthy=health.healthy,
        message=health.message,
        remaining_quota=health.remaining_quota,
        metadata=health.metadata,
    )


@router.post("/providers/config", response_model=ProviderConfigResponse)
def upsert_provider_config(
    data: ProviderConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("sourcing.config")),
):
    """Criar ou atualizar configuracao de provider."""
    from app.services.sourcing.provider_registry import ProviderRegistry

    if not ProviderRegistry.is_registered(data.provider_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider '{data.provider_name}' nao registrado",
        )

    company_id = current_user.company_id
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario sem empresa associada",
        )

    # Criptografar config
    config_encrypted = json.dumps(data.config_json)
    try:
        from app.services.encryption_service import EncryptionService
        config_encrypted = EncryptionService.encrypt_dict(data.config_json)
    except Exception:
        pass

    existing = db.query(ProviderConfig).filter(
        ProviderConfig.company_id == company_id,
        ProviderConfig.provider_name == data.provider_name,
    ).first()

    if existing:
        existing.is_enabled = data.is_enabled
        existing.config_json_encrypted = config_encrypted
        existing.schedule_cron = data.schedule_cron
        existing.rate_limit_rpm = data.rate_limit_rpm
        existing.rate_limit_daily = data.rate_limit_daily
        provider_config = existing
    else:
        provider_config = ProviderConfig(
            company_id=company_id,
            provider_name=data.provider_name,
            is_enabled=data.is_enabled,
            config_json_encrypted=config_encrypted,
            schedule_cron=data.schedule_cron,
            rate_limit_rpm=data.rate_limit_rpm,
            rate_limit_daily=data.rate_limit_daily,
        )
        db.add(provider_config)

    db.commit()
    db.refresh(provider_config)

    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="sourcing_config_upsert",
        entity="provider_config",
        entity_id=provider_config.id,
        metadata_json={
            "provider_name": data.provider_name,
            "is_enabled": data.is_enabled,
        },
    )
    db.add(audit)
    db.commit()

    return ProviderConfigResponse(
        id=provider_config.id,
        provider_name=provider_config.provider_name,
        is_enabled=provider_config.is_enabled,
        schedule_cron=provider_config.schedule_cron,
        rate_limit_rpm=provider_config.rate_limit_rpm,
        rate_limit_daily=provider_config.rate_limit_daily,
        config_keys=list(data.config_json.keys()),
        created_at=provider_config.created_at,
        updated_at=provider_config.updated_at,
    )


@router.post("/providers/{provider_name}/test", response_model=ProviderTestResponse)
async def test_provider(
    provider_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Testar conexao com um provider."""
    from app.services.sourcing.provider_registry import ProviderRegistry

    provider = ProviderRegistry.get(provider_name)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider '{provider_name}' nao encontrado",
        )

    config = {}
    if current_user.company_id:
        provider_config = db.query(ProviderConfig).filter(
            ProviderConfig.company_id == current_user.company_id,
            ProviderConfig.provider_name == provider_name,
        ).first()
        if provider_config and provider_config.config_json_encrypted:
            try:
                config = json.loads(provider_config.config_json_encrypted)
            except Exception:
                config = {}

    health = await provider.health_check(config)

    return ProviderTestResponse(
        healthy=health.healthy,
        message=health.message,
        remaining_quota=health.remaining_quota,
    )


@router.post("/providers/{provider_name}/sync")
def trigger_sync(
    provider_name: str,
    data: Optional[ProviderSyncRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("sourcing.sync")),
):
    """Dispara sincronizacao manual de um provider."""
    from app.services.sourcing.provider_registry import ProviderRegistry
    from app.tasks.sourcing_tasks import sync_provider_task

    if not ProviderRegistry.is_registered(provider_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider '{provider_name}' nao registrado",
        )

    company_id = current_user.company_id
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario sem empresa associada",
        )

    criteria = data.criteria if data else None

    task = sync_provider_task.delay(
        company_id=company_id,
        provider_name=provider_name,
        user_id=current_user.id,
        criteria=criteria,
        run_type="manual",
    )

    return {
        "message": f"Sincronizacao de '{provider_name}' iniciada",
        "task_id": task.id,
    }


# ================================================================
# Sync Runs
# ================================================================

@router.get("/runs", response_model=List[SyncRunResponse])
def list_sync_runs(
    provider_name: Optional[str] = Query(None),
    run_status: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista execucoes de sincronizacao."""
    from app.services.sourcing.sync_service import SyncService

    company_id = current_user.company_id
    if not company_id:
        return []

    runs = SyncService.get_sync_runs(
        db=db,
        company_id=company_id,
        provider_name=provider_name,
        status=run_status,
        limit=limit,
    )

    return [SyncRunResponse.model_validate(r) for r in runs]


@router.get("/runs/{run_id}", response_model=SyncRunResponse)
def get_sync_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Detalhes de uma execucao de sync."""
    from app.services.sourcing.sync_service import SyncService

    company_id = current_user.company_id
    if not company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    run = SyncService.get_sync_run_detail(db, run_id, company_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sync run nao encontrado",
        )

    return SyncRunResponse.model_validate(run)


# ================================================================
# Candidate Sources
# ================================================================

@router.get(
    "/candidates/{candidate_id}/sources",
    response_model=List[CandidateSourceResponse],
)
def get_candidate_sources(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista fontes de dados de um candidato."""
    company_id = current_user.company_id
    if not company_id:
        return []

    sources = db.query(CandidateSource).filter(
        CandidateSource.candidate_id == candidate_id,
        CandidateSource.company_id == company_id,
    ).all()

    return [CandidateSourceResponse.model_validate(s) for s in sources]


# ================================================================
# Snapshots
# ================================================================

@router.get(
    "/candidates/{candidate_id}/snapshots",
    response_model=List[SnapshotSummaryResponse],
)
def list_snapshots(
    candidate_id: int,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista snapshots de um candidato."""
    from app.services.sourcing.snapshot_service import SnapshotService

    company_id = current_user.company_id
    if not company_id:
        return []

    snapshots = SnapshotService.list_snapshots(
        db=db, candidate_id=candidate_id, company_id=company_id, limit=limit
    )

    return [SnapshotSummaryResponse.model_validate(s) for s in snapshots]


@router.get("/candidates/{candidate_id}/snapshots/diff")
def get_snapshot_diff(
    candidate_id: int,
    from_id: int = Query(...),
    to_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Diferenca entre dois snapshots."""
    from app.services.sourcing.snapshot_service import SnapshotService

    company_id = current_user.company_id
    if not company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    diff = SnapshotService.get_diff_between(
        db=db,
        candidate_id=candidate_id,
        company_id=company_id,
        from_snapshot_id=from_id,
        to_snapshot_id=to_id,
    )

    if diff is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Snapshots nao encontrados",
        )

    return diff


# ================================================================
# Hybrid Search
# ================================================================

@router.post("/search", response_model=List[HybridSourcingSearchResult])
def hybrid_sourcing_search(
    data: HybridSourcingSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Busca hibrida na base interna filtrada por providers."""
    from sqlalchemy import or_, func
    from app.db.models import Candidate

    company_id = current_user.company_id
    if not company_id:
        return []

    query = db.query(Candidate).filter(Candidate.company_id == company_id)

    search_text = data.query.lower()
    query = query.filter(
        or_(
            func.lower(Candidate.full_name).contains(search_text),
            func.lower(Candidate.email).contains(search_text),
            func.lower(Candidate.city).contains(search_text),
        )
    )

    # Filtrar por providers se especificado
    if data.providers:
        candidate_ids_with_source = db.query(CandidateSource.candidate_id).filter(
            CandidateSource.company_id == company_id,
            CandidateSource.provider_name.in_(data.providers),
        ).distinct().all()
        candidate_ids = [cid for (cid,) in candidate_ids_with_source]
        if candidate_ids:
            query = query.filter(Candidate.id.in_(candidate_ids))
        else:
            return []

    candidates = query.limit(data.limit).all()

    results = []
    for candidate in candidates:
        score = 0.0
        matched = []

        if search_text in (candidate.full_name or "").lower():
            score += 0.6
            matched.append("Nome")
        if search_text in (candidate.email or "").lower():
            score += 0.3
            matched.append("Email")
        if search_text in (candidate.city or "").lower():
            score += 0.1
            matched.append("Cidade")

        # Buscar sources do candidato
        sources = db.query(CandidateSource).filter(
            CandidateSource.candidate_id == candidate.id,
            CandidateSource.company_id == company_id,
        ).all()

        source_names = [s.provider_name for s in sources]
        external_url = None
        for s in sources:
            if s.external_url:
                external_url = s.external_url
                break

        results.append(HybridSourcingSearchResult(
            candidate_id=candidate.id,
            name=candidate.full_name,
            score=round(score, 2),
            source=", ".join(source_names) if source_names else "interno",
            external_url=external_url,
            matched_details=matched,
        ))

    results.sort(key=lambda x: x.score, reverse=True)
    return results


# ================================================================
# Merge Suggestions
# ================================================================

@router.get("/merge-suggestions", response_model=List[MergeSuggestionResponse])
def get_merge_suggestions(
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista sugestoes de merge entre candidatos."""
    from app.services.sourcing.deduplication_service import DeduplicationService

    company_id = current_user.company_id
    if not company_id:
        return []

    suggestions = DeduplicationService.suggest_merges(
        db=db, company_id=company_id, limit=limit
    )

    return [MergeSuggestionResponse(**s) for s in suggestions]


@router.post("/merge")
def execute_merge(
    data: MergeExecuteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("sourcing.merge")),
):
    """Executa merge de dois candidatos."""
    from app.services.sourcing.candidate_merge_service import CandidateMergeService

    company_id = current_user.company_id
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario sem empresa associada",
        )

    result = CandidateMergeService.execute_candidate_merge(
        db=db,
        primary_candidate_id=data.primary_candidate_id,
        secondary_candidate_id=data.secondary_candidate_id,
        company_id=company_id,
        user_id=current_user.id,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidatos nao encontrados",
        )

    db.commit()

    return {
        "message": "Merge executado com sucesso",
        "primary_candidate_id": data.primary_candidate_id,
        "secondary_candidate_id": data.secondary_candidate_id,
    }
