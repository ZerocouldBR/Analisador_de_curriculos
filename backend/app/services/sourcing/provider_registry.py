"""
Registro centralizado de providers de sourcing.

Mantém um dicionário singleton de SourceProvider registrados,
permitindo lookup por nome e filtragem por tipo.
"""
import logging
from typing import Dict, List, Optional

from app.services.sourcing.provider_base import ProviderType, SourceProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Singleton registry para providers de sourcing."""

    _providers: Dict[str, SourceProvider] = {}

    @classmethod
    def register(cls, provider: SourceProvider) -> None:
        """Registra um provider no registry."""
        name = provider.provider_name
        if name in cls._providers:
            logger.warning(f"Provider '{name}' ja registrado, sobrescrevendo")
        cls._providers[name] = provider
        logger.info(f"Provider '{name}' ({provider.provider_type.value}) registrado")

    @classmethod
    def get(cls, name: str) -> Optional[SourceProvider]:
        """Retorna um provider pelo nome."""
        return cls._providers.get(name)

    @classmethod
    def list_all(cls) -> List[SourceProvider]:
        """Lista todos os providers registrados."""
        return list(cls._providers.values())

    @classmethod
    def list_names(cls) -> List[str]:
        """Lista nomes de todos os providers registrados."""
        return list(cls._providers.keys())

    @classmethod
    def list_by_type(cls, provider_type: ProviderType) -> List[SourceProvider]:
        """Lista providers filtrados por tipo."""
        return [
            p for p in cls._providers.values()
            if p.provider_type == provider_type
        ]

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Verifica se um provider esta registrado."""
        return name in cls._providers

    @classmethod
    def clear(cls) -> None:
        """Remove todos os providers (usado em testes)."""
        cls._providers.clear()
