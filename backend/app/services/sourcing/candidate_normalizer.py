"""
Servico de normalizacao de candidatos.

Converte payloads de qualquer provider para o modelo canonico,
normaliza campos, computa hashes para deteccao de mudancas
e gera texto searchavel para embeddings.
"""
import hashlib
import json
import logging
import re
from dataclasses import asdict
from typing import Any, Dict, Optional

from app.services.sourcing.provider_base import CandidateCanonicalProfile

logger = logging.getLogger(__name__)

# Mapeamento de estados brasileiros
STATE_ABBREVIATIONS = {
    "acre": "AC", "alagoas": "AL", "amapa": "AP", "amapá": "AP",
    "amazonas": "AM", "bahia": "BA", "ceara": "CE", "ceará": "CE",
    "distrito federal": "DF", "espirito santo": "ES", "espírito santo": "ES",
    "goias": "GO", "goiás": "GO", "maranhao": "MA", "maranhão": "MA",
    "mato grosso": "MT", "mato grosso do sul": "MS", "minas gerais": "MG",
    "para": "PA", "pará": "PA", "paraiba": "PB", "paraíba": "PB",
    "parana": "PR", "paraná": "PR", "pernambuco": "PE", "piaui": "PI",
    "piauí": "PI", "rio de janeiro": "RJ", "rio grande do norte": "RN",
    "rio grande do sul": "RS", "rondonia": "RO", "rondônia": "RO",
    "roraima": "RR", "santa catarina": "SC", "sao paulo": "SP",
    "são paulo": "SP", "sergipe": "SE", "tocantins": "TO",
}

VALID_STATE_CODES = set(STATE_ABBREVIATIONS.values())


