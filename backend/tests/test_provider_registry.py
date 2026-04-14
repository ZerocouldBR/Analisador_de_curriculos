"""
Tests for the ProviderRegistry singleton.
"""
import pytest
from typing import Any, Dict, List, Optional

from app.services.sourcing.provider_base import (
    CandidateCanonicalProfile,
    ProviderHealthStatus,
    ProviderType,
    SourceProvider,
)
from app.services.sourcing.provider_registry import ProviderRegistry


# ================================================================
# Mock Provider
# ================================================================

class MockAPIProvider(SourceProvider):
    """Mock API provider for testing."""

    @property
    def provider_name(self) -> str:
        return "mock_api"

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.API

    async def health_check(self, config: Dict[str, Any]) -> ProviderHealthStatus:
        return ProviderHealthStatus(healthy=True, message="OK")

    async def search_candidates(
        self,
        config: Dict[str, Any],
        criteria: Dict[str, Any],
        limit: int = 50,
    ) -> List[CandidateCanonicalProfile]:
        return []

    async def fetch_candidate_by_external_id(
        self,
        config: Dict[str, Any],
        external_id: str,
    ) -> Optional[CandidateCanonicalProfile]:
        return None


class MockFileProvider(SourceProvider):
    """Mock file provider for testing."""

    @property
    def provider_name(self) -> str:
        return "mock_file"

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.FILE

    async def health_check(self, config: Dict[str, Any]) -> ProviderHealthStatus:
        return ProviderHealthStatus(healthy=True, message="File OK")

    async def search_candidates(
        self,
        config: Dict[str, Any],
        criteria: Dict[str, Any],
        limit: int = 50,
    ) -> List[CandidateCanonicalProfile]:
        return []

    async def fetch_candidate_by_external_id(
        self,
        config: Dict[str, Any],
        external_id: str,
    ) -> Optional[CandidateCanonicalProfile]:
        return None


class MockManualProvider(SourceProvider):
    """Mock manual provider for testing."""

    @property
    def provider_name(self) -> str:
        return "mock_manual"

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.MANUAL

    async def health_check(self, config: Dict[str, Any]) -> ProviderHealthStatus:
        return ProviderHealthStatus(healthy=True, message="Manual OK")

    async def search_candidates(
        self,
        config: Dict[str, Any],
        criteria: Dict[str, Any],
        limit: int = 50,
    ) -> List[CandidateCanonicalProfile]:
        return []

    async def fetch_candidate_by_external_id(
        self,
        config: Dict[str, Any],
        external_id: str,
    ) -> Optional[CandidateCanonicalProfile]:
        return None


# ================================================================
# Tests
# ================================================================

@pytest.fixture(autouse=True)
def clean_registry():
    """Ensure registry is clean before and after each test."""
    ProviderRegistry.clear()
    yield
    ProviderRegistry.clear()


class TestProviderRegistry:
    def test_register_provider(self):
        """Should register a provider successfully."""
        provider = MockAPIProvider()
        ProviderRegistry.register(provider)

        assert ProviderRegistry.is_registered("mock_api")

    def test_get_by_name(self):
        """Should retrieve a provider by name."""
        provider = MockAPIProvider()
        ProviderRegistry.register(provider)

        result = ProviderRegistry.get("mock_api")
        assert result is not None
        assert result.provider_name == "mock_api"
        assert result.provider_type == ProviderType.API

    def test_get_nonexistent(self):
        """Should return None for unregistered provider."""
        result = ProviderRegistry.get("does_not_exist")
        assert result is None

    def test_list_all(self):
        """Should list all registered providers."""
        ProviderRegistry.register(MockAPIProvider())
        ProviderRegistry.register(MockFileProvider())
        ProviderRegistry.register(MockManualProvider())

        all_providers = ProviderRegistry.list_all()
        assert len(all_providers) == 3

        names = {p.provider_name for p in all_providers}
        assert names == {"mock_api", "mock_file", "mock_manual"}

    def test_list_all_empty(self):
        """Should return empty list when no providers are registered."""
        assert ProviderRegistry.list_all() == []

    def test_list_by_type_api(self):
        """Should filter providers by type."""
        ProviderRegistry.register(MockAPIProvider())
        ProviderRegistry.register(MockFileProvider())
        ProviderRegistry.register(MockManualProvider())

        api_providers = ProviderRegistry.list_by_type(ProviderType.API)
        assert len(api_providers) == 1
        assert api_providers[0].provider_name == "mock_api"

    def test_list_by_type_file(self):
        """Should return file-type providers."""
        ProviderRegistry.register(MockAPIProvider())
        ProviderRegistry.register(MockFileProvider())

        file_providers = ProviderRegistry.list_by_type(ProviderType.FILE)
        assert len(file_providers) == 1
        assert file_providers[0].provider_name == "mock_file"

    def test_list_by_type_empty(self):
        """Should return empty list when no providers match the type."""
        ProviderRegistry.register(MockAPIProvider())

        webhook_providers = ProviderRegistry.list_by_type(ProviderType.WEBHOOK)
        assert webhook_providers == []

    def test_is_registered_true(self):
        """Should return True for registered providers."""
        ProviderRegistry.register(MockAPIProvider())
        assert ProviderRegistry.is_registered("mock_api") is True

    def test_is_registered_false(self):
        """Should return False for unregistered providers."""
        assert ProviderRegistry.is_registered("unknown") is False

    def test_clear(self):
        """Should remove all providers."""
        ProviderRegistry.register(MockAPIProvider())
        ProviderRegistry.register(MockFileProvider())
        assert len(ProviderRegistry.list_all()) == 2

        ProviderRegistry.clear()
        assert len(ProviderRegistry.list_all()) == 0
        assert ProviderRegistry.is_registered("mock_api") is False

    def test_register_overwrites_same_name(self):
        """Registering a provider with the same name should overwrite."""
        provider1 = MockAPIProvider()
        ProviderRegistry.register(provider1)

        # Create a second mock with same name but different type
        class AnotherMockAPI(SourceProvider):
            @property
            def provider_name(self) -> str:
                return "mock_api"

            @property
            def provider_type(self) -> ProviderType:
                return ProviderType.WEBHOOK

            async def health_check(self, config):
                return ProviderHealthStatus(healthy=False, message="V2")

            async def search_candidates(self, config, criteria, limit=50):
                return []

            async def fetch_candidate_by_external_id(self, config, external_id):
                return None

        provider2 = AnotherMockAPI()
        ProviderRegistry.register(provider2)

        # Should still have only one provider with that name
        assert len(ProviderRegistry.list_all()) == 1
        result = ProviderRegistry.get("mock_api")
        assert result.provider_type == ProviderType.WEBHOOK

    def test_list_names(self):
        """Should return list of all registered provider names."""
        ProviderRegistry.register(MockAPIProvider())
        ProviderRegistry.register(MockFileProvider())

        names = ProviderRegistry.list_names()
        assert set(names) == {"mock_api", "mock_file"}
