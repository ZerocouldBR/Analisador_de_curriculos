"""
Celery tasks for document processing
"""
from celery import Task
from sqlalchemy.orm import Session
from typing import Optional
import asyncio

from app.core.celery_app import celery_app
from app.db.database import SessionLocal
from app.db.models import Document, Candidate, Chunk, AuditLog
from app.services.storage_service import storage_service
from app.services.text_extraction_service import TextExtractionService
from app.services.resume_parser_service import ResumeParserService
from app.core.websocket_manager import websocket_manager


class DatabaseTask(Task):
    """Base task that provides database session"""
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


@celery_app.task(bind=True, base=DatabaseTask, name="app.tasks.document_tasks.process_document_task")
def process_document_task(
    self,
    document_id: int,
    user_id: Optional[int] = None
):
    """
    Celery task to process a document asynchronously

    Args:
        document_id: ID of the document to process
        user_id: ID of the user who initiated the processing
    """
    db = self.db

    try:
        # Send initial status
        _send_progress(document_id, "started", 0, "Iniciando processamento do documento")

        # Get document
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            _send_progress(document_id, "error", 0, f"Documento {document_id} não encontrado")
            raise ValueError(f"Document {document_id} not found")

        _send_progress(document_id, "processing", 10, "Documento encontrado")

        # Get absolute file path
        file_path = storage_service.get_absolute_path(document.source_path)
        _send_progress(document_id, "processing", 20, "Extraindo texto do documento")

        # Extract text
        text = TextExtractionService.extract_text(str(file_path), document.mime_type)
        _send_progress(document_id, "processing", 40, "Texto extraído com sucesso")

        # Normalize text
        text = TextExtractionService.normalize_text(text)
        _send_progress(document_id, "processing", 50, "Analisando estrutura do currículo")

        # Parse resume
        resume_data = ResumeParserService.parse_resume(text)
        _send_progress(document_id, "processing", 60, "Currículo analisado")

        # Update candidate with extracted information
        candidate = db.query(Candidate).filter(
            Candidate.id == document.candidate_id
        ).first()

        if candidate and resume_data["personal_info"].get("name"):
            candidate.full_name = resume_data["personal_info"]["name"]
            candidate.email = resume_data["personal_info"].get("email")
            candidate.phone = resume_data["personal_info"].get("phone")
            db.commit()

        _send_progress(document_id, "processing", 70, "Criando chunks de texto")

        # Create chunks by section
        sections = [
            ("full_text", text),
            ("personal_info", str(resume_data.get("personal_info", {}))),
            ("experiences", str(resume_data.get("experiences", []))),
            ("education", str(resume_data.get("education", []))),
            ("skills", ", ".join(resume_data.get("skills", []))),
            ("languages", str(resume_data.get("languages", []))),
            ("certifications", ", ".join(resume_data.get("certifications", []))),
        ]

        chunks_created = 0
        for section_name, section_content in sections:
            if section_content.strip():
                chunk = Chunk(
                    document_id=document.id,
                    candidate_id=document.candidate_id,
                    section=section_name,
                    content=section_content[:10000],  # Limit size
                    meta_json=resume_data if section_name == "full_text" else {}
                )
                db.add(chunk)
                chunks_created += 1

        db.commit()
        _send_progress(document_id, "processing", 90, f"{chunks_created} chunks criados")

        # Create audit log
        audit = AuditLog(
            user_id=user_id,
            action="process_document",
            entity="document",
            entity_id=document.id,
            metadata_json={
                "sections_created": chunks_created,
                "candidate_name": resume_data["personal_info"].get("name", "Unknown")
            }
        )
        db.add(audit)
        db.commit()

        _send_progress(document_id, "completed", 100, "Processamento concluído com sucesso")

        return {
            "document_id": document_id,
            "candidate_id": document.candidate_id,
            "chunks_created": chunks_created,
            "status": "completed"
        }

    except Exception as e:
        error_msg = f"Erro ao processar documento: {str(e)}"
        _send_progress(document_id, "error", 0, error_msg)

        # Log error
        audit = AuditLog(
            user_id=user_id,
            action="process_document_error",
            entity="document",
            entity_id=document_id,
            metadata_json={"error": str(e)}
        )
        db.add(audit)
        db.commit()

        raise


def _send_progress(document_id: int, status: str, progress: int, message: str):
    """
    Send progress update via WebSocket

    Args:
        document_id: ID of the document being processed
        status: Current status (started, processing, completed, error)
        progress: Progress percentage (0-100)
        message: Progress message
    """
    try:
        asyncio.run(
            websocket_manager.send_document_progress(
                document_id=document_id,
                status=status,
                progress=progress,
                message=message
            )
        )
    except Exception as e:
        # Don't fail task if WebSocket sending fails
        print(f"Failed to send WebSocket progress: {e}")
