"""
Servico de sincronizacao de providers.

Orquestra o fluxo completo de sync: buscar candidatos no provider,
normalizar, deduplicar, criar/atualizar no banco, gerar snapshots.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    AuditLog,
    Candidate,
    CandidateSource,
    ProviderConfig,
    SourcingSyncRun,
)
from app.services.sourcing.candidate_normalizer import CandidateNormalizer
from app.services.sourcing.deduplication_service import DeduplicationService
from app.services.sourcing.candidate_merge_service import CandidateMergeService
from app.services.sourcing.provider_base import CandidateCanonicalProfile
from app.services.sourcing.provider_registry import ProviderRegistry
from app.services.sourcing.snapshot_service import SnapshotService

logger = logging.getLogger(__name__)


class SyncService:
    """Orquestra sincronizacao de providers de sourcing."""

    @staticmethod
    async def sync_provider(
        db: Session,
        company_id: int,
        provider_name: str,
        user_id: Optional[int] = None,
        criteria: Optional[Dict[str, Any]] = None,
        run_type: str = "manual",
    ) -> SourcingSyncRun:
        """Executa sincronizacao completa de um provider.

        1. Carrega config do provider
        2. Busca candidatos no provider
        3. Para cada resultado: normaliza, deduplicar, criar/atualizar
        4. Gera snapshots
        5. Registra metricas
        """
        provider = ProviderRegistry.get(provider_name)
        if not provider:
            raise ValueError(f"Provider '{provider_name}' nao registrado")

        # Carregar config do tenant
        provider_config = db.query(ProviderConfig).filter(
            ProviderConfig.company_id == company_id,
            ProviderConfig.provider_name == provider_name,
        ).first()

        config = {}
        if provider_config and provider_config.config_json_encrypted:
            try:
                from app.services.encryption_service import EncryptionService
                config = EncryptionService.decrypt_dict(
                    provider_config.config_json_encrypted
                )
            except Exception:
                try:
                    config = json.loads(provider_config.config_json_encrypted)
                except Exception:
                    config = {}

        # Criar registro de sync run
        sync_run = SourcingSyncRun(
            company_id=company_id,
            provider_name=provider_name,
            run_type=run_type,
            status="running",
        )
        db.add(sync_run)
        db.flush()

        try:
            # Buscar candidatos no provider
            search_criteria = criteria or {}
            limit = min(
                search_criteria.get("limit", settings.sourcing_max_sync_candidates),
                settings.sourcing_max_sync_candidates,
            )

            profiles = await provider.search_candidates(
                config=config,
                criteria=search_criteria,
                limit=limit,
            )

            sync_run.total_scanned = len(profiles)

            # Processar cada perfil
            for profile in profiles:
                try:
                    SyncService._process_profile(
                        db=db,
                        company_id=company_id,
                        provider_name=provider_name,
                        profile=profile,
                        sync_run=sync_run,
                    )
                except Exception as e:
                    logger.error(
                        f"Erro processando perfil '{profile.full_name}': {e}"
                    )
                    sync_run.total_failed += 1

            # Atualizar status da config
            if provider_config:
                provider_config.last_sync_at = datetime.now(timezone.utc)

            # Finalizar sync run
            sync_run.status = "completed"
            sync_run.finished_at = datetime.now(timezone.utc)

            # Audit log
            audit = AuditLog(
                user_id=user_id,
                action="sourcing_sync",
                entity="sourcing_sync_run",
                entity_id=sync_run.id,
                metadata_json={
                    "provider": provider_name,
                    "run_type": run_type,
                    "scanned": sync_run.total_scanned,
                    "created": sync_run.total_created,
                    "updated": sync_run.total_updated,
                    "unchanged": sync_run.total_unchanged,
                    "failed": sync_run.total_failed,
                },
            )
            db.add(audit)
            db.commit()

        except Exception as e:
            sync_run.status = "failed"
            sync_run.error_detail = str(e)
            sync_run.finished_at = datetime.now(timezone.utc)
            db.commit()
            logger.error(f"Sync falhou para {provider_name}: {e}")
            raise

        return sync_run

    @staticmethod
    def _process_profile(
        db: Session,
        company_id: int,
        provider_name: str,
        profile: CandidateCanonicalProfile,
        sync_run: SourcingSyncRun,
    ) -> None:
        """Processa um perfil individual: dedup, create/update, snapshot."""
        # Buscar duplicatas
        duplicates = DeduplicationService.find_duplicates(
            db=db,
            profile=profile,
            company_id=company_id,
        )

        if duplicates:
            # Candidato existente encontrado
            best_match = duplicates[0]
            candidate_id = best_match["candidate_id"]

            # Verificar se ja tem source para esse provider
            existing_source = db.query(CandidateSource).filter(
                CandidateSource.candidate_id == candidate_id,
                CandidateSource.company_id == company_id,
                CandidateSource.provider_name == provider_name,
            ).first()

            if existing_source:
                # Atualizar source existente
                existing_source.last_sync_at = datetime.now(timezone.utc)
                existing_source.last_status = "success"
                existing_source.source_confidence = profile.confidence

                if profile.external_id:
                    existing_source.external_id = profile.external_id
                if profile.external_url:
                    existing_source.external_url = profile.external_url

                source_id = existing_source.id
            else:
                # Criar nova source para o candidato
                new_source = CandidateSource(
                    company_id=company_id,
                    candidate_id=candidate_id,
                    provider_name=provider_name,
                    provider_type=ProviderRegistry.get(provider_name).provider_type.value,
                    external_id=profile.external_id,
                    external_url=profile.external_url,
                    source_confidence=profile.confidence,
                    last_sync_at=datetime.now(timezone.utc),
                    last_status="success",
                )
                db.add(new_source)
                db.flush()
                source_id = new_source.id

            # Atualizar candidato com dados mergeados
            CandidateMergeService.apply_merge_to_candidate(
                db=db,
                candidate_id=candidate_id,
                merged_profile=profile,
            )

            # Criar snapshot
            snapshot = SnapshotService.create_snapshot(
                db=db,
                candidate_id=candidate_id,
                company_id=company_id,
                source_id=source_id,
                canonical=profile,
            )

            # Verificar se houve mudanca
            latest = SnapshotService.get_latest_snapshot(db, candidate_id, company_id)
            if latest and latest.id == snapshot.id and snapshot.snapshot_hash != (
                getattr(latest, '_prev_hash', None)
            ):
                sync_run.total_updated += 1
            else:
                sync_run.total_unchanged += 1

        else:
            # Candidato novo
            candidate_data = CandidateNormalizer.to_candidate_dict(profile)
            candidate = Candidate(
                company_id=company_id,
                **candidate_data,
            )
            db.add(candidate)
            db.flush()

            # Criar source
            source = CandidateSource(
                company_id=company_id,
                candidate_id=candidate.id,
                provider_name=provider_name,
                provider_type=ProviderRegistry.get(provider_name).provider_type.value,
                external_id=profile.external_id,
                external_url=profile.external_url,
                source_confidence=profile.confidence,
                last_sync_at=datetime.now(timezone.utc),
                last_status="success",
            )
            db.add(source)
            db.flush()

            # Criar snapshot inicial
            SnapshotService.create_snapshot(
                db=db,
                candidate_id=candidate.id,
                company_id=company_id,
                source_id=source.id,
                canonical=profile,
            )

            sync_run.total_created += 1

    @staticmethod
    async def sync_all_enabled(
        db: Session,
        company_id: int,
        user_id: Optional[int] = None,
    ) -> List[SourcingSyncRun]:
        """Sincroniza todos os providers habilitados de um tenant."""
        configs = db.query(ProviderConfig).filter(
            ProviderConfig.company_id == company_id,
            ProviderConfig.is_enabled == True,  # noqa: E712
        ).all()

        runs = []
        for config in configs:
            try:
                run = await SyncService.sync_provider(
                    db=db,
                    company_id=company_id,
                    provider_name=config.provider_name,
                    user_id=user_id,
                    run_type="scheduled",
                )
                runs.append(run)
            except Exception as e:
                logger.error(
                    f"Erro ao sincronizar {config.provider_name} "
                    f"para company_id={company_id}: {e}"
                )
        return runs

    @staticmethod
    def get_sync_runs(
        db: Session,
        company_id: int,
        provider_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[SourcingSyncRun]:
        """Lista execucoes de sincronizacao."""
        query = db.query(SourcingSyncRun).filter(
            SourcingSyncRun.company_id == company_id,
        )

        if provider_name:
            query = query.filter(SourcingSyncRun.provider_name == provider_name)
        if status:
            query = query.filter(SourcingSyncRun.status == status)

        return query.order_by(desc(SourcingSyncRun.started_at)).limit(limit).all()

    @staticmethod
    def get_sync_run_detail(
        db: Session, run_id: int, company_id: int
    ) -> Optional[SourcingSyncRun]:
        """Retorna detalhes de uma execucao de sync."""
        return db.query(SourcingSyncRun).filter(
            SourcingSyncRun.id == run_id,
            SourcingSyncRun.company_id == company_id,
        ).first()
