"""
Provider de sourcing para LinkedIn.

Adapter sobre o LinkedInService existente, delegando chamadas
ao Proxycurl/RapidAPI/Official e normalizando para CandidateCanonicalProfile.
"""
import logging
from typing import Any, Dict, List, Optional

from app.services.sourcing.provider_base import (
    CandidateCanonicalProfile,
    ProviderHealthStatus,
    ProviderType,
    RateLimitStatus,
    SourceProvider,
)
from app.services.sourcing.provider_registry import ProviderRegistry

logger = logging.getLogger(__name__)


class LinkedInProvider(SourceProvider):
    """Provider que integra com LinkedIn via Proxycurl/Official API."""

    @property
    def provider_name(self) -> str:
        return "linkedin"

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.API

    async def health_check(self, config: Dict[str, Any]) -> ProviderHealthStatus:
        """Verifica status da integracao LinkedIn."""
        from app.services.linkedin_service import LinkedInService

        status = LinkedInService.get_config_status()
        return ProviderHealthStatus(
            healthy=status.get("ready", False),
            message=status.get("message", ""),
            metadata={
                "provider": status.get("provider"),
                "credentials_configured": status.get("credentials_configured"),
            },
        )

    async def search_candidates(
        self,
        config: Dict[str, Any],
        criteria: Dict[str, Any],
        limit: int = 50,
    ) -> List[CandidateCanonicalProfile]:
        """Busca candidatos via Proxycurl Person Search."""
        from app.services.linkedin_service import LinkedInService

        criteria["limit"] = limit
        results = await LinkedInService.search_via_proxycurl(criteria)

        profiles = []
        for result in results:
            profile = CandidateCanonicalProfile(
                full_name=result.get("name", "N/A"),
                headline=result.get("headline"),
                linkedin_url=result.get("linkedin_url"),
                city=result.get("location"),
                external_id=result.get("linkedin_url"),
                external_url=result.get("linkedin_url"),
                confidence=0.6,
                raw_data=result,
            )
            profiles.append(profile)

        return profiles

    async def fetch_candidate_by_external_id(
        self,
        config: Dict[str, Any],
        external_id: str,
    ) -> Optional[CandidateCanonicalProfile]:
        """Busca perfil completo via URL do LinkedIn."""
        from app.services.linkedin_service import LinkedInService

        data = await LinkedInService.extract_profile_data(external_id)
        if not data:
            return None
        return self.normalize_candidate(data)

    def normalize_candidate(self, raw_data: Dict[str, Any]) -> CandidateCanonicalProfile:
        """Normaliza payload Proxycurl/scraping para perfil canonico."""
        location = raw_data.get("location", "")
        city = None
        state = None
        if location:
            parts = [p.strip() for p in location.split(",")]
            if len(parts) >= 1:
                city = parts[0]
            if len(parts) >= 2:
                state = parts[1]

        experiences = raw_data.get("experiences", [])
        current_company = None
        current_role = None
        if experiences:
            latest = experiences[0]
            current_company = latest.get("company")
            current_role = latest.get("title")

        return CandidateCanonicalProfile(
            full_name=raw_data.get("full_name") or "N/A",
            headline=raw_data.get("headline"),
            about=raw_data.get("about"),
            city=city,
            state=state,
            linkedin_url=raw_data.get("profile_url"),
            skills=raw_data.get("skills", []),
            certifications=raw_data.get("certifications", []),
            education=raw_data.get("education", []),
            languages=raw_data.get("languages", []),
            experiences=experiences,
            current_company=current_company,
            current_role=current_role,
            external_id=raw_data.get("profile_url"),
            external_url=raw_data.get("profile_url"),
            confidence=0.8 if raw_data.get("source") == "proxycurl" else 0.4,
            raw_data=raw_data,
        )

    async def get_rate_limit_status(self, config: Dict[str, Any]) -> RateLimitStatus:
        return RateLimitStatus()


ProviderRegistry.register(LinkedInProvider())
