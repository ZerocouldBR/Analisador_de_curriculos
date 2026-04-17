"""
Celery task para analise de fit de uma JobApplication.

Executa apos o processamento do curriculo pelo `process_document_task`.
Le o CandidateProfile mais recente + a vaga e chama o JobFitService.
"""
import asyncio
import logging
import time
from celery import Task
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.db.database import SessionLocal
from app.db.models import Document, Job, JobApplication
from app.services.job_fit_service import JobFitService
from app.services.job_service import JobService

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
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
    name="app.tasks.job_fit_tasks.analyze_application_fit_task",
    max_retries=3,
    default_retry_delay=30,
)
def analyze_application_fit_task(
    self,
    application_id: int,
    wait_for_profile_seconds: int = 90,
):
    """
    Analisa o fit de uma aplicacao, aguardando o curriculo ser processado.

    Args:
        application_id: ID da JobApplication
        wait_for_profile_seconds: tempo maximo (segundos) para aguardar o
            CandidateProfile ficar disponivel
    """
    db = self.db

    application = db.query(JobApplication).filter(
        JobApplication.id == application_id
    ).first()
    if not application:
        logger.warning(f"JobApplication {application_id} nao encontrada")
        return {"status": "not_found"}

    job = db.query(Job).filter(Job.id == application.job_id).first()
    if not job:
        logger.warning(f"Job {application.job_id} nao encontrada")
        return {"status": "job_not_found"}

    # Esperar o processamento do documento (polling curto)
    deadline = time.time() + wait_for_profile_seconds
    profile = None
    document_ready = False
    while time.time() < deadline:
        if application.document_id:
            doc = db.query(Document).filter(Document.id == application.document_id).first()
            if doc and doc.processing_status == "completed":
                document_ready = True
                db.refresh(application)
                profile = JobService.get_candidate_latest_profile(db, application.candidate_id)
                if profile:
                    break
        else:
            # Sem documento: tentar usar perfil ja existente
            profile = JobService.get_candidate_latest_profile(db, application.candidate_id)
            if profile:
                document_ready = True
                break
        time.sleep(3)

    if not profile:
        msg = "timeout" if not document_ready else "no_profile"
        logger.warning(f"Application {application_id}: {msg} - marcando fit_status=failed")
        JobService.save_fit_analysis(db, application_id, {"score": 0, "summary": msg}, status="failed")
        return {"status": msg}

    # Executar analise de fit
    job_payload = {
        "title": job.title,
        "description": job.description,
        "requirements": job.requirements,
        "skills_required": job.skills_required or [],
        "skills_desired": job.skills_desired or [],
        "seniority_level": job.seniority_level,
        "work_mode": job.work_mode,
        "location": job.location,
    }

    try:
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                JobFitService.analyze_fit(job_payload, profile)
            )
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Erro ao analisar fit da application {application_id}: {e}", exc_info=True)
        JobService.save_fit_analysis(
            db, application_id, {"score": 0, "summary": f"erro: {e}"}, status="failed"
        )
        raise self.retry(exc=e)

    if not result.get("ai_available"):
        JobService.save_fit_analysis(
            db, application_id, {"score": 0, "summary": "IA indisponivel"}, status="failed"
        )
        return {"status": "ai_unavailable"}

    if result.get("error") or not result.get("data"):
        JobService.save_fit_analysis(
            db, application_id,
            {"score": 0, "summary": result.get("error") or "sem dados"},
            status="failed",
        )
        return {"status": "error", "error": result.get("error")}

    JobService.save_fit_analysis(db, application_id, result["data"], status="analyzed")
    logger.info(
        f"Application {application_id}: fit analisado (score={result['data'].get('score')}, "
        f"recommendation={result['data'].get('recommendation')})"
    )
    return {
        "status": "ok",
        "application_id": application_id,
        "score": result["data"].get("score"),
    }
