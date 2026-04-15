from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.db.database import get_db
from app.schemas.candidate import DocumentResponse, DocumentStatusResponse
from app.services.document_service import DocumentService
from app.core.dependencies import get_current_user, require_permission
from app.core.config import settings
from app.db.models import User, Document


router = APIRouter(prefix="/documents", tags=["documents"])


class BulkUploadFileResult(BaseModel):
    filename: str
    status: str  # uploaded, error
    message: str
    document_id: Optional[int] = None
    candidate_id: Optional[int] = None


class BulkUploadResponse(BaseModel):
    total_files: int
    uploaded: int
    errors: int
    results: List[BulkUploadFileResult]


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile = File(..., description="Arquivo do currículo (PDF, DOCX, imagens)"),
    candidate_id: Optional[int] = Query(None, description="ID do candidato (cria novo se omitido)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("documents.create"))
):
    """
    Faz upload de um currículo

    Funcionalidades:
    - Suporta PDF, DOCX, TXT, imagens (JPG, PNG)
    - Extração automática de texto (OCR para imagens)
    - Parsing estruturado do currículo
    - Deduplicação por hash SHA256
    - Criação automática de chunks e embeddings

    **Requer permissão:** documents.create
    """
    # Validate file size
    max_size = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Arquivo excede o limite de {settings.max_upload_size_mb}MB"
        )
    # Reset file for downstream processing
    await file.seek(0)

    try:
        document = await DocumentService.upload_resume(
            db,
            file,
            candidate_id,
            current_user.id,
            company_id=current_user.company_id,
        )

        return DocumentResponse(
            id=document.id,
            candidate_id=document.candidate_id,
            original_filename=document.original_filename,
            mime_type=document.mime_type,
            source_path=document.source_path,
            sha256_hash=document.sha256_hash,
            uploaded_at=document.uploaded_at
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar upload: {str(e)}"
        )


@router.post("/{document_id}/reprocess")
async def reprocess_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("documents.update"))
):
    """
    Reprocessa um documento (extração e parsing)

    Útil quando:
    - Houve erro no processamento inicial
    - Melhorias foram feitas no parser
    - Precisa recriar chunks e embeddings

    **Requer permissão:** documents.update
    """
    document = db.query(Document).filter(Document.id == document_id).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento não encontrado"
        )

    try:
        from app.tasks.document_tasks import process_document_task
        task = process_document_task.delay(document.id, current_user.id)

        return {
            "message": "Documento enfileirado para reprocessamento",
            "task_id": task.id,
            "document_id": document.id
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao reprocessar documento: {str(e)}"
        )


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the processing status of a document.
    Used by frontend to poll for status updates.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento nao encontrado"
        )

    return DocumentStatusResponse(
        id=document.id,
        processing_status=document.processing_status or "pending",
        processing_progress=document.processing_progress or 0,
        processing_message=document.processing_message,
        processing_error=document.processing_error,
    )


@router.post("/batch-status", response_model=List[DocumentStatusResponse])
async def get_batch_document_status(
    document_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the processing status of multiple documents in a single request.
    Used by frontend to poll status for all active uploads.
    """
    documents = db.query(Document).filter(Document.id.in_(document_ids)).all()

    return [
        DocumentStatusResponse(
            id=doc.id,
            processing_status=doc.processing_status or "pending",
            processing_progress=doc.processing_progress or 0,
            processing_message=doc.processing_message,
            processing_error=doc.processing_error,
        )
        for doc in documents
    ]


@router.post("/bulk-upload", response_model=BulkUploadResponse)
async def bulk_upload_resumes(
    files: List[UploadFile] = File(..., description="Multiplos arquivos de curriculo"),
    candidate_id: Optional[int] = Query(None, description="ID do candidato (cria novo por arquivo se omitido)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("documents.create"))
):
    """
    Upload em lote de multiplos curriculos via browser

    Aceita multiplos arquivos simultaneamente (PDF, DOCX, TXT, imagens).
    Suporta selecao de pasta inteira via atributo webkitdirectory do browser.

    Para cada arquivo:
    - Cria um novo candidato (ou vincula ao candidato_id informado)
    - Salva no storage com deduplicacao por SHA256
    - Enfileira processamento async (OCR, parsing, embeddings)

    **Requer permissao:** documents.create
    """
    max_size = settings.max_upload_size_mb * 1024 * 1024
    results: List[BulkUploadFileResult] = []
    uploaded_count = 0
    error_count = 0

    for file in files:
        try:
            # Validate file size - read content and check
            content = await file.read()
            file_size = len(content)
            # Always reset file pointer after reading
            await file.seek(0)

            if file_size > max_size:
                results.append(BulkUploadFileResult(
                    filename=file.filename or "unknown",
                    status="error",
                    message=f"Arquivo excede o limite de {settings.max_upload_size_mb}MB ({file_size // (1024*1024)}MB)",
                ))
                error_count += 1
                continue

            document = await DocumentService.upload_resume(
                db,
                file,
                candidate_id,
                current_user.id,
                company_id=current_user.company_id,
            )

            results.append(BulkUploadFileResult(
                filename=file.filename or "unknown",
                status="uploaded",
                message="Upload realizado, processamento enfileirado",
                document_id=document.id,
                candidate_id=document.candidate_id,
            ))
            uploaded_count += 1

        except ValueError as e:
            results.append(BulkUploadFileResult(
                filename=file.filename or "unknown",
                status="error",
                message=str(e),
            ))
            error_count += 1

        except Exception as e:
            results.append(BulkUploadFileResult(
                filename=file.filename or "unknown",
                status="error",
                message=f"Erro: {str(e)}",
            ))
            error_count += 1

    return BulkUploadResponse(
        total_files=len(files),
        uploaded=uploaded_count,
        errors=error_count,
        results=results,
    )
