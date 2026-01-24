from sqlalchemy.orm import Session
from typing import Optional
from app.db.models import Candidate, Document, AuditLog
from app.schemas.candidate import CandidateCreate, CandidateUpdate


class CandidateService:
    @staticmethod
    def get_candidate(db: Session, candidate_id: int) -> Optional[Candidate]:
        """Obtém um candidato por ID"""
        return db.query(Candidate).filter(Candidate.id == candidate_id).first()

    @staticmethod
    def get_candidates(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        city: Optional[str] = None,
        state: Optional[str] = None
    ) -> list[Candidate]:
        """Lista candidatos com filtros opcionais"""
        query = db.query(Candidate)

        if city:
            query = query.filter(Candidate.city == city)
        if state:
            query = query.filter(Candidate.state == state)

        return query.offset(skip).limit(limit).all()

    @staticmethod
    def create_candidate(
        db: Session,
        candidate: CandidateCreate,
        user_id: Optional[int] = None
    ) -> Candidate:
        """Cria um novo candidato"""
        db_candidate = Candidate(**candidate.model_dump())
        db.add(db_candidate)
        db.commit()
        db.refresh(db_candidate)

        # Registrar no audit log
        audit = AuditLog(
            user_id=user_id,
            action="create",
            entity="candidate",
            entity_id=db_candidate.id,
            metadata_json={"name": candidate.full_name}
        )
        db.add(audit)
        db.commit()

        return db_candidate

    @staticmethod
    def update_candidate(
        db: Session,
        candidate_id: int,
        candidate_update: CandidateUpdate,
        user_id: Optional[int] = None
    ) -> Optional[Candidate]:
        """Atualiza um candidato existente"""
        db_candidate = CandidateService.get_candidate(db, candidate_id)
        if not db_candidate:
            return None

        update_data = candidate_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_candidate, field, value)

        db.commit()
        db.refresh(db_candidate)

        # Registrar no audit log
        audit = AuditLog(
            user_id=user_id,
            action="update",
            entity="candidate",
            entity_id=db_candidate.id,
            metadata_json={"updated_fields": list(update_data.keys())}
        )
        db.add(audit)
        db.commit()

        return db_candidate

    @staticmethod
    def delete_candidate(
        db: Session,
        candidate_id: int,
        user_id: Optional[int] = None
    ) -> bool:
        """
        Remove um candidato e todos os seus dados relacionados (currículos, chunks, embeddings, etc.)
        A remoção em cascata está configurada nos relacionamentos do modelo
        """
        db_candidate = CandidateService.get_candidate(db, candidate_id)
        if not db_candidate:
            return False

        candidate_name = db_candidate.full_name

        # Registrar no audit log antes de deletar
        audit = AuditLog(
            user_id=user_id,
            action="delete",
            entity="candidate",
            entity_id=candidate_id,
            metadata_json={
                "name": candidate_name,
                "total_documents": len(db_candidate.documents),
                "total_experiences": len(db_candidate.experiences)
            }
        )
        db.add(audit)

        # Deletar candidato (cascata automática remove relacionados)
        db.delete(db_candidate)
        db.commit()

        return True

    @staticmethod
    def get_candidate_documents(db: Session, candidate_id: int) -> list[Document]:
        """Lista todos os documentos/currículos de um candidato"""
        return db.query(Document).filter(Document.candidate_id == candidate_id).all()

    @staticmethod
    def delete_document(
        db: Session,
        document_id: int,
        user_id: Optional[int] = None
    ) -> bool:
        """
        Remove um documento/currículo específico
        A remoção em cascata remove automaticamente chunks e embeddings relacionados
        """
        db_document = db.query(Document).filter(Document.id == document_id).first()
        if not db_document:
            return False

        # Registrar no audit log antes de deletar
        audit = AuditLog(
            user_id=user_id,
            action="delete",
            entity="document",
            entity_id=document_id,
            metadata_json={
                "candidate_id": db_document.candidate_id,
                "filename": db_document.original_filename,
                "total_chunks": len(db_document.chunks)
            }
        )
        db.add(audit)

        # Deletar documento (cascata automática remove chunks e embeddings)
        db.delete(db_document)
        db.commit()

        return True
