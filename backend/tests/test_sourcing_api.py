"""
Integration tests for the sourcing API endpoints.

Uses the conftest.py fixtures: client, db, admin_user, admin_token.
"""
import pytest
from typing import Any, Dict, List, Optional

from app.db.models import (
    Candidate,
    CandidateSource,
    Company,
    ProviderConfig,
    SourcingSyncRun,
)
from app.services.sourcing.provider_base import (
    CandidateCanonicalProfile,
    ProviderHealthStatus,
    ProviderType,
    SourceProvider,
)
from app.services.sourcing.provider_registry import ProviderRegistry


# ================================================================
# Mock Provider for API tests
# ================================================================

class _TestableProvider(SourceProvider):
    """Provider used exclusively in API tests."""

    @property
    def provider_name(self) -> str:
        return "test_provider"

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.API

    async def health_check(self, config: Dict[str, Any]) -> ProviderHealthStatus:
        return ProviderHealthStatus(
            healthy=True,
            message="Test provider OK",
            remaining_quota=100,
        )

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
# Fixtures
# ================================================================

@pytest.fixture(autouse=True)
def register_test_provider():
    """Register and clean up the test provider for each test."""
    ProviderRegistry.register(_TestableProvider())
    yield
    # Only remove the test provider; do not clear everything
    if ProviderRegistry.is_registered("test_provider"):
        ProviderRegistry._providers.pop("test_provider", None)


