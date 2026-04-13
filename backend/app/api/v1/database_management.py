"""
API de gerenciamento do banco de dados

Permite:
- Limpar todos os dados (curriculos, candidatos, etc)
- Resetar sequences/contadores das tabelas
- Apagar dados seletivamente
- Obter estatisticas do banco
"""
import logging
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from app.core.dependencies import get_current_user, require_permission
from app.db.database import get_db
from app.db.models import (
    User, Candidate, Document, Chunk, Embedding, Experience,
    CandidateProfile, AuditLog, Consent, ExternalEnrichment,
    EncryptedPII, ChatConversation, ChatMessage, AIUsageLog,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/database", tags=["database-management"])


# ============================================
# Schemas
# ============================================

class DatabaseStatsResponse(BaseModel):
    candidates: int
    documents: int
    chunks: int
    embeddings: int
    experiences: int
    profiles: int
    conversations: int
    messages: int
    audit_logs: int
    ai_usage_logs: int
    total_records: int


class ClearDataRequest(BaseModel):
    confirm: bool = Field(
        ...,
        description="Deve ser True para confirmar a operacao destrutiva"
    )
    clear_candidates: bool = Field(
        default=True,
        description="Apagar todos os candidatos e dados relacionados"
    )
    clear_documents: bool = Field(
        default=True,
        description="Apagar todos os documentos"
    )
    clear_conversations: bool = Field(
        default=False,
        description="Apagar todas as conversas do chat"
    )
    clear_audit_logs: bool = Field(
        default=False,
        description="Apagar logs de auditoria"
    )
    clear_ai_usage: bool = Field(
        default=False,
        description="Apagar logs de uso de IA"
    )
    reset_sequences: bool = Field(
        default=True,
        description="Resetar contadores de ID (sequences)"
    )


class ClearDataResponse(BaseModel):
    success: bool
    message: str
    deleted: Dict[str, int]
    sequences_reset: List[str]


class DeleteCandidatesBatchRequest(BaseModel):
    candidate_ids: List[int] = Field(
        ...,
        description="Lista de IDs dos candidatos para apagar",
        min_length=1
    )
    confirm: bool = Field(
        ...,
        description="Deve ser True para confirmar"
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
    stats = {
        "candidates": db.query(func.count(Candidate.id)).scalar() or 0,
        "documents": db.query(func.count(Document.id)).scalar() or 0,
        "chunks": db.query(func.count(Chunk.id)).scalar() or 0,
        "embeddings": db.query(func.count(Embedding.id)).scalar() or 0,
        "experiences": db.query(func.count(Experience.id)).scalar() or 0,
        "profiles": db.query(func.count(CandidateProfile.id)).scalar() or 0,
        "conversations": db.query(func.count(ChatConversation.id)).scalar() or 0,
        "messages": db.query(func.count(ChatMessage.id)).scalar() or 0,
        "audit_logs": db.query(func.count(AuditLog.id)).scalar() or 0,
        "ai_usage_logs": db.query(func.count(AIUsageLog.id)).scalar() or 0,
    }
    stats["total_records"] = sum(stats.values())

    return DatabaseStatsResponse(**stats)


@router.post("/clear", response_model=ClearDataResponse)
def clear_database(
    data: ClearDataRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.update")),
):
    """
    Limpa dados do banco de dados com opcoes seletivas

    **ATENCAO:** Esta operacao e IRREVERSIVEL!

    Opcoes:
    - clear_candidates: Apaga candidatos, documentos, chunks, embeddings, experiencias, perfis
    - clear_documents: Apaga documentos e dados derivados (chunks, embeddings)
    - clear_conversations: Apaga conversas e mensagens do chat
    - clear_audit_logs: Apaga logs de auditoria
    - clear_ai_usage: Apaga logs de uso de IA
    - reset_sequences: Reseta contadores de ID para 1

    **Requer:** superuser ou permissao settings.update
    """
    if not data.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmacao necessaria: envie confirm=true para prosseguir"
        )

    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas superusuarios podem limpar o banco de dados"
        )

    deleted = {}
    sequences_reset = []

    try:
        # Ordem de delecao respeitando foreign keys (de baixo para cima)

        if data.clear_candidates:
            # Embeddings -> Chunks -> Documents -> Experiences ->
            # Profiles -> Consents -> Enrichments -> EncryptedPII -> Candidates
            count = db.query(Embedding).delete(synchronize_session=False)
            deleted["embeddings"] = count

            count = db.query(Chunk).delete(synchronize_session=False)
            deleted["chunks"] = count

            count = db.query(Document).delete(synchronize_session=False)
            deleted["documents"] = count

            count = db.query(Experience).delete(synchronize_session=False)
            deleted["experiences"] = count

            count = db.query(CandidateProfile).delete(synchronize_session=False)
            deleted["profiles"] = count

            count = db.query(Consent).delete(synchronize_session=False)
            deleted["consents"] = count

            count = db.query(ExternalEnrichment).delete(synchronize_session=False)
            deleted["enrichments"] = count

            count = db.query(EncryptedPII).delete(synchronize_session=False)
            deleted["encrypted_pii"] = count

            count = db.query(Candidate).delete(synchronize_session=False)
            deleted["candidates"] = count

        elif data.clear_documents:
            # Apenas documentos e derivados (sem apagar candidatos)
            count = db.query(Embedding).delete(synchronize_session=False)
            deleted["embeddings"] = count

            count = db.query(Chunk).delete(synchronize_session=False)
            deleted["chunks"] = count

            count = db.query(Document).delete(synchronize_session=False)
            deleted["documents"] = count

        if data.clear_conversations:
            count = db.query(ChatMessage).delete(synchronize_session=False)
            deleted["chat_messages"] = count

            count = db.query(ChatConversation).delete(synchronize_session=False)
            deleted["chat_conversations"] = count

        if data.clear_audit_logs:
            count = db.query(AuditLog).delete(synchronize_session=False)
            deleted["audit_logs"] = count

        if data.clear_ai_usage:
            count = db.query(AIUsageLog).delete(synchronize_session=False)
            deleted["ai_usage_logs"] = count

        db.commit()

        # Resetar sequences
        if data.reset_sequences:
            tables_to_reset = []

            if data.clear_candidates:
                tables_to_reset.extend([
                    "candidates", "documents", "chunks", "embeddings",
                    "experiences", "candidate_profiles", "consents",
                    "external_enrichments", "encrypted_pii",
                ])

            elif data.clear_documents:
                tables_to_reset.extend([
                    "documents", "chunks", "embeddings",
                ])

            if data.clear_conversations:
                tables_to_reset.extend([
                    "chat_conversations", "chat_messages",
                ])

            if data.clear_audit_logs:
                tables_to_reset.append("audit_logs")

            if data.clear_ai_usage:
                tables_to_reset.append("ai_usage_logs")

            for table in tables_to_reset:
                try:
                    db.execute(text(
                        f"ALTER SEQUENCE IF EXISTS {table}_id_seq RESTART WITH 1"
                    ))
                    sequences_reset.append(table)
                except Exception as e:
                    logger.warning(f"Erro ao resetar sequence de {table}: {e}")

            db.commit()

        # Audit log desta operacao
        audit = AuditLog(
            user_id=current_user.id,
            action="database_clear",
            entity="database",
            entity_id=0,
            metadata_json={
                "deleted": deleted,
                "sequences_reset": sequences_reset,
                "options": data.model_dump(),
            },
        )
        db.add(audit)
        db.commit()

        total_deleted = sum(deleted.values())
        logger.info(
            f"Database cleared by user {current_user.email}: "
            f"{total_deleted} records deleted, {len(sequences_reset)} sequences reset"
        )

        return ClearDataResponse(
            success=True,
            message=f"Banco limpo com sucesso: {total_deleted} registros removidos",
            deleted=deleted,
            sequences_reset=sequences_reset,
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao limpar banco: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao limpar banco de dados: {str(e)}"
        )


