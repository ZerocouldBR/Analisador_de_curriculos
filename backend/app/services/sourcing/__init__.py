"""
Modulo de sourcing hibrido de candidatos.

Importa todos os providers para auto-registro no ProviderRegistry.
"""
from app.services.sourcing.provider_base import (
    CandidateCanonicalProfile,
    ProviderHealthStatus,
    ProviderType,
    RateLimitStatus,
    SourceProvider,
)
from app.services.sourcing.provider_registry import ProviderRegistry
from app.services.sourcing.candidate_normalizer import CandidateNormalizer

# Auto-registrar providers ao importar o modulo
from app.services.sourcing import linkedin_provider  # noqa: F401
from app.services.sourcing import csv_import_provider  # noqa: F401
from app.services.sourcing import xlsx_import_provider  # noqa: F401
from app.services.sourcing import manual_entry_provider  # noqa: F401
from app.services.sourcing import webhook_provider  # noqa: F401
from app.services.sourcing import external_partner_provider  # noqa: F401

__all__ = [
    "CandidateCanonicalProfile",
    "ProviderHealthStatus",
    "ProviderType",
    "RateLimitStatus",
    "SourceProvider",
    "ProviderRegistry",
    "CandidateNormalizer",
]
