"""
API de administracao do sistema

Permite:
- Limpar banco de dados (candidatos, documentos, chunks, embeddings)
- Resetar contadores/sequences do banco
- Estatisticas do sistema
- Gerenciamento de dados
"""
import logging
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text, func
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_permission
from app.db.database import get_db
from app.db.models import (
    User, Candidate, Document, Chunk, Embedding, Experience,
    CandidateProfile, AuditLog, Consent, ExternalEnrichment,
    EncryptedPII, ChatConversation, ChatMessage,
)
from app.services.storage_service import storage_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# ============================================
# Schemas
# ============================================

class DatabaseStatsResponse(BaseModel):
    total_candidates: int = 0
    total_documents: int = 0
    total_chunks: int = 0
    total_embeddings: int = 0
    total_experiences: int = 0
    total_profiles: int = 0
    total_users: int = 0
    total_audit_logs: int = 0
    total_conversations: int = 0
    total_messages: int = 0
    storage_size_mb: float = 0.0


class CleanupRequest(BaseModel):
    delete_candidates: bool = Field(
        default=True,
        description="Deletar todos os candidatos e dados associados"
    )
    delete_documents: bool = Field(
        default=True,
        description="Deletar todos os documentos e arquivos do storage"
    )
    delete_chunks: bool = Field(
        default=True,
        description="Deletar todos os chunks e embeddings"
    )
    delete_experiences: bool = Field(
        default=True,
        description="Deletar todas as experiencias"
    )
    delete_chat_history: bool = Field(
        default=False,
        description="Deletar historico de conversas do chat"
    )
    delete_audit_logs: bool = Field(
        default=False,
        description="Deletar logs de auditoria"
    )
    reset_sequences: bool = Field(
        default=True,
        description="Resetar contadores de ID (autoincrement)"
    )
    confirm: str = Field(
        ...,
        description="Digite 'CONFIRMAR' para executar a limpeza"
    )


class CleanupResponse(BaseModel):
    success: bool
    message: str
    deleted: Dict[str, int]
    sequences_reset: List[str]


class DeleteCandidatesBatchRequest(BaseModel):
    candidate_ids: List[int] = Field(
        ...,
        description="Lista de IDs dos candidatos a deletar"
    )
    confirm: bool = Field(
        default=False,
        description="Confirmar delecao"
    )


# ============================================
# Endpoints
# ============================================

