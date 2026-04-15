"""
Servico de deduplicacao de candidatos.

Identifica candidatos duplicados entre multiplas fontes usando
scoring ponderado por email, telefone, nome e LinkedIn URL.
"""
import logging
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Candidate, CandidateSource
from app.services.sourcing.provider_base import CandidateCanonicalProfile

logger = logging.getLogger(__name__)


class DeduplicationService:
    """Detecta e sugere merge de candidatos duplicados."""

    @staticmethod
    def find_duplicates(
        db: Session,
        profile: CandidateCanonicalProfile,
        company_id: int,
        threshold: Optional[float] = None,
        exclude_candidate_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Busca candidatos existentes que podem ser duplicata do perfil.

        Retorna lista de {candidate_id, score, matched_fields} ordenada por score.
        """
        if threshold is None:
            threshold = settings.sourcing_dedup_threshold

        candidates = (
            db.query(Candidate)
            .filter(Candidate.company_id == company_id)
            .all()
        )

        results = []
        for candidate in candidates:
            if exclude_candidate_id and candidate.id == exclude_candidate_id:
                continue

            score, matched_fields = DeduplicationService._compute_similarity(
                profile, candidate
            )

            if score >= threshold:
                results.append({
                    "candidate_id": candidate.id,
                    "candidate_name": candidate.full_name,
                    "score": round(score, 3),
                    "matched_fields": matched_fields,
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    @staticmethod
    def suggest_merges(
        db: Session, company_id: int, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Sugere pares de candidatos que podem ser duplicatas.

        Varre candidatos com multiplas fontes e compara com outros.
        """
        candidates = (
            db.query(Candidate)
            .filter(Candidate.company_id == company_id)
            .all()
        )

        if len(candidates) < 2:
            return []

        suggestions = []
        seen_pairs = set()

        for i, cand_a in enumerate(candidates):
            for cand_b in candidates[i + 1:]:
                pair_key = (min(cand_a.id, cand_b.id), max(cand_a.id, cand_b.id))
                if pair_key in seen_pairs:
                    continue

                score, matched_fields = DeduplicationService._compare_candidates(
                    cand_a, cand_b
                )

                if score >= settings.sourcing_dedup_threshold:
                    seen_pairs.add(pair_key)
                    suggestions.append({
                        "candidate_id_a": cand_a.id,
                        "candidate_id_b": cand_b.id,
                        "name_a": cand_a.full_name,
                        "name_b": cand_b.full_name,
                        "similarity_score": round(score, 3),
                        "matched_fields": matched_fields,
                    })

                if len(suggestions) >= limit:
                    break
            if len(suggestions) >= limit:
                break

        suggestions.sort(key=lambda x: x["similarity_score"], reverse=True)
        return suggestions[:limit]

    @staticmethod
    def _compute_similarity(
        profile: CandidateCanonicalProfile, candidate: Candidate
    ) -> tuple:
        """Calcula score de similaridade entre um perfil canonico e um candidato."""
        score = 0.0
        matched_fields = []

        # Email (peso mais alto)
        if profile.email and candidate.email:
            if profile.email.strip().lower() == candidate.email.strip().lower():
                score += settings.sourcing_dedup_email_weight
                matched_fields.append("email")

        # Telefone
        if profile.phone and candidate.phone:
            norm_profile = DeduplicationService._normalize_phone(profile.phone)
            norm_candidate = DeduplicationService._normalize_phone(candidate.phone)
            if norm_profile and norm_candidate and norm_profile == norm_candidate:
                score += settings.sourcing_dedup_phone_weight
                matched_fields.append("phone")

        # Nome (fuzzy match)
        if profile.full_name and candidate.full_name:
            name_score = DeduplicationService._fuzzy_name_score(
                profile.full_name, candidate.full_name
            )
            if name_score >= settings.sourcing_dedup_name_fuzzy_threshold:
                score += settings.sourcing_dedup_name_weight * name_score
                matched_fields.append(f"name ({name_score:.0%})")

        # LinkedIn URL
        if profile.linkedin_url:
            sources = []
            if hasattr(candidate, "sources"):
                sources = candidate.sources or []
            candidate_linkedin = None
            for source in sources:
                if source.external_url and "linkedin.com" in source.external_url:
                    candidate_linkedin = source.external_url
                    break

            if candidate_linkedin and DeduplicationService._compare_linkedin_urls(
                profile.linkedin_url, candidate_linkedin
            ):
                score += settings.sourcing_dedup_linkedin_weight
                matched_fields.append("linkedin_url")

        return score, matched_fields

    @staticmethod
    def _compare_candidates(
        cand_a: Candidate, cand_b: Candidate
    ) -> tuple:
        """Compara dois candidatos existentes."""
        score = 0.0
        matched_fields = []

        if cand_a.email and cand_b.email:
            if cand_a.email.strip().lower() == cand_b.email.strip().lower():
                score += settings.sourcing_dedup_email_weight
                matched_fields.append("email")

        if cand_a.phone and cand_b.phone:
            norm_a = DeduplicationService._normalize_phone(cand_a.phone)
            norm_b = DeduplicationService._normalize_phone(cand_b.phone)
            if norm_a and norm_b and norm_a == norm_b:
                score += settings.sourcing_dedup_phone_weight
                matched_fields.append("phone")

        if cand_a.full_name and cand_b.full_name:
            name_score = DeduplicationService._fuzzy_name_score(
                cand_a.full_name, cand_b.full_name
            )
            if name_score >= settings.sourcing_dedup_name_fuzzy_threshold:
                score += settings.sourcing_dedup_name_weight * name_score
                matched_fields.append(f"name ({name_score:.0%})")

        return score, matched_fields

    @staticmethod
    def _normalize_phone(phone: str) -> Optional[str]:
        """Normaliza telefone para apenas digitos para comparacao."""
        if not phone:
            return None
        digits = re.sub(r"[^\d]", "", phone)
        if len(digits) >= 13 and digits[:2] == "55":
            digits = digits[2:]
        if len(digits) < 8:
            return None
        return digits

    @staticmethod
    def _fuzzy_name_score(name1: str, name2: str) -> float:
        """Calcula similaridade entre dois nomes usando SequenceMatcher."""
        n1 = name1.strip().lower()
        n2 = name2.strip().lower()
        if n1 == n2:
            return 1.0
        return SequenceMatcher(None, n1, n2).ratio()

    @staticmethod
    def _compare_linkedin_urls(url1: str, url2: str) -> bool:
        """Compara duas URLs do LinkedIn normalizando path."""
        def _extract_slug(url: str) -> str:
            url = url.rstrip("/").lower()
            parts = url.split("/in/")
            if len(parts) >= 2:
                return parts[1].split("/")[0].split("?")[0]
            return url

        return _extract_slug(url1) == _extract_slug(url2)
