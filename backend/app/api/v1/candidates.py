from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.database import get_db
from app.schemas.candidate import (
    CandidateResponse,
    CandidateCreate,
    CandidateUpdate,
    DocumentResponse
)
from app.services.candidate_service import CandidateService
from app.core.dependencies import get_current_user, require_permission
from app.db.models import User

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.get("/", response_model=List[CandidateResponse])
def list_candidates(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    city: Optional[str] = Query(None, description="Filtrar por cidade"),
    state: Optional[str] = Query(None, description="Filtrar por estado"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("candidates.read"))
):
    """
    Lista todos os candidatos com filtros opcionais

    **Requer permissão:** candidates.read
    """
    candidates = CandidateService.get_candidates(
        db,
        skip=skip,
        limit=limit,
        city=city,
        state=state
    )
    return candidates


@router.get("/{candidate_id}", response_model=CandidateResponse)
def get_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("candidates.read"))
):
    """
    Obtém um candidato específico por ID

    **Requer permissão:** candidates.read
    """
    candidate = CandidateService.get_candidate(db, candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidato {candidate_id} não encontrado"
        )
    return candidate


@router.post("/", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
def create_candidate(
    candidate: CandidateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("candidates.create"))
):
    """
    Cria um novo candidato

    **Requer permissão:** candidates.create
    """
    return CandidateService.create_candidate(db, candidate, user_id=current_user.id)


@router.put("/{candidate_id}", response_model=CandidateResponse)
def update_candidate(
    candidate_id: int,
    candidate_update: CandidateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("candidates.update"))
):
    """
    Atualiza um candidato existente

    **Requer permissão:** candidates.update
    """
    updated = CandidateService.update_candidate(db, candidate_id, candidate_update, user_id=current_user.id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidato {candidate_id} não encontrado"
        )
    return updated


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("candidates.delete"))
):
    """
    Remove um candidato e todos os seus dados relacionados (currículos, experiências, etc.)

    ATENÇÃO: Esta operação é irreversível e remove:
    - Dados pessoais do candidato
    - Todos os currículos e documentos
    - Chunks e embeddings gerados
    - Experiências profissionais
    - Dados de enriquecimento (LinkedIn, etc.)

    Conforme LGPD, um log de auditoria é criado antes da remoção.

    **Requer permissão:** candidates.delete
    """
    deleted = CandidateService.delete_candidate(db, candidate_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidato {candidate_id} não encontrado"
        )


# Endpoints para gerenciar documentos/currículos

@router.get("/{candidate_id}/documents", response_model=List[DocumentResponse])
def list_candidate_documents(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("candidates.read"))
):
    """
    Lista todos os documentos/currículos de um candidato

    **Requer permissão:** candidates.read
    """
    candidate = CandidateService.get_candidate(db, candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidato {candidate_id} não encontrado"
        )

    documents = CandidateService.get_candidate_documents(db, candidate_id)
    return documents


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("documents.delete"))
):
    """
    Remove um currículo/documento específico

    Esta operação remove:
    - O documento do sistema
    - Todos os chunks extraídos do documento
    - Todos os embeddings gerados a partir dos chunks

    Um log de auditoria é criado antes da remoção.

    **Requer permissão:** documents.delete
    """
    deleted = CandidateService.delete_document(db, document_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento {document_id} não encontrado"
        )
