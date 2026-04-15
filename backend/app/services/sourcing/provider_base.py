"""
Classes base para o sistema de sourcing hibrido.

Define a interface abstrata SourceProvider que todo provider deve implementar,
o modelo CandidateCanonicalProfile para normalizacao de dados entre fontes,
e tipos auxiliares.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ProviderType(str, Enum):
    """Tipos de provider de sourcing"""
    API = "api"
    FILE = "file"
    MANUAL = "manual"
    WEBHOOK = "webhook"


@dataclass
class CandidateCanonicalProfile:
    """Representacao canonica de um candidato, independente da fonte."""
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    headline: Optional[str] = None
    about: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "Brasil"
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    current_company: Optional[str] = None
    current_role: Optional[str] = None
    seniority: Optional[str] = None
    skills: List[str] = field(default_factory=list)
    certifications: List[str] = field(default_factory=list)
    education: List[Dict[str, Any]] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)
    experiences: List[Dict[str, Any]] = field(default_factory=list)
    raw_data: Optional[Dict[str, Any]] = None
    external_id: Optional[str] = None
    external_url: Optional[str] = None
    confidence: float = 0.5


@dataclass
class ProviderHealthStatus:
    """Status de saude de um provider"""
    healthy: bool
    message: str
    remaining_quota: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class RateLimitStatus:
    """Status de rate limit de um provider"""
    requests_remaining: Optional[int] = None
    requests_limit: Optional[int] = None
    reset_at: Optional[str] = None


class SourceProvider(ABC):
    """Interface abstrata para provedores de candidatos.

    Todo provider de sourcing deve implementar esta interface.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Nome unico do provider (ex: 'linkedin', 'csv_import')"""
        ...

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """Tipo do provider"""
        ...

    @abstractmethod
    async def health_check(self, config: Dict[str, Any]) -> ProviderHealthStatus:
        """Verifica se o provider esta operacional."""
        ...

    @abstractmethod
    async def search_candidates(
        self,
        config: Dict[str, Any],
        criteria: Dict[str, Any],
        limit: int = 50,
    ) -> List[CandidateCanonicalProfile]:
        """Busca candidatos no provider com base nos criterios."""
        ...

    @abstractmethod
    async def fetch_candidate_by_external_id(
        self,
        config: Dict[str, Any],
        external_id: str,
    ) -> Optional[CandidateCanonicalProfile]:
        """Busca um candidato especifico pelo ID externo."""
        ...

    def normalize_candidate(self, raw_data: Dict[str, Any]) -> CandidateCanonicalProfile:
        """Normaliza payload cru do provider para o perfil canonico.

        Override nos providers que precisam de logica customizada.
        """
        raise NotImplementedError(
            f"Provider {self.provider_name} nao implementa normalize_candidate"
        )

    async def get_rate_limit_status(self, config: Dict[str, Any]) -> RateLimitStatus:
        """Retorna o status atual de rate limit do provider."""
        return RateLimitStatus()
