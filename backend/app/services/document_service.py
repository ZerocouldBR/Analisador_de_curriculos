from sqlalchemy.orm import Session
from fastapi import UploadFile
from typing import Optional, BinaryIO
import io

from app.db.models import Document, Candidate, Chunk, Embedding, AuditLog
from app.services.storage_service import storage_service
from app.services.text_extraction_service import TextExtractionService
from app.services.resume_parser_service import ResumeParserService
from app.schemas.candidate import CandidateCreate


class DocumentService:
    """Serviço para gerenciamento de documentos/currículos"""

    @staticmethod
    async def upload_resume(
        db: Session,
        file: UploadFile,
        candidate_id: Optional[int] = None,
        user_id: Optional[int] = None,
        company_id: Optional[int] = None,
    ) -> Document:
        """
        Faz upload de um currículo e processa

        Args:
            db: Sessão do banco
            file: Arquivo enviado
            candidate_id: ID do candidato (cria novo se None)
            user_id: ID do usuário que fez upload

        Returns:
            Document criado
        """
        # Verificar formato suportado
        if not storage_service.is_supported_format(file.filename):
            raise ValueError(f"Formato não suportado: {file.filename}")

        # Ler arquivo
        file_content = await file.read()
        file_bytes = io.BytesIO(file_content)

        # Calcular hash
        sha256_hash = storage_service.calculate_sha256(file_bytes)

        # Verificar se documento já existe para o mesmo candidato (deduplicação)
        if candidate_id:
            existing_doc = db.query(Document).filter(
                Document.sha256_hash == sha256_hash,
                Document.candidate_id == candidate_id
            ).first()
            if existing_doc:
                return existing_doc

        # Salvar no storage
        relative_path, _ = storage_service.save_document(
            file_bytes,
            file.filename,
            sha256_hash
        )

        # Detectar tipo MIME
        mime_type = storage_service.get_mime_type(file.filename)

        # Se não tem candidato, criar novo
        if not candidate_id:
            candidate = Candidate(
                full_name="Aguardando processamento",
                email=None,
                company_id=company_id,
            )
            db.add(candidate)
            db.flush()
            candidate_id = candidate.id

        # Criar documento
        document = Document(
            candidate_id=candidate_id,
            original_filename=file.filename,
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

        # Audit log
        audit = AuditLog(
            user_id=user_id,
            action="upload_document",
            entity="document",
            entity_id=document.id,
            metadata_json={
                "filename": file.filename,
                "candidate_id": candidate_id,
                "size": len(file_content)
            }
        )
        db.add(audit)
        db.commit()

        # Processar documento em background usando Celery
        try:
            from app.tasks.document_tasks import process_document_task
            process_document_task.delay(document.id, user_id)
        except Exception as e:
            print(f"Erro ao enfileirar processamento do documento: {e}")
            # Não falhar upload por erro de processamento

        return document

    @staticmethod
    def process_document(
        db: Session,
        document: Document,
        user_id: Optional[int] = None
    ):
        """
        Processa um documento: extrai texto, parseia e cria chunks

        Args:
            db: Sessão do banco
            document: Documento a processar
            user_id: ID do usuário
        """
        # Obter caminho absoluto
        file_path = storage_service.get_absolute_path(document.source_path)

        # Extrair texto
        text = TextExtractionService.extract_text(str(file_path), document.mime_type)

        # Normalizar texto
        text = TextExtractionService.normalize_text(text)

        # Parsear currículo
        resume_data = ResumeParserService.parse_resume(text)

        # Atualizar candidato com informações extraídas
        candidate = db.query(Candidate).filter(
            Candidate.id == document.candidate_id
        ).first()

        if candidate and resume_data["personal_info"].get("name"):
            candidate.full_name = resume_data["personal_info"]["name"]
            candidate.email = resume_data["personal_info"].get("email")
            candidate.phone = resume_data["personal_info"].get("phone")
            if resume_data["personal_info"].get("cpf"):
                candidate.doc_id = resume_data["personal_info"]["cpf"]
            db.commit()

        # Clear old chunks and their embeddings for this document (safe reprocessing)
        old_chunk_ids = [
            c.id for c in db.query(Chunk.id).filter(
                Chunk.document_id == document.id
            ).all()
        ]
        if old_chunk_ids:
            db.query(Embedding).filter(
                Embedding.chunk_id.in_(old_chunk_ids)
            ).delete(synchronize_session=False)
        db.query(Chunk).filter(
            Chunk.document_id == document.id
        ).delete(synchronize_session=False)
        db.flush()

        # Criar chunks por seção
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
                    content=section_content[:10000],
                    meta_json=resume_data if section_name == "full_text" else {}
                )
                db.add(chunk)
                chunks_created += 1

        db.commit()

        # Audit log
        audit = AuditLog(
            user_id=user_id,
            action="process_document",
            entity="document",
            entity_id=document.id,
            metadata_json={"sections_created": chunks_created}
        )
        db.add(audit)
        db.commit()
