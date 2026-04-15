"""
Provider de sourcing para webhooks.

Recebe payloads de sistemas externos via webhook
e normaliza para CandidateCanonicalProfile.
"""
import hashlib
import hmac
import logging
from typing import Any, Dict, List, Optional

from app.services.sourcing.provider_base import (
    CandidateCanonicalProfile,
    ProviderHealthStatus,
    ProviderType,
    SourceProvider,
)
from app.services.sourcing.provider_registry import ProviderRegistry

logger = logging.getLogger(__name__)


class WebhookProvider(SourceProvider):
    """Provider para recepcao de candidatos via webhook."""

    @property
    def provider_name(self) -> str:
        return "webhook"

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.WEBHOOK

    async def health_check(self, config: Dict[str, Any]) -> ProviderHealthStatus:
        """Verifica se o webhook esta configurado com secret."""
        has_secret = bool(config.get("webhook_secret"))
        return ProviderHealthStatus(
            healthy=has_secret,
            message="Webhook configurado" if has_secret else "webhook_secret nao definido",
        )

    async def search_candidates(
        self,
        config: Dict[str, Any],
        criteria: Dict[str, Any],
        limit: int = 50,
    ) -> List[CandidateCanonicalProfile]:
        """Webhooks nao suportam busca - dados chegam via push."""
        return []

    async def fetch_candidate_by_external_id(
        self,
        config: Dict[str, Any],
        external_id: str,
    ) -> Optional[CandidateCanonicalProfile]:
        return None

    def validate_signature(
        self, payload: bytes, signature: str, secret: str
    ) -> bool:
        """Valida assinatura HMAC-SHA256 do webhook."""
        expected = hmac.new(
            secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(f"sha256={expected}", signature)

    def normalize_candidate(self, raw_data: Dict[str, Any]) -> CandidateCanonicalProfile:
        """Normaliza payload de webhook para perfil canonico.

        Espera payload no formato:
        {
            "candidate": {
                "name": "...",
                "email": "...",
                "phone": "...",
                ...
            },
            "source_id": "external_system_id",
            "source_url": "https://..."
        }
        """
        candidate_data = raw_data.get("candidate", raw_data)

        skills = candidate_data.get("skills", [])
        if isinstance(skills, str):
            skills = [s.strip() for s in skills.split(",") if s.strip()]

        return CandidateCanonicalProfile(
            full_name=candidate_data.get("name") or candidate_data.get("full_name", "N/A"),
            email=candidate_data.get("email"),
            phone=candidate_data.get("phone"),
            city=candidate_data.get("city"),
            state=candidate_data.get("state"),
            country=candidate_data.get("country", "Brasil"),
            linkedin_url=candidate_data.get("linkedin_url"),
            github_url=candidate_data.get("github_url"),
            current_company=candidate_data.get("current_company") or candidate_data.get("company"),
            current_role=candidate_data.get("current_role") or candidate_data.get("title"),
            skills=skills,
            external_id=raw_data.get("source_id"),
            external_url=raw_data.get("source_url"),
            confidence=0.5,
            raw_data=raw_data,
        )


ProviderRegistry.register(WebhookProvider())
