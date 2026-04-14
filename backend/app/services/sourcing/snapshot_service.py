"""
Servico de snapshots de candidatos.

Gerencia snapshots versionados do perfil canonico,
calcula hashes para deteccao de mudancas e persiste diffs.
"""
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db.models import CandidateChangeLog, CandidateSnapshot
from app.services.sourcing.candidate_normalizer import CandidateNormalizer
from app.services.sourcing.provider_base import CandidateCanonicalProfile

logger = logging.getLogger(__name__)


class SnapshotService:
    """Gerencia snapshots e change logs de candidatos."""

    @staticmethod
    def create_snapshot(
        db: Session,
        candidate_id: int,
        company_id: int,
        source_id: Optional[int],
        canonical: CandidateCanonicalProfile,
    ) -> CandidateSnapshot:
        """Cria um novo snapshot do candidato.

        Se o hash for igual ao ultimo snapshot, retorna o existente sem criar novo.
        Se diferente, cria snapshot e registra as diferencas no change log.
        """
        canonical_json = CandidateNormalizer.to_canonical_json(canonical)
        snapshot_hash = CandidateNormalizer.compute_hash(canonical)
        extracted_text = CandidateNormalizer.extract_text(canonical)

        latest = SnapshotService.get_latest_snapshot(db, candidate_id, company_id)

        if latest and latest.snapshot_hash == snapshot_hash:
            logger.debug(
                f"Snapshot inalterado para candidate_id={candidate_id}"
            )
            return latest

        snapshot = CandidateSnapshot(
            company_id=company_id,
            candidate_id=candidate_id,
            source_id=source_id,
            snapshot_hash=snapshot_hash,
            canonical_json=canonical_json,
            extracted_text=extracted_text,
        )
        db.add(snapshot)
        db.flush()

        if latest:
            diff = SnapshotService.compute_diff(latest, snapshot)
            if diff["changed_fields"]:
                SnapshotService.record_change(
                    db=db,
                    company_id=company_id,
                    candidate_id=candidate_id,
                    from_id=latest.id,
                    to_id=snapshot.id,
                    changed_fields=diff["changed_fields"],
                    summary=diff["diff_summary"],
                )
        else:
            SnapshotService.record_change(
                db=db,
                company_id=company_id,
                candidate_id=candidate_id,
                from_id=None,
                to_id=snapshot.id,
                changed_fields=canonical_json,
                summary="Snapshot inicial",
            )

        return snapshot

    @staticmethod
    def get_latest_snapshot(
        db: Session, candidate_id: int, company_id: int
    ) -> Optional[CandidateSnapshot]:
        """Retorna o snapshot mais recente do candidato."""
        return (
            db.query(CandidateSnapshot)
            .filter(
                CandidateSnapshot.candidate_id == candidate_id,
                CandidateSnapshot.company_id == company_id,
            )
            .order_by(desc(CandidateSnapshot.created_at))
            .first()
        )

    @staticmethod
    def list_snapshots(
        db: Session, candidate_id: int, company_id: int, limit: int = 50
    ) -> List[CandidateSnapshot]:
        """Lista snapshots de um candidato ordenados por data."""
        return (
            db.query(CandidateSnapshot)
            .filter(
                CandidateSnapshot.candidate_id == candidate_id,
                CandidateSnapshot.company_id == company_id,
            )
            .order_by(desc(CandidateSnapshot.created_at))
            .limit(limit)
            .all()
        )

    @staticmethod
    def compute_diff(
        old_snapshot: CandidateSnapshot, new_snapshot: CandidateSnapshot
    ) -> Dict[str, Any]:
        """Compara dois snapshots e retorna as diferencas."""
        old_data = old_snapshot.canonical_json or {}
        new_data = new_snapshot.canonical_json or {}

        changed_fields = {}
        all_keys = set(list(old_data.keys()) + list(new_data.keys()))

        for key in all_keys:
            old_val = old_data.get(key)
            new_val = new_data.get(key)
            if old_val != new_val:
                changed_fields[key] = {
                    "from": old_val,
                    "to": new_val,
                }

        summary_parts = []
        for field_name in changed_fields:
            if changed_fields[field_name]["from"] is None:
                summary_parts.append(f"+ {field_name}")
            elif changed_fields[field_name]["to"] is None:
                summary_parts.append(f"- {field_name}")
            else:
                summary_parts.append(f"~ {field_name}")

        diff_summary = "; ".join(summary_parts) if summary_parts else "Sem alteracoes"

        return {
            "changed_fields": changed_fields,
            "diff_summary": diff_summary,
        }

    @staticmethod
    def get_diff_between(
        db: Session,
        candidate_id: int,
        company_id: int,
        from_snapshot_id: int,
        to_snapshot_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Retorna diff entre dois snapshots especificos."""
        from_snap = (
            db.query(CandidateSnapshot)
            .filter(
                CandidateSnapshot.id == from_snapshot_id,
                CandidateSnapshot.candidate_id == candidate_id,
                CandidateSnapshot.company_id == company_id,
            )
            .first()
        )
        to_snap = (
            db.query(CandidateSnapshot)
            .filter(
                CandidateSnapshot.id == to_snapshot_id,
                CandidateSnapshot.candidate_id == candidate_id,
                CandidateSnapshot.company_id == company_id,
            )
            .first()
        )

        if not from_snap or not to_snap:
            return None

        return SnapshotService.compute_diff(from_snap, to_snap)

    @staticmethod
    def record_change(
        db: Session,
        company_id: int,
        candidate_id: int,
        from_id: Optional[int],
        to_id: int,
        changed_fields: Dict,
        summary: str,
    ) -> CandidateChangeLog:
        """Registra uma mudanca no change log."""
        change_log = CandidateChangeLog(
            company_id=company_id,
            candidate_id=candidate_id,
            snapshot_from_id=from_id,
            snapshot_to_id=to_id,
            changed_fields_json=changed_fields,
            diff_summary=summary,
        )
        db.add(change_log)
        db.flush()
        return change_log

    @staticmethod
    def get_change_logs(
        db: Session, candidate_id: int, company_id: int, limit: int = 50
    ) -> List[CandidateChangeLog]:
        """Lista change logs de um candidato."""
        return (
            db.query(CandidateChangeLog)
            .filter(
                CandidateChangeLog.candidate_id == candidate_id,
                CandidateChangeLog.company_id == company_id,
            )
            .order_by(desc(CandidateChangeLog.created_at))
            .limit(limit)
            .all()
        )