class CandidateNormalizer:
    """Normaliza e padroniza dados de candidatos de qualquer fonte."""

    @staticmethod
    def normalize(
        raw: Dict[str, Any], provider_name: str
    ) -> CandidateCanonicalProfile:
        """Normaliza um payload cru para CandidateCanonicalProfile.

        Aplica normalizacoes: trim, case, estado, telefone, skills, etc.
        """
        full_name = CandidateNormalizer._normalize_name(
            raw.get("full_name") or raw.get("name") or "N/A"
        )
        email = CandidateNormalizer._normalize_email(raw.get("email"))
        phone = CandidateNormalizer._normalize_phone(raw.get("phone"))
        state = CandidateNormalizer._normalize_state(raw.get("state"))
        city = (raw.get("city") or "").strip().title() or None
        country = (raw.get("country") or "Brasil").strip()

        skills = raw.get("skills", [])
        if isinstance(skills, str):
            skills = [s.strip() for s in skills.split(",") if s.strip()]
        skills = CandidateNormalizer._normalize_skills(skills)

        certifications = raw.get("certifications", [])
        if isinstance(certifications, str):
            certifications = [c.strip() for c in certifications.split(",") if c.strip()]

        languages = raw.get("languages", [])
        if isinstance(languages, str):
            languages = [lang.strip() for lang in languages.split(",") if lang.strip()]

        return CandidateCanonicalProfile(
            full_name=full_name,
            email=email,
            phone=phone,
            headline=_clean_text(raw.get("headline")),
            about=_clean_text(raw.get("about")),
            city=city,
            state=state,
            country=country,
            linkedin_url=_clean_url(raw.get("linkedin_url")),
            github_url=_clean_url(raw.get("github_url")),
            portfolio_url=_clean_url(raw.get("portfolio_url")),
            current_company=_clean_text(raw.get("current_company")),
            current_role=_clean_text(raw.get("current_role")),
            seniority=_clean_text(raw.get("seniority")),
            skills=skills,
            certifications=certifications,
            education=raw.get("education", []),
            languages=languages,
            experiences=raw.get("experiences", []),
            raw_data=raw,
            external_id=raw.get("external_id"),
            external_url=raw.get("external_url"),
            confidence=raw.get("confidence", 0.5),
        )

    @staticmethod
    def compute_hash(profile: CandidateCanonicalProfile) -> str:
        """Computa hash SHA-256 deterministic do perfil canonico.

        Exclui raw_data e confidence do hash para focar nos dados canonicos.
        """
        data = asdict(profile)
        data.pop("raw_data", None)
        data.pop("confidence", None)
        data.pop("external_id", None)
        data.pop("external_url", None)

        canonical_str = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    @staticmethod
    def to_candidate_dict(profile: CandidateCanonicalProfile) -> Dict[str, Any]:
        """Converte perfil canonico para dict compativel com o model Candidate."""
        return {
            "full_name": profile.full_name,
            "email": profile.email,
            "phone": profile.phone,
            "city": profile.city,
            "state": profile.state,
            "country": profile.country,
        }

    @staticmethod
    def to_canonical_json(profile: CandidateCanonicalProfile) -> Dict[str, Any]:
        """Converte perfil canonico para JSON serializavel (para snapshot)."""
        data = asdict(profile)
        data.pop("raw_data", None)
        return data

    @staticmethod
    def extract_text(profile: CandidateCanonicalProfile) -> str:
        """Gera texto searchavel a partir do perfil canonico."""
        parts = [profile.full_name]

        if profile.headline:
            parts.append(profile.headline)
        if profile.about:
            parts.append(profile.about)
        if profile.current_role:
            parts.append(f"Cargo: {profile.current_role}")
        if profile.current_company:
            parts.append(f"Empresa: {profile.current_company}")
        if profile.city:
            parts.append(f"Cidade: {profile.city}")
        if profile.state:
            parts.append(f"Estado: {profile.state}")
        if profile.skills:
            parts.append(f"Skills: {', '.join(profile.skills)}")
        if profile.certifications:
            parts.append(f"Certificacoes: {', '.join(profile.certifications)}")
        if profile.languages:
            parts.append(f"Idiomas: {', '.join(profile.languages)}")

        for exp in profile.experiences:
            exp_parts = []
            if exp.get("title"):
                exp_parts.append(exp["title"])
            if exp.get("company"):
                exp_parts.append(exp["company"])
            if exp.get("description"):
                exp_parts.append(exp["description"])
            if exp_parts:
                parts.append(" - ".join(exp_parts))

        for edu in profile.education:
            edu_parts = []
            if edu.get("degree"):
                edu_parts.append(edu["degree"])
            if edu.get("field"):
                edu_parts.append(edu["field"])
            if edu.get("school"):
                edu_parts.append(edu["school"])
            if edu_parts:
                parts.append(" - ".join(edu_parts))

        return "\n".join(parts)

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normaliza nome: trim, title case."""
        name = re.sub(r"\s+", " ", name.strip())
        return name.title() if name else "N/A"

    @staticmethod
    def _normalize_email(email: Optional[str]) -> Optional[str]:
        """Normaliza email: lowercase, trim."""
        if not email:
            return None
        email = email.strip().lower()
        if "@" not in email:
            return None
        return email

    @staticmethod
    def _normalize_phone(phone: Optional[str]) -> Optional[str]:
        """Normaliza telefone: apenas digitos, formato brasileiro."""
        if not phone:
            return None
        digits = re.sub(r"[^\d]", "", phone)
        if len(digits) < 8:
            return None
        if len(digits) == 11 and digits[0] != "0":
            return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
        if len(digits) == 10:
            return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
        if len(digits) == 13 and digits[:2] == "55":
            digits = digits[2:]
            return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
        return phone.strip()

    @staticmethod
    def _normalize_state(state: Optional[str]) -> Optional[str]:
        """Normaliza estado para sigla de 2 letras."""
        if not state:
            return None
        state = state.strip()
        if len(state) == 2 and state.upper() in VALID_STATE_CODES:
            return state.upper()
        state_lower = state.lower()
        if state_lower in STATE_ABBREVIATIONS:
            return STATE_ABBREVIATIONS[state_lower]
        return state.strip()

    @staticmethod
    def _normalize_skills(skills: list) -> list:
        """Normaliza lista de skills: dedup, trim, lowercase."""
        seen = set()
        normalized = []
        for skill in skills:
            if not skill:
                continue
            key = skill.strip().lower()
            if key and key not in seen:
                seen.add(key)
                normalized.append(skill.strip())
        return normalized


def _clean_text(text: Optional[str]) -> Optional[str]:
    """Limpa texto: trim, remove quebras duplas."""
    if not text:
        return None
    text = text.strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text if text else None


def _clean_url(url: Optional[str]) -> Optional[str]:
    """Limpa URL: trim, valida formato basico."""
    if not url:
        return None
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        if "." in url:
            url = f"https://{url}"
        else:
            return None
    return url