@router.post("/delete-candidates")
def delete_candidates_batch(
    data: DeleteCandidatesBatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("candidates.delete")),
):
    """
    Apaga candidatos em lote com todos os dados relacionados

    **Requer permissao:** candidates.delete
    """
    if not data.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmacao necessaria"
        )

    deleted_count = 0
    errors = []

    for cid in data.candidate_ids:
        try:
            candidate = db.query(Candidate).filter(Candidate.id == cid).first()
            if not candidate:
                errors.append(f"Candidato {cid} nao encontrado")
                continue

            # Cascade deletes are configured in the model, so just delete candidate
            db.delete(candidate)
            deleted_count += 1

        except Exception as e:
            errors.append(f"Erro ao apagar candidato {cid}: {str(e)}")

    db.commit()

    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="batch_delete_candidates",
        entity="candidates",
        entity_id=0,
        metadata_json={
            "candidate_ids": data.candidate_ids,
            "deleted_count": deleted_count,
            "errors": errors,
        },
    )
    db.add(audit)
    db.commit()

    return {
        "success": True,
        "deleted_count": deleted_count,
        "total_requested": len(data.candidate_ids),
        "errors": errors,
    }


@router.post("/reset-sequences")
def reset_all_sequences(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.update")),
):
    """
    Reseta contadores de ID (sequences) de todas as tabelas

    Util apos limpar dados para recomecar a contagem do ID 1.

    **ATENCAO:** So use apos confirmar que as tabelas estao vazias!

    **Requer:** superuser
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas superusuarios podem resetar sequences"
        )

    tables = [
        "candidates", "documents", "chunks", "embeddings",
        "experiences", "candidate_profiles", "consents",
        "external_enrichments", "encrypted_pii",
        "chat_conversations", "chat_messages",
        "audit_logs", "ai_usage_logs",
    ]

    reset = []
    errors = []

    for table in tables:
        try:
            # Verificar se tabela esta vazia
            result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.scalar()

            if count == 0:
                db.execute(text(
                    f"ALTER SEQUENCE IF EXISTS {table}_id_seq RESTART WITH 1"
                ))
                reset.append(table)
            else:
                # Resetar para max(id) + 1
                result = db.execute(text(f"SELECT COALESCE(MAX(id), 0) + 1 FROM {table}"))
                next_val = result.scalar()
                db.execute(text(
                    f"ALTER SEQUENCE IF EXISTS {table}_id_seq RESTART WITH {next_val}"
                ))
                reset.append(f"{table} (-> {next_val})")

        except Exception as e:
            errors.append(f"{table}: {str(e)}")

    db.commit()

    return {
        "success": True,
        "sequences_reset": reset,
        "errors": errors,
    }
