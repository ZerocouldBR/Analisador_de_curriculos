"""
Celery tasks for document processing

Enhanced with:
- Advanced OCR with image preprocessing and confidence scoring
- Production/logistics keyword extraction
- Structured metadata indexing with industry profiles
- Optimized chunking for LLM retrieval
- Safety certifications, licenses, equipment extraction
- Experience table population from parsed data
"""
import re
import logging
from datetime import datetime, timezone
from celery import Task
from sqlalchemy.orm import Session
from typing import Optional

from app.core.celery_app import celery_app
from app.db.database import SessionLocal
from app.db.models import Document, Candidate, Chunk, Embedding, Experience, CandidateProfile, AuditLog
from app.services.storage_service import storage_service
from app.services.text_extraction_service import TextExtractionService
from app.services.resume_parser_service import ResumeParserService
from app.services.keyword_extraction_service import KeywordExtractionService
from app.services.embedding_service import SemanticChunker
from app.core.config import settings

logger = logging.getLogger(__name__)


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

    Pipeline:
    1. Extract text (with enhanced OCR for image PDFs)
    2. Parse resume structure
    3. Extract production/logistics specific data
    4. Extract and categorize keywords
    5. Clear old chunks/embeddings (for reprocessing)
    6. Create optimized chunks with metadata
    7. Populate Experience table
    8. Create CandidateProfile snapshot
    9. Index for LLM retrieval

    Args:
        document_id: ID of the document to process
        user_id: ID of the user who initiated the processing
    """
    db = self.db

    try:
        # Send initial status
        _update_document_status(db, document_id, "processing", 0, "Iniciando processamento do documento")

        # Get document
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            _update_document_status(db, document_id, "error", 0, f"Documento {document_id} nao encontrado", error=f"Document {document_id} not found")
            raise ValueError(f"Document {document_id} not found")

        _update_document_status(db, document_id, "processing", 10, "Documento encontrado")

        # Get absolute file path
        file_path = storage_service.get_absolute_path(document.source_path)
        _update_document_status(db, document_id, "processing", 15, "Extraindo texto do documento (OCR avancado)")

        # ============================================
        # STEP 1: Enhanced Text Extraction
        # ============================================
        ocr_result = TextExtractionService.extract_text_with_metadata(
            str(file_path), document.mime_type
        )
        text = ocr_result.text

        # Log OCR quality
        ocr_metadata = {
            "confidence": ocr_result.confidence,
            "language": ocr_result.language,
            "pages_processed": ocr_result.pages_processed,
            "pages_with_ocr": ocr_result.pages_with_ocr,
            "pages_with_text": ocr_result.pages_with_text,
            "warnings": ocr_result.warnings,
        }

        if ocr_result.warnings:
            logger.warning(
                f"OCR warnings for document {document_id}: {ocr_result.warnings}"
            )

        progress_msg = "Texto extraido"
        if ocr_result.pages_with_ocr > 0:
            progress_msg += f" (OCR em {ocr_result.pages_with_ocr} paginas, confianca: {ocr_result.confidence:.0%})"

        _update_document_status(db, document_id, "processing", 35, progress_msg)

        # ============================================
        # STEP 2: Normalize Text
        # ============================================
        text = TextExtractionService.normalize_text(text)
        _update_document_status(db, document_id, "processing", 40, "Texto normalizado")

        # ============================================
        # STEP 3: Parse Resume Structure (Regex + AI Pipeline)
        # ============================================
        _update_document_status(db, document_id, "processing", 45, "Analisando estrutura do curriculo")
        resume_data = ResumeParserService.parse_resume(text)

        # Run enrichment pipeline (regex + AI validation + confidence scoring)
        enriched_result = None
        try:
            from app.services.resume_enrichment_pipeline import ResumeEnrichmentPipeline
            _update_document_status(db, document_id, "processing", 48, "Executando pipeline de enriquecimento (IA + validacao)")
            enriched_result = ResumeEnrichmentPipeline.process_sync(
                text,
                enable_ai=bool(settings.openai_api_key),
                enable_career_advisory=False,
            )
        except Exception as enrich_err:
            logger.warning(f"Pipeline de enriquecimento falhou, usando apenas regex: {enrich_err}")
            enriched_result = None

        # Use enriched data if available, otherwise fallback to regex
        if enriched_result and enriched_result.get("data"):
            enriched_data = enriched_result["data"]
            enriched_personal = enriched_data.get("personal_info", {})
        else:
            enriched_data = None
            enriched_personal = None

        _update_document_status(db, document_id, "processing", 55, "Curriculo analisado com sucesso")

        # ============================================
        # STEP 4: Update Candidate Information
        # ============================================
        candidate = db.query(Candidate).filter(
            Candidate.id == document.candidate_id
        ).first()

        if candidate:
            # Prefer enriched data (AI-validated) over raw regex
            if enriched_personal:
                personal = enriched_personal
            else:
                personal = resume_data["personal_info"]

            if personal.get("name"):
                candidate.full_name = personal["name"]
            if personal.get("email"):
                candidate.email = personal["email"]
            if personal.get("phone"):
                candidate.phone = personal["phone"]

            # Update CPF/document ID
            if personal.get("cpf"):
                candidate.doc_id = personal["cpf"]

            # Update birth date
            if personal.get("birth_date"):
                try:
                    from dateutil.parser import parse as parse_date
                    candidate.birth_date = parse_date(
                        personal["birth_date"], dayfirst=True
                    ).date()
                except (ValueError, TypeError):
                    logger.warning(
                        f"Could not parse birth_date: {personal['birth_date']}"
                    )

            # Update location from resume
            if personal.get("location"):
                location = personal["location"]
                loc_match = re.match(
                    r'([A-ZÁÉÍÓÚÂÊÔÃÕÇa-záéíóúâêôãõç\s]+),?\s*[-–]?\s*([A-Z]{2})',
                    location
                )
                if loc_match:
                    candidate.city = loc_match.group(1).strip()
                    candidate.state = loc_match.group(2).strip()

            db.commit()

        _update_document_status(db, document_id, "processing", 58, "Dados do candidato atualizados")

        # ============================================
        # STEP 4b: Populate Experience Table
        # ============================================
        if candidate and resume_data.get("experiences"):
            # Remove old experiences from this document's parsing
            db.query(Experience).filter(
                Experience.candidate_id == candidate.id
            ).delete(synchronize_session=False)

            for exp_data in resume_data["experiences"]:
                start_date = None
                end_date = None

                # Parse dates
                if exp_data.get("start_date"):
                    try:
                        from dateutil.parser import parse as parse_date
                        start_date = parse_date(
                            exp_data["start_date"], dayfirst=True
                        ).date()
                    except (ValueError, TypeError):
                        pass

                if exp_data.get("end_date"):
                    end_val = exp_data["end_date"].lower()
                    if end_val not in ("atual", "presente", "current"):
                        try:
                            from dateutil.parser import parse as parse_date
                            end_date = parse_date(
                                exp_data["end_date"], dayfirst=True
                            ).date()
                        except (ValueError, TypeError):
                            pass

                description = exp_data.get("description", "")
                if isinstance(description, list):
                    description = "\n".join(description)

                experience = Experience(
                    candidate_id=candidate.id,
                    company_name=exp_data.get("company"),
                    title=exp_data.get("title"),
                    start_date=start_date,
                    end_date=end_date,
                    description=description,
                )
                db.add(experience)

            db.commit()

        _update_document_status(db, document_id, "processing", 60, "Experiencias salvas no banco de dados")

        # ============================================
        # STEP 5: Extract Keywords (Enhanced)
        # ============================================
        _update_document_status(db, document_id, "processing", 65, "Extraindo palavras-chave (producao/logistica/qualidade)")

        document_keywords = {}
        if getattr(settings, 'enable_keyword_extraction', True):
            document_keywords = KeywordExtractionService.extract_keywords(text, resume_data)

        profile_type = document_keywords.get("candidate_profile_type", "general")
        _update_document_status(
            db, document_id, "processing", 72,
            f"Keywords extraidas - Perfil detectado: {profile_type}"
        )

        # ============================================
        # STEP 6: Clear Old Chunks and Create New Ones
        # ============================================
        _update_document_status(db, document_id, "processing", 75, "Criando chunks de texto otimizados")

        # Delete old embeddings for this document's chunks first (cascade)
        old_chunk_ids = [
            c.id for c in db.query(Chunk.id).filter(
                Chunk.document_id == document.id
            ).all()
        ]
        if old_chunk_ids:
            db.query(Embedding).filter(
                Embedding.chunk_id.in_(old_chunk_ids)
            ).delete(synchronize_session=False)

        # Delete old chunks for this document
        db.query(Chunk).filter(
            Chunk.document_id == document.id
        ).delete(synchronize_session=False)
        db.flush()

        # Usar chunking semantico para o texto completo
        semantic_chunks = SemanticChunker.create_semantic_chunks(
            text, section_name="full_text",
            chunk_size=settings.chunk_size,
            overlap=settings.chunk_overlap,
        )

        sections = [
            ("personal_info", str(resume_data.get("personal_info", {}))),
            ("experiences", str(resume_data.get("experiences", []))),
            ("education", str(resume_data.get("education", []))),
            ("skills", ", ".join(resume_data.get("skills", []))),
            ("languages", str(resume_data.get("languages", []))),
            ("certifications", ", ".join(resume_data.get("certifications", []))),
        ]

        # Adicionar chunks semanticos do texto completo
        for sc in semantic_chunks:
            sc_section = sc["metadata"].get("section", "full_text")
            sections.insert(0, (sc_section, sc["content"]))

        # Add production/logistics specific sections
        if resume_data.get("licenses"):
            licenses_text = "\n".join([
                f"{lic.get('type', '')}: {lic.get('description', '')}"
                for lic in resume_data["licenses"]
            ])
            if licenses_text.strip():
                sections.append(("licenses", licenses_text))

        if resume_data.get("safety_certs"):
            safety_text = "\n".join([
                f"{s.get('code', '')}: {s.get('description', '')}"
                for s in resume_data["safety_certs"]
            ])
            if safety_text.strip():
                sections.append(("safety_certifications", safety_text))

        if resume_data.get("equipment"):
            equipment_text = "\n".join([
                f"{e.get('name', '')}: {e.get('detail', '')}"
                for e in resume_data["equipment"]
            ])
            if equipment_text.strip():
                sections.append(("equipment", equipment_text))

        if resume_data.get("erp_systems"):
            erp_text = "\n".join([
                f"{s.get('system', '')}: {', '.join(s.get('modules', []))}"
                for s in resume_data["erp_systems"]
            ])
            if erp_text.strip():
                sections.append(("erp_systems", erp_text))

        if resume_data.get("availability"):
            avail = resume_data["availability"]
            avail_parts = []
            if avail.get("shifts"):
                avail_parts.append(f"Turnos: {', '.join(avail['shifts'])}")
            if avail.get("travel") is not None:
                avail_parts.append(f"Viagens: {'Sim' if avail['travel'] else 'Nao'}")
            if avail.get("relocation"):
                avail_parts.append("Disponivel para mudanca")
            if avail.get("immediate_start"):
                avail_parts.append("Disponibilidade imediata")
            avail_text = "\n".join(avail_parts)
            if avail_text.strip():
                sections.append(("availability", avail_text))

        # Add keyword index as special chunk
        if document_keywords.get("search_index"):
            sections.append(("keyword_index", document_keywords["search_index"]))

        chunks_created = 0
        total_sections = len([s for s in sections if s[1].strip()])

        for section_name, section_content in sections:
            if section_content.strip():
                # Create enhanced metadata for this chunk
                chunk_metadata = KeywordExtractionService.create_chunk_metadata(
                    section=section_name,
                    content=section_content[:settings.chunk_max_content_size],
                    keywords=document_keywords,
                    chunk_index=chunks_created,
                    total_chunks=total_sections
                )

                # Merge with full data for full_text chunk
                if section_name == "full_text":
                    chunk_metadata["resume_data"] = resume_data
                    chunk_metadata["ocr_metadata"] = ocr_metadata
                    chunk_metadata["candidate_profile_type"] = profile_type
                    chunk_metadata["document_keywords"] = {
                        "keywords": document_keywords.get("keywords", [])[:50],
                        "technical_skills": document_keywords.get("technical_skills", []),
                        "soft_skills": document_keywords.get("soft_skills", []),
                        "tools_and_frameworks": document_keywords.get("tools_and_frameworks", []),
                        "certifications": document_keywords.get("certifications", []),
                        "domains": document_keywords.get("domains", []),
                        "companies": document_keywords.get("companies", []),
                        "production_skills": document_keywords.get("production_skills", []),
                        "logistics_skills": document_keywords.get("logistics_skills", []),
                        "quality_skills": document_keywords.get("quality_skills", []),
                        "safety_certifications": document_keywords.get("safety_certifications", []),
                        "maintenance_skills": document_keywords.get("maintenance_skills", []),
                        "licenses": document_keywords.get("licenses", []),
                        "erp_systems": document_keywords.get("erp_systems", []),
                        "improvement_methods": document_keywords.get("improvement_methods", []),
                        "industry_sectors": document_keywords.get("industry_sectors", []),
                        "relevance_scores": document_keywords.get("relevance_scores", {})
                    }

                chunk = Chunk(
                    document_id=document.id,
                    candidate_id=document.candidate_id,
                    section=section_name,
                    content=section_content[:settings.chunk_max_content_size],
                    meta_json=chunk_metadata
                )
                db.add(chunk)
                chunks_created += 1

        db.commit()
        _update_document_status(db, document_id, "processing", 85, f"{chunks_created} chunks criados")

        # ============================================
        # STEP 7: Generate Embeddings for Document
        # ============================================
        _update_document_status(db, document_id, "processing", 87, "Gerando embeddings vetoriais")

        try:
            import asyncio
            from app.services.embedding_service import EmbeddingService
            embedding_svc = EmbeddingService()

            # Run async embedding generation from sync Celery task
            loop = asyncio.new_event_loop()
            try:
                embeddings_result = loop.run_until_complete(
                    embedding_svc.generate_embeddings_for_document(db, document.id)
                )
                embeddings_count = len(embeddings_result) if embeddings_result else 0
                _update_document_status(
                    db, document_id, "processing", 92,
                    f"{embeddings_count} embeddings gerados"
                )
            finally:
                loop.close()
        except Exception as emb_err:
            logger.error(f"Erro ao gerar embeddings para documento {document_id}: {emb_err}")
            _update_document_status(
                db, document_id, "processing", 92,
                f"Chunks criados mas embeddings falharam: {emb_err}"
            )

        # ============================================
        # STEP 8: Save CandidateProfile Snapshot
        # ============================================
        if candidate:
            # Determine next version number
            last_profile = db.query(CandidateProfile).filter(
                CandidateProfile.candidate_id == candidate.id
            ).order_by(CandidateProfile.version.desc()).first()

            next_version = (last_profile.version + 1) if last_profile else 1

            # Store enriched data if available, otherwise raw regex data
            profile_data = enriched_result if enriched_result and enriched_result.get("data") else resume_data
            profile = CandidateProfile(
                candidate_id=candidate.id,
                version=next_version,
                profile_json=profile_data
            )
            db.add(profile)
            db.commit()

        _update_document_status(db, document_id, "processing", 92, "Perfil do candidato salvo")

        # ============================================
        # STEP 9: Audit Log
        # ============================================
        audit_metadata = {
            "sections_created": chunks_created,
            "candidate_name": resume_data["personal_info"].get("name", "Unknown"),
            "profile_type": profile_type,
            "ocr_confidence": ocr_result.confidence,
            "pages_with_ocr": ocr_result.pages_with_ocr,
            "keywords_found": len(document_keywords.get("keywords", [])),
            "production_skills": len(document_keywords.get("production_skills", [])),
            "logistics_skills": len(document_keywords.get("logistics_skills", [])),
            "quality_skills": len(document_keywords.get("quality_skills", [])),
            "safety_certs": len(resume_data.get("safety_certs", [])),
            "licenses": len(resume_data.get("licenses", [])),
            "equipment": len(resume_data.get("equipment", [])),
            "experiences_saved": len(resume_data.get("experiences", [])),
        }

        audit = AuditLog(
            user_id=user_id,
            action="process_document",
            entity="document",
            entity_id=document.id,
            metadata_json=audit_metadata
        )
        db.add(audit)
        db.commit()

        _update_document_status(db, document_id, "completed", 100, "Processamento concluido com sucesso")

        return {
            "document_id": document_id,
            "candidate_id": document.candidate_id,
            "chunks_created": chunks_created,
            "profile_type": profile_type,
            "ocr_confidence": ocr_result.confidence,
            "experiences_saved": len(resume_data.get("experiences", [])),
            "status": "completed"
        }

    except Exception as e:
        error_msg = f"Erro ao processar documento: {str(e)}"
        logger.error(error_msg, exc_info=True)
        _update_document_status(db, document_id, "error", 0, error_msg, error=str(e))

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


def _update_document_status(db: Session, document_id: int, status: str, progress: int, message: str, error: str = None):
    """Persist processing status in the database so frontend can poll it"""
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if document:
            document.processing_status = status
            document.processing_progress = progress
            document.processing_message = message
            if error:
                document.processing_error = error
            if status == "processing" and not document.processing_started_at:
                document.processing_started_at = datetime.now(timezone.utc)
            if status in ("completed", "error"):
                document.processing_completed_at = datetime.now(timezone.utc)
            db.commit()
    except Exception as e:
        logger.warning(f"Failed to update document status: {e}")
        try:
            db.rollback()
        except Exception:
            pass