@pytest.fixture
def test_company(db):
    """Create a test company and attach it to admin_user."""
    company = Company(
        name="Sourcing Test Corp",
        slug="sourcing-test-corp",
        plan="pro",
        is_active=True,
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@pytest.fixture
def admin_with_company(db, admin_user, test_company):
    """Attach admin_user to a company."""
    admin_user.company_id = test_company.id
    db.commit()
    db.refresh(admin_user)
    return admin_user


# ================================================================
# GET /api/v1/sourcing/providers
# ================================================================

class TestListProviders:
    def test_list_providers_authenticated(self, client, admin_token, admin_with_company):
        """Should list registered providers."""
        response = client.get(
            "/api/v1/sourcing/providers",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        # The test provider should be in the list
        names = [p["name"] for p in data]
        assert "test_provider" in names

    def test_list_providers_without_auth(self, client, db):
        """Should fail without authentication."""
        response = client.get("/api/v1/sourcing/providers")
        assert response.status_code == 403

    def test_list_providers_shows_config_status(
        self, client, db, admin_token, admin_with_company, test_company
    ):
        """Should show is_configured=True when config exists."""
        # Create a config for the test provider
        config = ProviderConfig(
            company_id=test_company.id,
            provider_name="test_provider",
            is_enabled=True,
        )
        db.add(config)
        db.commit()

        response = client.get(
            "/api/v1/sourcing/providers",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        test_prov = next(p for p in data if p["name"] == "test_provider")
        assert test_prov["is_configured"] is True
        assert test_prov["is_enabled"] is True


# ================================================================
# POST /api/v1/sourcing/providers/config
# ================================================================

class TestProviderConfig:
    def test_create_config(self, client, db, admin_token, admin_with_company):
        """Admin should be able to create provider config."""
        response = client.post(
            "/api/v1/sourcing/providers/config",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "provider_name": "test_provider",
                "is_enabled": True,
                "config_json": {"api_key": "test-key-123"},
                "schedule_cron": "0 3 * * *",
                "rate_limit_rpm": 30,
                "rate_limit_daily": 500,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["provider_name"] == "test_provider"
        assert data["is_enabled"] is True
        assert data["schedule_cron"] == "0 3 * * *"
        assert data["rate_limit_rpm"] == 30
        assert "api_key" in data["config_keys"]

    def test_create_config_unregistered_provider(
        self, client, admin_token, admin_with_company
    ):
        """Should reject config for unregistered provider."""
        response = client.post(
            "/api/v1/sourcing/providers/config",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "provider_name": "nonexistent_provider",
                "is_enabled": True,
                "config_json": {},
            },
        )

        assert response.status_code == 400
        assert "nao registrado" in response.json()["detail"]

    def test_create_config_without_auth(self, client, db):
        """Should fail without authentication."""
        response = client.post(
            "/api/v1/sourcing/providers/config",
            json={
                "provider_name": "test_provider",
                "is_enabled": True,
                "config_json": {},
            },
        )

        assert response.status_code == 403

    def test_update_config_upsert(self, client, db, admin_token, admin_with_company):
        """Should update existing config on second call (upsert)."""
        payload = {
            "provider_name": "test_provider",
            "is_enabled": False,
            "config_json": {"key": "v1"},
        }
        resp1 = client.post(
            "/api/v1/sourcing/providers/config",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=payload,
        )
        assert resp1.status_code == 200

        # Update
        payload["is_enabled"] = True
        payload["config_json"] = {"key": "v2"}
        resp2 = client.post(
            "/api/v1/sourcing/providers/config",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=payload,
        )
        assert resp2.status_code == 200
        assert resp2.json()["is_enabled"] is True
        assert resp2.json()["id"] == resp1.json()["id"]


# ================================================================
# POST /api/v1/sourcing/providers/{name}/test
# ================================================================

class TestProviderTest:
    def test_test_connection(self, client, admin_token, admin_with_company):
        """Should test provider connection and return health status."""
        response = client.post(
            "/api/v1/sourcing/providers/test_provider/test",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["healthy"] is True
        assert data["message"] == "Test provider OK"
        assert data["remaining_quota"] == 100

    def test_test_nonexistent_provider(self, client, admin_token, admin_with_company):
        """Should 404 for unknown provider."""
        response = client.post(
            "/api/v1/sourcing/providers/unknown_provider/test",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 404

    def test_test_connection_without_auth(self, client, db):
        """Should fail without authentication."""
        response = client.post(
            "/api/v1/sourcing/providers/test_provider/test"
        )
        assert response.status_code == 403


# ================================================================
# GET /api/v1/sourcing/runs
# ================================================================

class TestListSyncRuns:
    def test_list_runs_empty(self, client, admin_token, admin_with_company):
        """Should return empty list when no runs exist."""
        response = client.get(
            "/api/v1/sourcing/runs",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 200
        assert response.json() == []

    def test_list_runs_with_data(
        self, client, db, admin_token, admin_with_company, test_company
    ):
        """Should list sync runs for the company."""
        run = SourcingSyncRun(
            company_id=test_company.id,
            provider_name="test_provider",
            run_type="manual",
            status="completed",
            total_scanned=10,
            total_created=5,
        )
        db.add(run)
        db.commit()

        response = client.get(
            "/api/v1/sourcing/runs",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["provider_name"] == "test_provider"
        assert data[0]["status"] == "completed"
        assert data[0]["total_scanned"] == 10

    def test_list_runs_filter_by_provider(
        self, client, db, admin_token, admin_with_company, test_company
    ):
        """Should filter runs by provider_name."""
        run1 = SourcingSyncRun(
            company_id=test_company.id,
            provider_name="test_provider",
            run_type="manual",
            status="completed",
        )
        run2 = SourcingSyncRun(
            company_id=test_company.id,
            provider_name="other_provider",
            run_type="scheduled",
            status="completed",
        )
        db.add_all([run1, run2])
        db.commit()

        response = client.get(
            "/api/v1/sourcing/runs?provider_name=test_provider",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert all(r["provider_name"] == "test_provider" for r in data)

    def test_list_runs_without_auth(self, client, db):
        """Should fail without authentication."""
        response = client.get("/api/v1/sourcing/runs")
        assert response.status_code == 403


# ================================================================
# GET /api/v1/sourcing/candidates/{id}/sources
# ================================================================

class TestCandidateSources:
    def test_get_sources_for_candidate(
        self, client, db, admin_token, admin_with_company, test_company
    ):
        """Should return sources for a candidate."""
        candidate = Candidate(
            company_id=test_company.id,
            full_name="Source Test Candidate",
            email="source.test@example.com",
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        source = CandidateSource(
            company_id=test_company.id,
            candidate_id=candidate.id,
            provider_name="test_provider",
            provider_type="api",
            external_id="ext-001",
            external_url="https://example.com/ext-001",
            source_confidence=0.85,
        )
        db.add(source)
        db.commit()

        response = client.get(
            f"/api/v1/sourcing/candidates/{candidate.id}/sources",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["provider_name"] == "test_provider"
        assert data[0]["external_id"] == "ext-001"
        assert data[0]["source_confidence"] == 0.85

    def test_get_sources_empty(
        self, client, db, admin_token, admin_with_company, test_company
    ):
        """Should return empty list for candidate with no sources."""
        candidate = Candidate(
            company_id=test_company.id,
            full_name="No Source Candidate",
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        response = client.get(
            f"/api/v1/sourcing/candidates/{candidate.id}/sources",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 200
        assert response.json() == []

    def test_get_sources_without_auth(self, client, db):
        """Should fail without authentication."""
        response = client.get("/api/v1/sourcing/candidates/1/sources")
        assert response.status_code == 403

    def test_get_sources_multiple(
        self, client, db, admin_token, admin_with_company, test_company
    ):
        """Should return all sources for a multi-source candidate."""
        candidate = Candidate(
            company_id=test_company.id,
            full_name="Multi Source Candidate",
            email="multi@example.com",
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        for pname, ptype in [("linkedin", "api"), ("csv_import", "file"), ("manual", "manual")]:
            db.add(CandidateSource(
                company_id=test_company.id,
                candidate_id=candidate.id,
                provider_name=pname,
                provider_type=ptype,
            ))
        db.commit()

        response = client.get(
            f"/api/v1/sourcing/candidates/{candidate.id}/sources",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        names = {s["provider_name"] for s in data}
        assert names == {"linkedin", "csv_import", "manual"}


# ================================================================
# GET /api/v1/sourcing/merge-suggestions
# ================================================================

class TestMergeSuggestions:
    def test_merge_suggestions_empty(
        self, client, admin_token, admin_with_company
    ):
        """Should return empty list when no candidates exist."""
        response = client.get(
            "/api/v1/sourcing/merge-suggestions",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 200
        assert response.json() == []

    def test_merge_suggestions_with_duplicates(
        self, client, db, admin_token, admin_with_company, test_company
    ):
        """Should detect potential duplicates with same email."""
        cand1 = Candidate(
            company_id=test_company.id,
            full_name="Maria Silva",
            email="maria@example.com",
            phone="(11) 99999-0000",
        )
        cand2 = Candidate(
            company_id=test_company.id,
            full_name="Maria Silva Santos",
            email="maria@example.com",
            phone="(11) 99999-0000",
        )
        db.add_all([cand1, cand2])
        db.commit()

        response = client.get(
            "/api/v1/sourcing/merge-suggestions",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        # With same email + similar name, dedup should find a suggestion
        assert len(data) >= 1
        suggestion = data[0]
        assert "candidate_id_a" in suggestion
        assert "candidate_id_b" in suggestion
        assert "similarity_score" in suggestion
        assert suggestion["similarity_score"] > 0

    def test_merge_suggestions_without_auth(self, client, db):
        """Should fail without authentication."""
        response = client.get("/api/v1/sourcing/merge-suggestions")
        assert response.status_code == 403
