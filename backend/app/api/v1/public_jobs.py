"""
Endpoints publicos (sem autenticacao) para o painel de vagas.

- `GET /public/careers/{company_slug}` - lista vagas ativas + branding
- `GET /public/careers/{company_slug}/{job_slug}` - detalhe da vaga
- `POST /public/careers/{company_slug}/{job_slug}/apply` - aplicar enviando curriculo

A aplicacao cria Candidate + Document + JobApplication, dispara o
processamento do documento e depois a analise de fit em background.
"""
import io
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.db.models import AuditLog, Document
from app.schemas.job import (
    PublicJobsPageResponse,
    PublicJobResponse,
    JobApplicationPublicResponse,
)
from app.services.job_service import JobService
from app.services.storage_service import storage_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/careers/{company_slug}", response_model=PublicJobsPageResponse)
def public_careers_page(company_slug: str, db: Session = Depends(get_db)):
    """
    Pagina publica da empresa: branding + lista de vagas ativas.
    Nao requer autenticacao.
    """
    company = JobService.get_public_company(db, company_slug)
    if not company:
        raise HTTPException(status_code=404, detail="Empresa nao encontrada")

    jobs = JobService.list_public_jobs(db, company.id)
    return PublicJobsPageResponse(
        company=JobService.company_brand_payload(company),
        jobs=[JobService.public_job_list_item(j) for j in jobs],
        total=len(jobs),
    )


@router.get("/careers/{company_slug}/{job_slug}", response_model=PublicJobResponse)
def public_job_detail(
    company_slug: str,
    job_slug: str,
    db: Session = Depends(get_db),
):
    """Detalhe publico de uma vaga."""
    company = JobService.get_public_company(db, company_slug)
    if not company:
        raise HTTPException(status_code=404, detail="Empresa nao encontrada")
    job = JobService.get_public_job(db, company.id, job_slug)
    if not job:
        raise HTTPException(status_code=404, detail="Vaga nao encontrada")
    return JobService.public_job_payload(job, company)


@router.post(
    "/careers/{company_slug}/{job_slug}/apply",
    response_model=JobApplicationPublicResponse,
    status_code=status.HTTP_201_CREATED,
)
async def apply_to_job_public(
    company_slug: str,
    job_slug: str,
    resume: UploadFile = File(..., description="Curriculo em PDF, DOCX ou imagem"),
    applicant_name: str = Form(..., min_length=2, max_length=200),
    applicant_email: str = Form(...),
    applicant_phone: Optional[str] = Form(None),
    cover_letter: Optional[str] = Form(None),
    consent_given: bool = Form(...),
    db: Session = Depends(get_db),
):
    """
    Aplicacao publica a uma vaga. Nao requer autenticacao.

    Fluxo:
    1. Valida empresa + vaga ativa
    2. Valida arquivo (formato + tamanho)
    3. Cria/encontra Candidate por email
    4. Faz upload do curriculo (reutiliza Document/storage)
    5. Cria JobApplication
    6. Enfileira processamento do documento + analise de fit
    """
    if not consent_given:
        raise HTTPException(status_code=400, detail="Consentimento LGPD obrigatorio")

    company = JobService.get_public_company(db, company_slug)
    if not company:
        raise HTTPException(status_code=404, detail="Empresa nao encontrada")

    job = JobService.get_public_job(db, company.id, job_slug)
    if not job:
        raise HTTPException(status_code=404, detail="Vaga nao encontrada ou indisponivel")

    # Validar formato
    if not storage_service.is_supported_format(resume.filename or ""):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Formato nao suportado: {resume.filename}",
        )

    # Validar tamanho
    max_size = settings.max_upload_size_mb * 1024 * 1024
    content = await resume.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Arquivo excede {settings.max_upload_size_mb}MB",
        )

    # Criar/encontrar candidato
    candidate = JobService.find_or_create_candidate(
        db=db,
        company_id=company.id,
        name=applicant_name,
        email=applicant_email,
        phone=applicant_phone,
    )

    # Salvar no storage
    file_bytes = io.BytesIO(content)
    sha256_hash = storage_service.calculate_sha256(file_bytes)

    # Deduplicacao por candidato
    existing_doc = db.query(Document).filter(
        Document.sha256_hash == sha256_hash,
        Document.candidate_id == candidate.id,
    ).first()

    if existing_doc:
        document = existing_doc
    else:
        relative_path, _ = storage_service.save_document(
            file_bytes, resume.filename or "resume.pdf", sha256_hash
        )
        mime_type = storage_service.get_mime_type(resume.filename or "")
        document = Document(
            candidate_id=candidate.id,
            original_filename=resume.filename or "resume.pdf",
            mime_type=mime_type,
            source_path=relative_path,
            sha256_hash=sha256_hash,
            processing_status="pending",
            processing_progress=0,
            processing_message="Aguardando processamento",
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        # Enfileirar processamento do documento
        try:
            from app.tasks.document_tasks import process_document_task
            process_document_task.delay(document.id, None)
        except Exception as e:
            logger.warning(f"Falha ao enfileirar processamento do documento: {e}")

    # Criar aplicacao
    application = JobService.create_application(
        db=db,
        job=job,
        candidate=candidate,
        document=document,
        applicant_name=applicant_name,
        applicant_email=applicant_email,
        applicant_phone=applicant_phone,
        cover_letter=cover_letter,
        consent_given=consent_given,
    )

    # Audit log
    try:
        audit = AuditLog(
            user_id=None,
            action="public_job_apply",
            entity="job_application",
            entity_id=application.id,
            metadata_json={
                "job_id": job.id,
                "job_slug": job.slug,
                "company_slug": company.slug,
                "candidate_id": candidate.id,
                "document_id": document.id,
                "applicant_email": applicant_email,
            },
        )
        db.add(audit)
        db.commit()
    except Exception:
        pass

    # Enfileirar analise de fit (aguarda processamento do curriculo)
    try:
        from app.tasks.job_fit_tasks import analyze_application_fit_task
        analyze_application_fit_task.delay(application.id)
    except Exception as e:
        logger.warning(f"Falha ao enfileirar analise de fit: {e}")

    return JobApplicationPublicResponse(
        id=application.id,
        message=(
            "Candidatura recebida. Seu curriculo esta sendo processado e "
            "voce podera ser contactado em breve."
        ),
        fit_status=application.fit_status,
        fit_score=None,
        fit_summary=None,
    )
