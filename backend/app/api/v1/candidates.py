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

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.get("/", response_model=List[CandidateResponse])
def list_candidates(
    skip: int = 0,
    limit: int = 100,
    city: Optional[str] = Query(None, description="Filtrar por cidade"),
    state: Optional[str] = Query(None, description="Filtrar por estado"),
    db: Session = Depends(get_db)
):
    """Lista todos os candidatos com filtros opcionais"""
    candidates = CandidateService.get_candidates(
        db,
        skip=skip,
        limit=limit,
        city=city,
        state=state
    )
    return candidates


@router.get("/{candidate_id}", response_model=CandidateResponse)
def get_candidate(candidate_id: int, db: Session = Depends(get_db)):
    """Obtém um candidato específico por ID"""
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
    # TODO: Adicionar autenticação e obter user_id do token
):
    """Cria um novo candidato"""
    return CandidateService.create_candidate(db, candidate)


@router.put("/{candidate_id}", response_model=CandidateResponse)
def update_candidate(
    candidate_id: int,
    candidate_update: CandidateUpdate,
    db: Session = Depends(get_db),
    # TODO: Adicionar autenticação e obter user_id do token
):
    """Atualiza um candidato existente"""
    updated = CandidateService.update_candidate(db, candidate_id, candidate_update)
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
    # TODO: Adicionar autenticação e obter user_id do token
):
    """
    Remove um candidato e todos os seus dados relacionados (currículos, experiências, etc.)

    ⚠️ ATENÇÃO: Esta operação é irreversível e remove:
    - Dados pessoais do candidato
    - Todos os currículos e documentos
    - Chunks e embeddings gerados
    - Experiências profissionais
    - Dados de enriquecimento (LinkedIn, etc.)

    Conforme LGPD, um log de auditoria é criado antes da remoção.
    """
    deleted = CandidateService.delete_candidate(db, candidate_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidato {candidate_id} não encontrado"
        )


# Endpoints para gerenciar documentos/currículos

@router.get("/{candidate_id}/documents", response_model=List[DocumentResponse])
def list_candidate_documents(
    candidate_id: int,
    db: Session = Depends(get_db)
):
    """Lista todos os documentos/currículos de um candidato"""
    # Verificar se candidato existe
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
    # TODO: Adicionar autenticação e obter user_id do token
):
    """
    Remove um currículo/documento específico

    Esta operação remove:
    - O documento do sistema
    - Todos os chunks extraídos do documento
    - Todos os embeddings gerados a partir dos chunks

    Um log de auditoria é criado antes da remoção.
    """
    deleted = CandidateService.delete_document(db, document_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento {document_id} não encontrado"
        )
