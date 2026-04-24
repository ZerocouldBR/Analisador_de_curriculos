"""
Validador deterministico dos campos de identidade do candidato.

Objetivo: impedir que endereco, cidade, paginacao, cargo, headline,
competencia ou texto narrativo sejam gravados como nome do candidato.

Esta camada e propositalmente conservadora e roda depois do parser regex,
da IA e dos normalizadores de layout. Ela nao substitui a IA; ela atua como
um guardrail antes de persistir dados sensiveis no cadastro.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

_SECTION_WORDS = {
    "contato", "contact", "resumo", "summary", "sobre", "about",
    "experiencia", "experiência", "experience", "formacao", "formação",
    "education", "certifications", "certificacoes", "certificações",
    "languages", "idiomas", "skills", "competencias", "competências",
}

_TITLE_WORDS = {
    "analista", "assistente", "arquiteto", "cientista", "consultor", "coordenador",
    "desenvolvedor", "diretor", "engenheiro", "especialista", "gerente", "gestor",
    "lead", "leader", "manager", "project", "product", "program", "senior", "sênior",
    "supervisor", "tech", "ti", "ia", "dados", "data", "cloud", "digital", "pmo",
    "infraestrutura", "inteligencia", "inteligência", "transformacao", "transformação",
}

_TECH_SKILL_WORDS = {
    "active", "directory", "workspace", "android", "enterprise", "certified",
    "professional", "expert", "gestao", "gestão", "data", "center", "sap", "aws",
    "azure", "google", "cloud", "python", "java", "javascript", "typescript",
    "react", "docker", "kubernetes", "oracle", "linux", "windows", "itil", "cobit",
}

_LOCATION_TERMS = {
    "brasil", "brazil", "rio grande do sul", "são paulo", "sao paulo",
    "santa catarina", "paraná", "parana", "minas gerais", "rio de janeiro",
}

_ALLOWED_PARTICLES = {"de", "da", "do", "dos", "das", "e", "di", "del", "van", "von"}


def _norm(value: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def looks_like_page_marker(value: Optional[str]) -> bool:
    text = _norm(value)
    return bool(
        re.fullmatch(r"(?:Page|Página|Pagina)\s+\d+\s+(?:of|de)\s+\d+", text, re.I)
        or re.fullmatch(r"\d+\s*/\s*\d+", text)
    )


def looks_like_email_or_url(value: Optional[str]) -> bool:
    text = _norm(value)
    return bool(re.search(r"@|(?:https?://|www\.|linkedin\.com|github\.com)", text, re.I))


def looks_like_location(value: Optional[str]) -> bool:
    text = _norm(value)
    if not text:
        return False
    low = text.lower()
    if any(term in low for term in _LOCATION_TERMS) and "," in text:
        return True
    if text.count(",") >= 2 and re.search(r"\b(?:Brasil|Brazil)\b", text, re.I):
        return True
    if re.fullmatch(r"[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç\s.'-]+\s*(?:,|-|–)\s*[A-Z]{2}", text):
        return True
    if re.search(r"\b(?:Rua|Avenida|Av\.|Travessa|Bairro|CEP)\b", text, re.I):
        return True
    return False


def looks_like_title_or_skill(value: Optional[str]) -> bool:
    text = _norm(value)
    if not text:
        return False
    low_words = {w.strip(".,;:()[]{}|/\\").lower() for w in text.split()}
    if "|" in text:
        return True
    if low_words & _TITLE_WORDS:
        return True
    if low_words & _TECH_SKILL_WORDS:
        return True
    if re.search(r"\bgest[aã]o\s+d[eo]\b", text, re.I):
        return True
    if re.search(r"\b(?:especialista|gerente|analista|coordenador|diretor|supervisor)\s+(?:de|em)\b", text, re.I):
        return True
    return False


def is_valid_person_name(value: Optional[str]) -> bool:
    text = _norm(value)
    if not text or len(text) < 5 or len(text) > 80:
        return False
    if looks_like_page_marker(text) or looks_like_email_or_url(text) or looks_like_location(text):
        return False
    if looks_like_title_or_skill(text):
        return False
    if any(ch.isdigit() for ch in text):
        return False
    if any(sym in text for sym in ("|", "@", "/", "\\", ":", ";", "#")):
        return False
    if text.lower().rstrip(":") in _SECTION_WORDS:
        return False

    words = text.split()
    if len(words) < 2 or len(words) > 7:
        return False

    capitalized = 0
    for word in words:
        clean = word.strip(".,()[]{}'")
        low = clean.lower()
        if low in _ALLOWED_PARTICLES:
            continue
        if not clean or not clean[0].isalpha() or not clean[0].isupper():
            return False
        capitalized += 1

    return capitalized >= 2


def _candidate_name_score(value: str, idx: int, lines: List[str]) -> float:
    score = 0.5
    if is_valid_person_name(value):
        score += 0.3
    next_lines = lines[idx + 1: idx + 4]
    if any(looks_like_title_or_skill(line) for line in next_lines):
        score += 0.2
    if any(looks_like_location(line) for line in next_lines):
        score += 0.15
    previous = " ".join(lines[max(0, idx - 8):idx]).lower()
    if "linkedin.com/in" in previous or "certifications" in previous or "certificações" in previous:
        score += 0.1
    if idx < 30:
        score += 0.05
    return min(score, 0.99)


def find_best_name_in_text(text: str) -> Tuple[Optional[str], float]:
    lines = [_norm(l) for l in (text or "").splitlines() if _norm(l)]
    if not lines:
        return None, 0.0

    candidates: List[Tuple[str, float]] = []
    for idx, line in enumerate(lines[:120]):
        if is_valid_person_name(line):
            candidates.append((line, _candidate_name_score(line, idx, lines)))

    if not candidates:
        return None, 0.0

    candidates.sort(key=lambda item: item[1], reverse=True)
    return candidates[0]


class ResumeIdentityValidationService:
    """Guardrail final de identidade do curriculo."""

    @staticmethod
    def sanitize_enriched_data(
        enriched_data: Dict[str, Any],
        raw_text: str = "",
        linkedin_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        linkedin_metadata = linkedin_metadata or {}
        personal = enriched_data.setdefault("personal_info", {})
        notes: List[str] = []

        current_name = _norm(personal.get("name"))
        linkedin_name = _norm(linkedin_metadata.get("name"))

        # LinkedIn PDF e uma fonte de alta confianca quando o normalizador achou
        # nome ancorado antes da headline e da localizacao.
        if linkedin_name and is_valid_person_name(linkedin_name):
            if current_name != linkedin_name:
                notes.append(f"name_overridden_by_linkedin_pdf:{current_name or 'empty'}->{linkedin_name}")
            personal["name"] = linkedin_name
            personal["name_confidence"] = 0.99
        elif not is_valid_person_name(current_name):
            fallback_name, fallback_conf = find_best_name_in_text(raw_text)
            if fallback_name:
                notes.append(f"name_recovered_from_text:{current_name or 'invalid'}->{fallback_name}")
                personal["name"] = fallback_name
                personal["name_confidence"] = max(float(personal.get("name_confidence") or 0), fallback_conf)
            else:
                notes.append(f"invalid_name_cleared:{current_name or 'empty'}")
                personal["name"] = None
                personal["name_confidence"] = 0.0

        # Nunca permitir que localizacao esteja duplicada como nome.
        if personal.get("name") and personal.get("location"):
            if _norm(personal["name"]).lower() == _norm(personal["location"]).lower():
                notes.append("name_equal_location_cleared")
                personal["name"] = linkedin_name if is_valid_person_name(linkedin_name) else None
                personal["name_confidence"] = 0.99 if personal.get("name") else 0.0

        # Se o campo location vier vazio e o normalizador tiver localizacao, preenche.
        linkedin_location = _norm(linkedin_metadata.get("location"))
        if linkedin_location and not personal.get("location"):
            personal["location"] = linkedin_location
            personal["location_confidence"] = 0.96
            notes.append("location_filled_from_linkedin_pdf")

        enriched_data.setdefault("metadata", {})
        enriched_data["metadata"]["identity_validation"] = {
            "notes": notes,
            "name_valid": is_valid_person_name(personal.get("name")),
        }
        return enriched_data

    @staticmethod
    def is_valid_person_name(value: Optional[str]) -> bool:
        return is_valid_person_name(value)
