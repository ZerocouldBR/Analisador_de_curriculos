"""
Tests for the hybrid sourcing models: CandidateSource, CandidateSnapshot,
CandidateChangeLog, SourcingSyncRun, ProviderConfig.
"""
import pytest
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    Candidate,
    CandidateChangeLog,
    CandidateSnapshot,
    CandidateSource,
    Company,
    ProviderConfig,
    SourcingSyncRun,
)


# ================================================================
# Helpers
# ================================================================

def _make_company(db, slug="test-co"):
    """Create a test company."""
    company = Company(
        name="Test Company",
        slug=slug,
        plan="pro",
        is_active=True,
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def _make_candidate(db, company_id, name="Maria Silva"):
    """Create a test candidate."""
    candidate = Candidate(
        company_id=company_id,
        full_name=name,
        email=f"{name.lower().replace(' ', '.')}@example.com",
        phone="(11) 99999-0000",
        city="Sao Paulo",
        state="SP",
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


# ================================================================
# CandidateSource
# ================================================================

class TestCandidateSource:
    def test_create_source(self, db):
        """Should create a CandidateSource record."""
        company = _make_company(db)
        candidate = _make_candidate(db, company.id)

        source = CandidateSource(
            company_id=company.id,
            candidate_id=candidate.id,
            provider_name="linkedin",
            provider_type="api",
            external_id="ext-123",
            external_url="https://linkedin.com/in/maria-silva",
            source_confidence=0.9,
            source_priority=80,
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        assert source.id is not None
        assert source.provider_name == "linkedin"
        assert source.provider_type == "api"
        assert source.external_id == "ext-123"
        assert source.source_confidence == 0.9
        assert source.source_priority == 80
        assert source.sync_enabled is True
        assert source.consent_status == "pending"

    def test_read_source(self, db):
        """Should read back a CandidateSource by id."""
        company = _make_company(db)
        candidate = _make_candidate(db, company.id)

        source = CandidateSource(
            company_id=company.id,
            candidate_id=candidate.id,
            provider_name="csv_import",
            provider_type="file",
        )
        db.add(source)
        db.commit()

        fetched = db.query(CandidateSource).filter(
            CandidateSource.id == source.id
        ).first()
        assert fetched is not None
        assert fetched.provider_name == "csv_import"

    def test_update_source(self, db):
        """Should update CandidateSource fields."""
        company = _make_company(db)
        candidate = _make_candidate(db, company.id)

        source = CandidateSource(
            company_id=company.id,
            candidate_id=candidate.id,
            provider_name="manual",
            provider_type="manual",
            source_confidence=0.5,
        )
        db.add(source)
        db.commit()

        source.source_confidence = 0.95
        source.last_status = "success"
        source.last_sync_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(source)

        assert source.source_confidence == 0.95
        assert source.last_status == "success"
        assert source.last_sync_at is not None

    def test_delete_source(self, db):
        """Should delete a CandidateSource."""
        company = _make_company(db)
        candidate = _make_candidate(db, company.id)

        source = CandidateSource(
            company_id=company.id,
            candidate_id=candidate.id,
            provider_name="webhook",
            provider_type="webhook",
        )
        db.add(source)
        db.commit()
        source_id = source.id

        db.delete(source)
        db.commit()

        deleted = db.query(CandidateSource).filter(
            CandidateSource.id == source_id
        ).first()
        assert deleted is None

    def test_unique_constraint_external_id(self, db):
        """Unique index on (company_id, provider_name, external_id) should prevent duplicates."""
        company = _make_company(db)
        candidate = _make_candidate(db, company.id)

        source1 = CandidateSource(
            company_id=company.id,
            candidate_id=candidate.id,
            provider_name="linkedin",
            provider_type="api",
            external_id="dup-ext-1",
        )
        db.add(source1)
        db.commit()

        source2 = CandidateSource(
            company_id=company.id,
            candidate_id=candidate.id,
            provider_name="linkedin",
            provider_type="api",
            external_id="dup-ext-1",
        )
        db.add(source2)

        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_relationship_to_candidate(self, db):
        """Source should navigate back to candidate via relationship."""
        company = _make_company(db)
        candidate = _make_candidate(db, company.id)

        source = CandidateSource(
            company_id=company.id,
            candidate_id=candidate.id,
            provider_name="csv_import",
            provider_type="file",
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        assert source.candidate.id == candidate.id
        assert source.candidate.full_name == candidate.full_name


# ================================================================
# CandidateSnapshot
# ================================================================

class TestCandidateSnapshot:
    def test_create_snapshot(self, db):
        """Should create a CandidateSnapshot with hash and JSON."""
        company = _make_company(db)
        candidate = _make_candidate(db, company.id)
        source = CandidateSource(
            company_id=company.id,
            candidate_id=candidate.id,
            provider_name="linkedin",
            provider_type="api",
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        snapshot = CandidateSnapshot(
            company_id=company.id,
            candidate_id=candidate.id,
            source_id=source.id,
            snapshot_hash="abc123def456",
            canonical_json={"full_name": "Maria Silva", "email": "maria@example.com"},
            extracted_text="Maria Silva - Engenheira",
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)

        assert snapshot.id is not None
        assert snapshot.snapshot_hash == "abc123def456"
        assert snapshot.canonical_json["full_name"] == "Maria Silva"
        assert snapshot.extracted_text == "Maria Silva - Engenheira"

    def test_relationship_to_source(self, db):
        """Snapshot should navigate back to its source."""
        company = _make_company(db)
        candidate = _make_candidate(db, company.id)
        source = CandidateSource(
            company_id=company.id,
            candidate_id=candidate.id,
            provider_name="csv_import",
            provider_type="file",
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        snapshot = CandidateSnapshot(
            company_id=company.id,
            candidate_id=candidate.id,
            source_id=source.id,
            snapshot_hash="hash-rel",
            canonical_json={"full_name": "Test"},
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)

        assert snapshot.source is not None
        assert snapshot.source.provider_name == "csv_import"

    def test_snapshot_without_source(self, db):
        """Snapshot with source_id=None should still work (manual import)."""
        company = _make_company(db)
        candidate = _make_candidate(db, company.id)

        snapshot = CandidateSnapshot(
            company_id=company.id,
            candidate_id=candidate.id,
            source_id=None,
            snapshot_hash="hash-no-src",
            canonical_json={"full_name": "No Source"},
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)

        assert snapshot.id is not None
        assert snapshot.source is None

    def test_source_snapshots_relationship(self, db):
        """CandidateSource.snapshots should list related snapshots."""
        company = _make_company(db)
        candidate = _make_candidate(db, company.id)
        source = CandidateSource(
            company_id=company.id,
            candidate_id=candidate.id,
            provider_name="manual",
            provider_type="manual",
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        for i in range(3):
            snap = CandidateSnapshot(
                company_id=company.id,
                candidate_id=candidate.id,
                source_id=source.id,
                snapshot_hash=f"hash-{i}",
                canonical_json={"version": i},
            )
            db.add(snap)
        db.commit()
        db.refresh(source)

        assert len(source.snapshots) == 3


# ================================================================
# CandidateChangeLog
# ================================================================

class TestCandidateChangeLog:
    def test_create_changelog(self, db):
        """Should create a CandidateChangeLog referencing from/to snapshots."""
        company = _make_company(db)
        candidate = _make_candidate(db, company.id)

        snap_from = CandidateSnapshot(
            company_id=company.id,
            candidate_id=candidate.id,
            snapshot_hash="hash-from",
            canonical_json={"email": "old@example.com"},
        )
        snap_to = CandidateSnapshot(
            company_id=company.id,
            candidate_id=candidate.id,
            snapshot_hash="hash-to",
            canonical_json={"email": "new@example.com"},
        )
        db.add_all([snap_from, snap_to])
        db.commit()
        db.refresh(snap_from)
        db.refresh(snap_to)

        changelog = CandidateChangeLog(
            company_id=company.id,
            candidate_id=candidate.id,
            snapshot_from_id=snap_from.id,
            snapshot_to_id=snap_to.id,
            changed_fields_json={"email": {"from": "old@example.com", "to": "new@example.com"}},
            diff_summary="Email atualizado",
        )
        db.add(changelog)
        db.commit()
        db.refresh(changelog)

        assert changelog.id is not None
        assert changelog.snapshot_from_id == snap_from.id
        assert changelog.snapshot_to_id == snap_to.id
        assert changelog.changed_fields_json["email"]["to"] == "new@example.com"
        assert changelog.diff_summary == "Email atualizado"

    def test_changelog_with_null_from_snapshot(self, db):
        """First snapshot has no 'from' - snapshot_from_id can be null."""
        company = _make_company(db)
        candidate = _make_candidate(db, company.id)

        snap_to = CandidateSnapshot(
            company_id=company.id,
            candidate_id=candidate.id,
            snapshot_hash="hash-initial",
            canonical_json={"full_name": "New Candidate"},
        )
        db.add(snap_to)
        db.commit()
        db.refresh(snap_to)

        changelog = CandidateChangeLog(
            company_id=company.id,
            candidate_id=candidate.id,
            snapshot_from_id=None,
            snapshot_to_id=snap_to.id,
            changed_fields_json={"full_name": {"from": None, "to": "New Candidate"}},
        )
        db.add(changelog)
        db.commit()
        db.refresh(changelog)

        assert changelog.snapshot_from_id is None
        assert changelog.snapshot_to_id == snap_to.id

    def test_changelog_relationships(self, db):
        """Should navigate to snapshot_from and snapshot_to."""
        company = _make_company(db)
        candidate = _make_candidate(db, company.id)

        snap_a = CandidateSnapshot(
            company_id=company.id,
            candidate_id=candidate.id,
            snapshot_hash="snap-a",
            canonical_json={"v": 1},
        )
        snap_b = CandidateSnapshot(
            company_id=company.id,
            candidate_id=candidate.id,
            snapshot_hash="snap-b",
            canonical_json={"v": 2},
        )
        db.add_all([snap_a, snap_b])
        db.commit()
        db.refresh(snap_a)
        db.refresh(snap_b)

        changelog = CandidateChangeLog(
            company_id=company.id,
            candidate_id=candidate.id,
            snapshot_from_id=snap_a.id,
            snapshot_to_id=snap_b.id,
            changed_fields_json={"v": {"from": 1, "to": 2}},
        )
        db.add(changelog)
        db.commit()
        db.refresh(changelog)

        assert changelog.snapshot_from.snapshot_hash == "snap-a"
        assert changelog.snapshot_to.snapshot_hash == "snap-b"


# ================================================================
# SourcingSyncRun
# ================================================================

class TestSourcingSyncRun:
    def test_create_sync_run(self, db):
        """Should create a SourcingSyncRun with default values."""
        company = _make_company(db)

        run = SourcingSyncRun(
            company_id=company.id,
            provider_name="linkedin",
            run_type="manual",
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        assert run.id is not None
        assert run.status == "pending"
        assert run.total_scanned == 0
        assert run.total_created == 0
        assert run.total_updated == 0
        assert run.total_unchanged == 0
        assert run.total_failed == 0
        assert run.started_at is not None
        assert run.finished_at is None

    def test_status_transitions(self, db):
        """Should allow transitioning status from pending -> running -> completed."""
        company = _make_company(db)

        run = SourcingSyncRun(
            company_id=company.id,
            provider_name="csv_import",
            run_type="scheduled",
            status="pending",
        )
        db.add(run)
        db.commit()
        assert run.status == "pending"

        run.status = "running"
        db.commit()
        db.refresh(run)
        assert run.status == "running"

        run.status = "completed"
        run.finished_at = datetime.now(timezone.utc)
        run.total_scanned = 100
        run.total_created = 50
        run.total_updated = 30
        run.total_unchanged = 15
        run.total_failed = 5
        db.commit()
        db.refresh(run)

        assert run.status == "completed"
        assert run.finished_at is not None
        assert run.total_scanned == 100
        assert run.total_created == 50
        assert run.total_updated == 30
        assert run.total_unchanged == 15
        assert run.total_failed == 5

    def test_status_transition_to_failed(self, db):
        """Should allow transitioning to failed with error detail."""
        company = _make_company(db)

        run = SourcingSyncRun(
            company_id=company.id,
            provider_name="webhook",
            run_type="webhook",
            status="running",
        )
        db.add(run)
        db.commit()

        run.status = "failed"
        run.error_detail = "Connection timeout"
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)

        assert run.status == "failed"
        assert run.error_detail == "Connection timeout"

    def test_sync_run_with_metadata(self, db):
        """Should store metadata_json."""
        company = _make_company(db)

        run = SourcingSyncRun(
            company_id=company.id,
            provider_name="linkedin",
            run_type="manual",
            metadata_json={"search_criteria": {"skills": ["python"]}, "page": 1},
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        assert run.metadata_json["search_criteria"]["skills"] == ["python"]
        assert run.metadata_json["page"] == 1


# ================================================================
# ProviderConfig
# ================================================================

class TestProviderConfig:
    def test_create_provider_config(self, db):
        """Should create a ProviderConfig with defaults."""
        company = _make_company(db)

        config = ProviderConfig(
            company_id=company.id,
            provider_name="linkedin",
            is_enabled=True,
            config_json_encrypted='{"api_key": "secret"}',
            schedule_cron="0 3 * * *",
            rate_limit_rpm=30,
            rate_limit_daily=500,
        )
        db.add(config)
        db.commit()
        db.refresh(config)

        assert config.id is not None
        assert config.provider_name == "linkedin"
        assert config.is_enabled is True
        assert config.schedule_cron == "0 3 * * *"
        assert config.rate_limit_rpm == 30
        assert config.rate_limit_daily == 500

    def test_unique_constraint_company_provider(self, db):
        """Unique index on (company_id, provider_name) should prevent duplicates."""
        company = _make_company(db)

        config1 = ProviderConfig(
            company_id=company.id,
            provider_name="linkedin",
            is_enabled=False,
        )
        db.add(config1)
        db.commit()

        config2 = ProviderConfig(
            company_id=company.id,
            provider_name="linkedin",
            is_enabled=True,
        )
        db.add(config2)

        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_different_companies_same_provider(self, db):
        """Different companies should be able to use the same provider name."""
        company1 = _make_company(db, slug="co-alpha")
        company2 = _make_company(db, slug="co-beta")

        config1 = ProviderConfig(
            company_id=company1.id,
            provider_name="linkedin",
            is_enabled=True,
        )
        config2 = ProviderConfig(
            company_id=company2.id,
            provider_name="linkedin",
            is_enabled=False,
        )
        db.add_all([config1, config2])
        db.commit()

        assert config1.id is not None
        assert config2.id is not None
        assert config1.id != config2.id

    def test_company_sourcing_configs_relationship(self, db):
        """Company.sourcing_configs should list its provider configs."""
        company = _make_company(db)

        for name in ["linkedin", "csv_import", "manual"]:
            db.add(ProviderConfig(
                company_id=company.id,
                provider_name=name,
            ))
        db.commit()
        db.refresh(company)

        assert len(company.sourcing_configs) == 3
        names = {c.provider_name for c in company.sourcing_configs}
        assert names == {"linkedin", "csv_import", "manual"}

    def test_default_values(self, db):
        """Should have sensible defaults for schedule, rate limits, etc."""
        company = _make_company(db)

        config = ProviderConfig(
            company_id=company.id,
            provider_name="webhook",
        )
        db.add(config)
        db.commit()
        db.refresh(config)

        assert config.is_enabled is False
        assert config.schedule_cron == "0 2 */5 * *"
        assert config.rate_limit_rpm == 60
        assert config.rate_limit_daily == 1000
