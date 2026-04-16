"""
Endpoints autenticados (RH) para gerar e gerenciar magic links de candidatos.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.core.dependencies import require_permission
from app.core.config import settings
from app.db.database import get_db
from app.db.models import AuditLog, Candidate, User
from app.schemas.candidate_portal import (
    AccessTokenResponse,
    AccessTokenListItem,
    GenerateTokenRequest,
)
from app.services.candidate_access_token_service import CandidateAccessTokenService


router = APIRouter(prefix="/candidates", tags=["candidate-access-tokens"])


def _check_company(current_user: User, candidate: Candidate) -> None:
    if settings.multi_tenant_enabled and not current_user.is_superuser and current_user.company_id:
        if candidate.company_id != current_user.company_id:
            raise HTTPException(status_code=404, detail="Candidato nao encontrado")


def _build_portal_url(request: Request, token_raw: str) -> str:
    # Preferencia: PUBLIC_BASE_URL se definido; fallback para host da request
    base = getattr(settings, "public_base_url", None)
    if not base:
        scheme = request.url.scheme
        host = request.headers.get("host") or request.url.netloc
        base = f"{scheme}://{host}"
    return f"{base.rstrip('/')}/me/{token_raw}"


@router.post(
    "/{candidate_id}/access-tokens",
    response_model=AccessTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_access_token(
    candidate_id: int,
    data: GenerateTokenRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("candidates.update")),
):
    """
    Gera um magic link (token) para o candidato acessar seu proprio perfil
    e ajusta-lo. Requer permissao `candidates.update`.

    Devolve a URL completa para enviar ao candidato (RH envia por email/WhatsApp).
    """
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidato nao encontrado")
    _check_company(current_user, candidate)

    token = CandidateAccessTokenService.generate_token(
        db=db,
        candidate_id=candidate_id,
        created_by=current_user.id,
        expires_in_hours=data.expires_in_hours or 72,
        purpose=data.purpose or "self_edit",
    )

    # Audit log
    try:
        audit = AuditLog(
            user_id=current_user.id,
            action="generate_candidate_access_token",
            entity="candidate",
            entity_id=candidate_id,
            metadata_json={"token_id": token.id, "expires_at": str(token.expires_at)},
        )
        db.add(audit)
        db.commit()
    except Exception:
        pass

    url = _build_portal_url(request, token.token)
    return AccessTokenResponse(
        id=token.id,
        candidate_id=token.candidate_id,
        token=token.token,
        url=url,
        expires_at=token.expires_at,
        created_at=token.created_at,
        revoked_at=token.revoked_at,
        last_used_at=token.last_used_at,
        use_count=token.use_count or 0,
        purpose=token.purpose or "self_edit",
    )


@router.get(
    "/{candidate_id}/access-tokens",
    response_model=List[AccessTokenListItem],
)
def list_access_tokens(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("candidates.read")),
):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidato nao encontrado")
    _check_company(current_user, candidate)
    return CandidateAccessTokenService.list_for_candidate(db, candidate_id)


@router.delete(
    "/{candidate_id}/access-tokens/{token_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_access_token(
    candidate_id: int,
    token_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("candidates.update")),
):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidato nao encontrado")
    _check_company(current_user, candidate)

    ok = CandidateAccessTokenService.revoke(db, token_id, candidate_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Token nao encontrado ou ja revogado")
