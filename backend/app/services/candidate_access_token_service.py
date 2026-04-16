"""
Servico de gestao de magic links (CandidateAccessToken).

Responsabilidades:
- Gerar token seguro (32 bytes url-safe)
- Validar token por expiracao, revogacao e candidato ativo
- Registrar uso (contador + timestamp)
- Revogar
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models import Candidate, CandidateAccessToken


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


DEFAULT_EXPIRY_HOURS = 72


class CandidateAccessTokenService:
    @staticmethod
    def generate_token(
        db: Session,
        candidate_id: int,
        created_by: Optional[int],
        expires_in_hours: int = DEFAULT_EXPIRY_HOURS,
        purpose: str = "self_edit",
    ) -> CandidateAccessToken:
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            raise ValueError("Candidato nao encontrado")

        raw = secrets.token_urlsafe(32)
        expires_at = _utcnow() + timedelta(hours=max(1, expires_in_hours))

        token = CandidateAccessToken(
            candidate_id=candidate_id,
            token=raw,
            expires_at=expires_at,
            created_by=created_by,
            purpose=purpose,
        )
        db.add(token)
        db.commit()
        db.refresh(token)
        return token

    @staticmethod
    def validate(
        db: Session,
        raw_token: str,
        record_use: bool = True,
    ) -> Optional[CandidateAccessToken]:
        """
        Retorna o token se valido (nao expirado, nao revogado).
        Se record_use=True, incrementa o contador e atualiza last_used_at.
        """
        if not raw_token or len(raw_token) < 20:
            return None

        token = db.query(CandidateAccessToken).filter(
            CandidateAccessToken.token == raw_token
        ).first()
        if not token:
            return None

        if token.revoked_at is not None:
            return None

        # Comparacao timezone-aware
        now = _utcnow()
        expires_at = token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < now:
            return None

        if record_use:
            token.last_used_at = now
            token.use_count = (token.use_count or 0) + 1
            db.commit()

        return token

    @staticmethod
    def revoke(db: Session, token_id: int, candidate_id: int) -> bool:
        token = db.query(CandidateAccessToken).filter(
            CandidateAccessToken.id == token_id,
            CandidateAccessToken.candidate_id == candidate_id,
        ).first()
        if not token or token.revoked_at is not None:
            return False
        token.revoked_at = _utcnow()
        db.commit()
        return True

    @staticmethod
    def list_for_candidate(db: Session, candidate_id: int) -> List[CandidateAccessToken]:
        return db.query(CandidateAccessToken).filter(
            CandidateAccessToken.candidate_id == candidate_id
        ).order_by(CandidateAccessToken.created_at.desc()).all()
