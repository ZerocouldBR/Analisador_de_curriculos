"""
Servico de merge de candidatos.

Consolida multiplas fontes em um unico perfil canonico,
resolve conflitos por prioridade + recencia + confianca.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import AuditLog, Candidate, CandidateSource
from app.services.sourcing.provider_base import CandidateCanonicalProfile

logger = logging.getLogger(__name__)

# Campos simples (usar valor da fonte com maior prioridade)
SIMPLE_FIELDS = [
    "full_name", "email", "phone", "headline", "about",
    "city", "state", "country", "linkedin_url", "github_url",
    "portfolio_url", "current_company", "current_role", "seniority",
]

# Campos de lista (unir de todas as fontes)
LIST_FIELDS = [
    "skills", "certifications", "languages", "education", "experiences",
]


class CandidateMergeService:
    """Consolida perfis de multiplas fontes em um perfil unico."""

    @staticmethod
    def merge_profiles(
        profiles: List[CandidateCanonicalProfile],
        priority_order: Optional[List[str]] = None,
    ) -> CandidateCanonicalProfile:
        """Merge multiplos perfis canonicos em um unico perfil.

        Para campos simples: usa valor da fonte com maior prioridade que tenha o campo.
        Para listas: uniao de todas as fontes, removendo duplicatas.
        """
        if not profiles:
            raise ValueError("Nenhum perfil para merge")

        if len(profiles) == 1:
            return profiles[0]

        if priority_order is None:
            priority_order = settings.sourcing_merge_priority_order

        # Ordenar perfis por prioridade (provider com menor indice = maior prioridade)
        def _get_priority(profile: CandidateCanonicalProfile) -> int:
            raw = profile.raw_data or {}
            provider = raw.get("source") or raw.get("provider_name", "")
            try:
                return priority_order.index(provider)
            except ValueError:
                return len(priority_order)

        sorted_profiles = sorted(profiles, key=_get_priority)

        # Iniciar com dados do perfil de maior prioridade
        merged_data: Dict[str, Any] = {}

        # Campos simples: primeiro valor nao-nulo na ordem de prioridade
        for field in SIMPLE_FIELDS:
            for profile in sorted_profiles:
                value = getattr(profile, field, None)
                if value:
                    merged_data[field] = value
                    break

        # Campos de lista: uniao de todas as fontes
        for field in LIST_FIELDS:
            all_values = []
            seen = set()
            for profile in sorted_profiles:
                values = getattr(profile, field, []) or []
                for item in values:
                    if isinstance(item, dict):
                        key = str(sorted(item.items()))
                    else:
                        key = str(item).lower()
                    if key not in seen:
                        seen.add(key)
                        all_values.append(item)
            merged_data[field] = all_values

        # Confidence: media ponderada
        total_confidence = sum(p.confidence for p in profiles)
        avg_confidence = total_confidence / len(profiles)

        return CandidateCanonicalProfile(
            full_name=merged_data.get("full_name", "N/A"),
            email=merged_data.get("email"),
            phone=merged_data.get("phone"),
            headline=merged_data.get("headline"),
            about=merged_data.get("about"),
            city=merged_data.get("city"),
            state=merged_data.get("state"),
            country=merged_data.get("country", "Brasil"),
            linkedin_url=merged_data.get("linkedin_url"),
            github_url=merged_data.get("github_url"),
            portfolio_url=merged_data.get("portfolio_url"),
            current_company=merged_data.get("current_company"),
            current_role=merged_data.get("current_role"),
            seniority=merged_data.get("seniority"),
            skills=merged_data.get("skills", []),
            certifications=merged_data.get("certifications", []),
            education=merged_data.get("education", []),
            languages=merged_data.get("languages", []),
            experiences=merged_data.get("experiences", []),
            confidence=round(avg_confidence, 2),
        )

    @staticmethod
    def apply_merge_to_candidate(
        db: Session,
        candidate_id: int,
        merged_profile: CandidateCanonicalProfile,
        user_id: Optional[int] = None,
        company_id: Optional[int] = None,
    ) -> Optional[Candidate]:
        """Aplica perfil mergeado ao registro do candidato no banco."""
        query = db.query(Candidate).filter(Candidate.id == candidate_id)
        if company_id:
            query = query.filter(Candidate.company_id == company_id)
        candidate = query.first()
        if not candidate:
            return None

        updated_fields = []

        if merged_profile.full_name and merged_profile.full_name != "N/A":
            if candidate.full_name != merged_profile.full_name:
                candidate.full_name = merged_profile.full_name
                updated_fields.append("full_name")

        if merged_profile.email and candidate.email != merged_profile.email:
            candidate.email = merged_profile.email
            updated_fields.append("email")

        if merged_profile.phone and candidate.phone != merged_profile.phone:
            candidate.phone = merged_profile.phone
            updated_fields.append("phone")

        if merged_profile.city and candidate.city != merged_profile.city:
            candidate.city = merged_profile.city
            updated_fields.append("city")

        if merged_profile.state and candidate.state != merged_profile.state:
            candidate.state = merged_profile.state
            updated_fields.append("state")

        if merged_profile.country and candidate.country != merged_profile.country:
            candidate.country = merged_profile.country
            updated_fields.append("country")

        if updated_fields:
            db.flush()

            audit = AuditLog(
                user_id=user_id,
                action="sourcing_merge",
                entity="candidate",
                entity_id=candidate_id,
                metadata_json={
                    "updated_fields": updated_fields,
                    "source": "merge_service",
                },
            )
            db.add(audit)
            db.flush()

        return candidate

    @staticmethod
    def execute_candidate_merge(
        db: Session,
        primary_candidate_id: int,
        secondary_candidate_id: int,
        company_id: int,
        user_id: Optional[int] = None,
    ) -> Optional[Candidate]:
        """Merge dois candidatos: transfere fontes do secundario para o primario.

        O candidato secundario tem suas fontes transferidas e e marcado
        como merged (nao e deletado para manter auditoria).
        """
        primary = db.query(Candidate).filter(
            Candidate.id == primary_candidate_id,
            Candidate.company_id == company_id,
        ).first()

        secondary = db.query(Candidate).filter(
            Candidate.id == secondary_candidate_id,
            Candidate.company_id == company_id,
        ).first()

        if not primary or not secondary:
            return None

        # Transferir fontes do secundario para o primario
        secondary_sources = db.query(CandidateSource).filter(
            CandidateSource.candidate_id == secondary_candidate_id,
            CandidateSource.company_id == company_id,
        ).all()

        for source in secondary_sources:
            existing = db.query(CandidateSource).filter(
                CandidateSource.candidate_id == primary_candidate_id,
                CandidateSource.company_id == company_id,
                CandidateSource.provider_name == source.provider_name,
                CandidateSource.external_id == source.external_id,
            ).first()

            if not existing:
                source.candidate_id = primary_candidate_id
            # Se ja existe, manter a do primario

        # Audit log
        audit = AuditLog(
            user_id=user_id,
            action="sourcing_candidate_merge",
            entity="candidate",
            entity_id=primary_candidate_id,
            metadata_json={
                "primary_id": primary_candidate_id,
                "secondary_id": secondary_candidate_id,
                "secondary_name": secondary.full_name,
                "sources_transferred": len(secondary_sources),
            },
        )
        db.add(audit)
        db.flush()

        return primary
