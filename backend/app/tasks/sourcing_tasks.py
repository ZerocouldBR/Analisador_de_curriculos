"""
Celery tasks para sourcing hibrido.

Tasks asincronas para sincronizacao de providers,
refresh de perfis e health checks noturnos.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from celery import Task
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import ProviderConfig, SourcingSyncRun

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Base task que fornece sessao de banco de dados."""
    _db: Session = None

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="app.tasks.sourcing_tasks.sync_provider_task",
)
def sync_provider_task(
    self,
    company_id: int,
    provider_name: str,
    user_id: Optional[int] = None,
    criteria: Optional[dict] = None,
    run_type: str = "manual",
):
    """Task assincrona para sincronizar um provider."""
    from app.services.sourcing.sync_service import SyncService

    logger.info(
        f"Iniciando sync: provider={provider_name}, "
        f"company_id={company_id}, run_type={run_type}"
    )

    try:
        run = asyncio.run(
            SyncService.sync_provider(
                db=self.db,
                company_id=company_id,
                provider_name=provider_name,
                user_id=user_id,
                criteria=criteria,
                run_type=run_type,
            )
        )

        logger.info(
            f"Sync concluido: provider={provider_name}, "
            f"created={run.total_created}, updated={run.total_updated}, "
            f"failed={run.total_failed}"
        )

        return {
            "sync_run_id": run.id,
            "status": run.status,
            "total_scanned": run.total_scanned,
            "total_created": run.total_created,
            "total_updated": run.total_updated,
            "total_failed": run.total_failed,
        }

    except Exception as e:
        logger.error(f"Erro no sync_provider_task: {e}")
        raise


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="app.tasks.sourcing_tasks.sync_all_enabled_providers_task",
)
def sync_all_enabled_providers_task(
    self,
    company_id: int,
    user_id: Optional[int] = None,
):
    """Task para sincronizar todos os providers habilitados de um tenant."""
    from app.services.sourcing.sync_service import SyncService

    logger.info(f"Sync all enabled providers: company_id={company_id}")

    try:
        runs = asyncio.run(
            SyncService.sync_all_enabled(
                db=self.db,
                company_id=company_id,
                user_id=user_id,
            )
        )

        return {
            "company_id": company_id,
            "providers_synced": len(runs),
            "runs": [
                {
                    "provider": r.provider_name,
                    "status": r.status,
                    "created": r.total_created,
                    "updated": r.total_updated,
                }
                for r in runs
            ],
        }

    except Exception as e:
        logger.error(f"Erro no sync_all_enabled_providers_task: {e}")
        raise


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="app.tasks.sourcing_tasks.refresh_candidate_profiles_task",
)
def refresh_candidate_profiles_task(
    self,
    company_id: int,
    candidate_ids: List[int],
):
    """Re-busca dados externos para candidatos especificos."""
    from app.services.sourcing.sync_service import SyncService
    from app.db.models import CandidateSource

    logger.info(
        f"Refresh profiles: company_id={company_id}, "
        f"candidates={len(candidate_ids)}"
    )

    refreshed = 0
    for candidate_id in candidate_ids:
        sources = self.db.query(CandidateSource).filter(
            CandidateSource.candidate_id == candidate_id,
            CandidateSource.company_id == company_id,
            CandidateSource.sync_enabled == True,  # noqa: E712
        ).all()

        for source in sources:
            try:
                sync_provider_task.delay(
                    company_id=company_id,
                    provider_name=source.provider_name,
                    run_type="refresh",
                )
                refreshed += 1
            except Exception as e:
                logger.error(
                    f"Erro ao enfileirar refresh para candidate_id={candidate_id}, "
                    f"provider={source.provider_name}: {e}"
                )

    return {"candidates_processed": len(candidate_ids), "tasks_queued": refreshed}


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="app.tasks.sourcing_tasks.nightly_source_healthcheck_task",
)
def nightly_source_healthcheck_task(self):
    """Health check noturno de todos os providers habilitados.

    Verifica saude dos providers e dispara syncs pendentes
    baseado no schedule configurado (default: a cada 5 dias).
    """
    logger.info("Iniciando nightly source healthcheck")

    configs = self.db.query(ProviderConfig).filter(
        ProviderConfig.is_enabled == True,  # noqa: E712
    ).all()

    now = datetime.now(timezone.utc)
    syncs_triggered = 0
    health_results = []

    for config in configs:
        provider_name = config.provider_name
        company_id = config.company_id

        # Verificar se sync esta pendente
        last_sync = self.db.query(SourcingSyncRun).filter(
            SourcingSyncRun.company_id == company_id,
            SourcingSyncRun.provider_name == provider_name,
            SourcingSyncRun.status == "completed",
        ).order_by(SourcingSyncRun.finished_at.desc()).first()

        sync_interval = timedelta(days=settings.sourcing_sync_interval_days)
        should_sync = False

        if not last_sync:
            should_sync = True
        elif last_sync.finished_at:
            if now - last_sync.finished_at >= sync_interval:
                should_sync = True

        if should_sync:
            try:
                sync_provider_task.delay(
                    company_id=company_id,
                    provider_name=provider_name,
                    run_type="scheduled",
                )
                syncs_triggered += 1
                logger.info(
                    f"Sync agendado: provider={provider_name}, "
                    f"company_id={company_id}"
                )
            except Exception as e:
                logger.error(
                    f"Erro ao agendar sync: provider={provider_name}, "
                    f"company_id={company_id}, erro={e}"
                )

        health_results.append({
            "company_id": company_id,
            "provider": provider_name,
            "should_sync": should_sync,
            "last_sync": last_sync.finished_at.isoformat() if last_sync and last_sync.finished_at else None,
        })

    logger.info(
        f"Healthcheck concluido: {len(configs)} configs verificadas, "
        f"{syncs_triggered} syncs agendados"
    )

    return {
        "configs_checked": len(configs),
        "syncs_triggered": syncs_triggered,
        "details": health_results,
    }
