"""
Provider de sourcing para entrada manual.

Registra candidatos inseridos manualmente via formulario
e garante que cada entrada manual tenha um CandidateSource.
"""
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


class ManualEntryProvider(SourceProvider):
    """Provider para candidatos inseridos manualmente."""

    @property
    def provider_name(self) -> str:
        return "manual"

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.MANUAL

    async def health_check(self, config: Dict[str, Any]) -> ProviderHealthStatus:
        return ProviderHealthStatus(
            healthy=True,
            message="Entrada manual sempre disponivel",
        )

    async def search_candidates(
        self,
        config: Dict[str, Any],
        criteria: Dict[str, Any],
        limit: int = 50,
    ) -> List[CandidateCanonicalProfile]:
        """Entrada manual nao suporta busca - candidatos sao inseridos via API."""
        return []

    async def fetch_candidate_by_external_id(
        self,
        config: Dict[str, Any],
        external_id: str,
    ) -> Optional[CandidateCanonicalProfile]:
        return None

    def normalize_candidate(self, raw_data: Dict[str, Any]) -> CandidateCanonicalProfile:
        """Normaliza dados de entrada manual."""
        skills = raw_data.get("skills", [])
        if isinstance(skills, str):
            skills = [s.strip() for s in skills.split(",") if s.strip()]

        return CandidateCanonicalProfile(
            full_name=raw_data.get("full_name", "N/A"),
            email=raw_data.get("email"),
            phone=raw_data.get("phone"),
            city=raw_data.get("city"),
            state=raw_data.get("state"),
            country=raw_data.get("country", "Brasil"),
            linkedin_url=raw_data.get("linkedin_url"),
            github_url=raw_data.get("github_url"),
            portfolio_url=raw_data.get("portfolio_url"),
            current_company=raw_data.get("current_company"),
            current_role=raw_data.get("current_role"),
            seniority=raw_data.get("seniority"),
            headline=raw_data.get("headline"),
            about=raw_data.get("about"),
            skills=skills,
            confidence=1.0,
            raw_data=raw_data,
        )


ProviderRegistry.register(ManualEntryProvider())
