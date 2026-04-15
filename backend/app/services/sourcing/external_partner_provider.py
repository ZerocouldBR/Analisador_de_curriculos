"""
Provider generico para parceiros externos.

Adapter HTTP configuravel que permite conectar a qualquer
API de recrutamento/ATS sem alterar o codigo core.
"""
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.services.sourcing.provider_base import (
    CandidateCanonicalProfile,
    ProviderHealthStatus,
    ProviderType,
    RateLimitStatus,
    SourceProvider,
)
from app.services.sourcing.provider_registry import ProviderRegistry

logger = logging.getLogger(__name__)


def _extract_field(data: Dict[str, Any], path: str) -> Any:
    """Extrai campo de um dict usando path separado por ponto.

    Exemplo: _extract_field(data, "person.name") -> data["person"]["name"]
    """
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if current is None:
            return None
    return current


class ExternalPartnerProvider(SourceProvider):
    """Provider generico para APIs de parceiros externos.

    Configuracao esperada no config_json:
    {
        "base_url": "https://api.partner.com/v1",
        "auth_header": "Authorization",
        "auth_value": "Bearer <token>",
        "search_endpoint": "/candidates/search",
        "detail_endpoint": "/candidates/{external_id}",
        "health_endpoint": "/health",
        "response_mapping": {
            "results_path": "data.candidates",
            "full_name": "name",
            "email": "contact.email",
            "phone": "contact.phone",
            "city": "location.city",
            "state": "location.state",
            "current_role": "current_position.title",
            "current_company": "current_position.company",
            "skills": "skills",
            "linkedin_url": "social.linkedin",
            "external_id": "id"
        },
        "request_timeout": 30
    }
    """

    @property
    def provider_name(self) -> str:
        return "external_partner"

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.API

    async def health_check(self, config: Dict[str, Any]) -> ProviderHealthStatus:
        base_url = config.get("base_url")
        if not base_url:
            return ProviderHealthStatus(
                healthy=False,
                message="base_url nao configurado",
            )

        health_endpoint = config.get("health_endpoint", "/health")
        timeout = config.get("request_timeout", 30)

        try:
            headers = {}
            if config.get("auth_header") and config.get("auth_value"):
                headers[config["auth_header"]] = config["auth_value"]

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    f"{base_url.rstrip('/')}{health_endpoint}",
                    headers=headers,
                )
                if response.status_code == 200:
                    return ProviderHealthStatus(
                        healthy=True,
                        message="Partner API operacional",
                    )
                return ProviderHealthStatus(
                    healthy=False,
                    message=f"Partner API retornou status {response.status_code}",
                )
        except Exception as e:
            return ProviderHealthStatus(
                healthy=False,
                message=f"Erro ao conectar: {str(e)}",
            )

    async def search_candidates(
        self,
        config: Dict[str, Any],
        criteria: Dict[str, Any],
        limit: int = 50,
    ) -> List[CandidateCanonicalProfile]:
        base_url = config.get("base_url")
        search_endpoint = config.get("search_endpoint", "/candidates/search")
        mapping = config.get("response_mapping", {})
        timeout = config.get("request_timeout", 30)

        if not base_url:
            logger.error("External partner: base_url nao configurado")
            return []

        headers = {}
        if config.get("auth_header") and config.get("auth_value"):
            headers[config["auth_header"]] = config["auth_value"]

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{base_url.rstrip('/')}{search_endpoint}",
                    json={**criteria, "limit": limit},
                    headers=headers,
                )

                if response.status_code != 200:
                    logger.error(
                        f"External partner search erro {response.status_code}: {response.text[:200]}"
                    )
                    return []

                data = response.json()
                results_path = mapping.get("results_path", "results")
                items = _extract_field(data, results_path)

                if not isinstance(items, list):
                    logger.warning("External partner: results_path nao retornou lista")
                    return []

                profiles = []
                for item in items[:limit]:
                    profile = self._map_to_profile(item, mapping)
                    if profile:
                        profiles.append(profile)

                return profiles

        except Exception as e:
            logger.error(f"External partner search erro: {str(e)}")
            return []

    async def fetch_candidate_by_external_id(
        self,
        config: Dict[str, Any],
        external_id: str,
    ) -> Optional[CandidateCanonicalProfile]:
        base_url = config.get("base_url")
        detail_endpoint = config.get("detail_endpoint", "/candidates/{external_id}")
        mapping = config.get("response_mapping", {})
        timeout = config.get("request_timeout", 30)

        if not base_url:
            return None

        url = f"{base_url.rstrip('/')}{detail_endpoint}".replace("{external_id}", external_id)
        headers = {}
        if config.get("auth_header") and config.get("auth_value"):
            headers[config["auth_header"]] = config["auth_value"]

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url, headers=headers)
                if response.status_code != 200:
                    return None
                data = response.json()
                return self._map_to_profile(data, mapping)
        except Exception as e:
            logger.error(f"External partner fetch erro: {str(e)}")
            return None

    def _map_to_profile(
        self, item: Dict[str, Any], mapping: Dict[str, str]
    ) -> Optional[CandidateCanonicalProfile]:
        """Mapeia um item da resposta do parceiro para perfil canonico."""
        full_name = _extract_field(item, mapping.get("full_name", "name"))
        if not full_name:
            return None

        skills = _extract_field(item, mapping.get("skills", "skills")) or []
        if isinstance(skills, str):
            skills = [s.strip() for s in skills.split(",") if s.strip()]

        return CandidateCanonicalProfile(
            full_name=full_name,
            email=_extract_field(item, mapping.get("email", "email")),
            phone=_extract_field(item, mapping.get("phone", "phone")),
            city=_extract_field(item, mapping.get("city", "city")),
            state=_extract_field(item, mapping.get("state", "state")),
            country=_extract_field(item, mapping.get("country", "country")) or "Brasil",
            linkedin_url=_extract_field(item, mapping.get("linkedin_url", "linkedin_url")),
            github_url=_extract_field(item, mapping.get("github_url", "github_url")),
            current_company=_extract_field(item, mapping.get("current_company", "current_company")),
            current_role=_extract_field(item, mapping.get("current_role", "current_role")),
            skills=skills,
            external_id=str(_extract_field(item, mapping.get("external_id", "id")) or ""),
            confidence=0.5,
            raw_data=item,
        )

    async def get_rate_limit_status(self, config: Dict[str, Any]) -> RateLimitStatus:
        return RateLimitStatus()


ProviderRegistry.register(ExternalPartnerProvider())