@router.get("/stats", response_model=DatabaseStatsResponse)
def get_database_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.read")),
):
    """
    Retorna estatisticas do banco de dados

    **Requer permissao:** settings.read
    """
    stats = DatabaseStatsResponse(
        total_candidates=db.query(func.count(Candidate.id)).scalar() or 0,
        total_documents=db.query(func.count(Document.id)).scalar() or 0,
        total_chunks=db.query(func.count(Chunk.id)).scalar() or 0,
        total_embeddings=db.query(func.count(Embedding.id)).scalar() or 0,
        total_experiences=db.query(func.count(Experience.id)).scalar() or 0,
        total_profiles=db.query(func.count(CandidateProfile.id)).scalar() or 0,
        total_users=db.query(func.count(User.id)).scalar() or 0,
        total_audit_logs=db.query(func.count(AuditLog.id)).scalar() or 0,
        total_conversations=db.query(func.count(ChatConversation.id)).scalar() or 0,
        total_messages=db.query(func.count(ChatMessage.id)).scalar() or 0,
    )

    # Calcular tamanho do storage
    try:
        import os
        total_size = 0
        docs_path = storage_service.base_path / "documents"
        if docs_path.exists():
            for dirpath, _dirnames, filenames in os.walk(docs_path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    total_size += os.path.getsize(fp)
        stats.storage_size_mb = round(total_size / (1024 * 1024), 2)
    except Exception:
        pass

    return stats


@router.post("/cleanup", response_model=CleanupResponse)
def cleanup_database(
    data: CleanupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.update")),
):
    """
    Limpa dados do banco de dados com opcoes granulares

    **ATENCAO:** Esta operacao e irreversivel!

    Opcoes:
    - delete_candidates: Remove todos os candidatos e dados associados
    - delete_documents: Remove documentos e arquivos fisicos
    - delete_chunks: Remove chunks de texto e embeddings vetoriais
    - delete_experiences: Remove experiencias profissionais
    - delete_chat_history: Remove conversas e mensagens do chat
    - delete_audit_logs: Remove logs de auditoria
    - reset_sequences: Reseta contadores de ID para comecar do 1

    **Requer permissao:** settings.update
    **Requer superuser**
    """
    if data.confirm != "CONFIRMAR":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Para confirmar a limpeza, envie confirm='CONFIRMAR'"
        )

    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas superusuarios podem executar limpeza do banco"
        )

    deleted = {}
    sequences_reset = []

    try:
        # Contar ANTES de deletar para ter os numeros corretos
        if data.delete_chunks:
            deleted["embeddings"] = db.query(func.count(Embedding.id)).scalar() or 0
            deleted["chunks"] = db.query(func.count(Chunk.id)).scalar() or 0
        if data.delete_experiences:
            deleted["experiences"] = db.query(func.count(Experience.id)).scalar() or 0
        if data.delete_documents:
            deleted["documents"] = db.query(func.count(Document.id)).scalar() or 0
        if data.delete_candidates:
            deleted["consents"] = db.query(func.count(Consent.id)).scalar() or 0
            deleted["candidates"] = db.query(func.count(Candidate.id)).scalar() or 0
        if data.delete_chat_history:
            deleted["chat_messages"] = db.query(func.count(ChatMessage.id)).scalar() or 0
            deleted["chat_conversations"] = db.query(func.count(ChatConversation.id)).scalar() or 0
        if data.delete_audit_logs:
            deleted["audit_logs"] = db.query(func.count(AuditLog.id)).scalar() or 0

        # Deletar na ordem correta (foreign keys: filhos antes de pais)

        # 1. Embeddings dependem de Chunks
        if data.delete_chunks or data.delete_documents or data.delete_candidates:
            db.query(Embedding).delete(synchronize_session=False)
            db.query(Chunk).delete(synchronize_session=False)

        # 2. Experiences
        if data.delete_experiences or data.delete_candidates:
            db.query(Experience).delete(synchronize_session=False)

        # 3. Documents e arquivos fisicos
        if data.delete_documents or data.delete_candidates:
            documents = db.query(Document).all()
            files_deleted = 0
            for doc in documents:
                try:
                    if doc.source_path:
                        storage_service.delete_file(doc.source_path)
                        files_deleted += 1
                except Exception as e:
                    logger.warning(f"Erro ao deletar arquivo {doc.source_path}: {e}")
            deleted["files_deleted"] = files_deleted
            db.query(Document).delete(synchronize_session=False)

        # 4. Dados associados a candidatos
        if data.delete_candidates:
            db.query(Consent).delete(synchronize_session=False)
            db.query(ExternalEnrichment).delete(synchronize_session=False)
            db.query(EncryptedPII).delete(synchronize_session=False)
            db.query(CandidateProfile).delete(synchronize_session=False)
            db.query(Candidate).delete(synchronize_session=False)

        # 5. Chat
        if data.delete_chat_history:
            db.query(ChatMessage).delete(synchronize_session=False)
            db.query(ChatConversation).delete(synchronize_session=False)

        # 6. Audit logs
        if data.delete_audit_logs:
            db.query(AuditLog).delete(synchronize_session=False)

        db.commit()

        # Resetar sequences
        if data.reset_sequences:
            tables_to_reset = []
            if data.delete_candidates:
                # Candidatos e todos os filhos (cascade)
                tables_to_reset.extend([
                    "candidates", "candidate_profiles", "consents",
                    "external_enrichments", "encrypted_pii",
                    "documents", "chunks", "embeddings", "experiences",
                ])
            if data.delete_documents:
                tables_to_reset.extend(["documents", "chunks", "embeddings"])
            if data.delete_chunks:
                tables_to_reset.extend(["chunks", "embeddings"])
            if data.delete_experiences:
                tables_to_reset.extend(["experiences"])
            if data.delete_chat_history:
                tables_to_reset.extend(["chat_conversations", "chat_messages"])
            if data.delete_audit_logs:
                tables_to_reset.extend(["audit_logs"])

            for table in set(tables_to_reset):
                try:
                    db.execute(text(
                        f"ALTER SEQUENCE IF EXISTS {table}_id_seq RESTART WITH 1"
                    ))
                    sequences_reset.append(table)
                except Exception as e:
                    logger.warning(f"Erro ao resetar sequence de {table}: {e}")

            db.commit()

        # Audit log da operacao
        audit = AuditLog(
            user_id=current_user.id,
            action="database_cleanup",
            entity="system",
            entity_id=0,
            metadata_json={
                "deleted": deleted,
                "sequences_reset": sequences_reset,
                "options": data.model_dump(exclude={"confirm"}),
            },
        )
        db.add(audit)
        db.commit()

        total_deleted = sum(v for v in deleted.values() if isinstance(v, int))

        logger.info(
            f"Database cleanup by user {current_user.email}: "
            f"{total_deleted} records deleted, {len(sequences_reset)} sequences reset"
        )

        return CleanupResponse(
            success=True,
            message=f"Limpeza concluida: {total_deleted} registros removidos",
            deleted=deleted,
            sequences_reset=sequences_reset,
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Database cleanup error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro durante limpeza: {str(e)}"
        )


@router.post("/delete-candidates")
def delete_candidates_batch(
    data: DeleteCandidatesBatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("candidates.delete")),
):
    """
    Deleta candidatos selecionados e todos os dados associados

    **Requer permissao:** candidates.delete
    """
    if not data.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirme a operacao com confirm=true"
        )

    deleted_count = 0
    errors = []

    for cid in data.candidate_ids:
        try:
            candidate = db.query(Candidate).filter(Candidate.id == cid).first()
            if not candidate:
                errors.append(f"Candidato {cid} nao encontrado")
                continue

            # Deletar arquivos fisicos dos documentos
            for doc in candidate.documents:
                try:
                    if doc.source_path:
                        storage_service.delete_file(doc.source_path)
                except Exception as e:
                    logger.warning(f"Erro ao deletar arquivo do candidato {cid}: {e}")

            # Cascade vai cuidar dos relacionamentos
            db.delete(candidate)
            deleted_count += 1

        except Exception as e:
            db.rollback()
            errors.append(f"Erro ao deletar candidato {cid}: {str(e)}")
            logger.error(f"Erro ao deletar candidato {cid}: {e}")

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao commitar delecao de candidatos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao salvar delecao: {str(e)}"
        )

    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="batch_delete_candidates",
        entity="candidate",
        entity_id=0,
        metadata_json={
            "candidate_ids": data.candidate_ids,
            "deleted": deleted_count,
            "errors": errors,
        },
    )
    db.add(audit)
    db.commit()

    return {
        "deleted": deleted_count,
        "errors": errors,
        "message": f"{deleted_count} candidato(s) removido(s)",
    }
