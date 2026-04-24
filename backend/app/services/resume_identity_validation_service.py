"""
Validador deterministico dos campos de identidade do candidato.

Impede que endereco, cidade, paginacao, cargo, empresa, headline,
competencia ou texto narrativo sejam gravados como nome do candidato.
Tambem usa o slug do LinkedIn como evidencia forte para escolher o nome.
"""
from __future__ import annotations

import re
import unicodedata
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

_COMPANY_WORDS = {
    "ltda", "ltpa", "sa", "s/a", "inc", "corp", "corporation", "company", "empresa",
    "tecnologia", "technology", "consultoria", "solutions", "solution", "sistemas", "system",
    "software", "servicos", "serviços", "consulting",
}

_LOCATION_TERMS = {
    "brasil", "brazil", "rio grande do sul", "são paulo", "sao paulo",
    "santa catarina", "paraná", "parana", "minas gerais", "rio de janeiro",
}

_ALLOWED_PARTICLES = {"de", "da", "do", "dos", "das", "e", "di", "del", "van", "von"}


def _strip_accents(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", value or "") if not unicodedata.combining(ch))


def _tokens(value: Optional[str]) -> List[str]:
    return [t for t in re.split(r"[^a-z0-9]+", _strip_accents(value or "").lower()) if t]


def _norm(value: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _slug_tokens(linkedin_url: Optional[str]) -> List[str]:
    match = re.search(r"linkedin\.com/(?:in|pub)/([^/?#\s]+)", linkedin_url or "", re.I)
    if not match:
        return []
    return [t for t in _tokens(match.group(1)) if not t.isdigit() and len(t) > 1]


def _slug_overlap_score(name: Optional[str], linkedin_url: Optional[str]) -> float:
    name_tokens = set(_tokens(name))
    slug = set(_slug_tokens(linkedin_url))
    if not name_tokens or not slug:
        return 0.0
    return len(name_tokens & slug) / max(len(name_tokens), 1)


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


def looks_like_company(value: Optional[str]) -> bool:
    return bool(set(_tokens(value)) & _COMPANY_WORDS)


def is_valid_person_name(value: Optional[str]) -> bool:
    text = _norm(value)
    if not text or len(text) < 5 or len(text) > 80:
        return False
    if looks_like_page_marker(text) or looks_like_email_or_url(text) or looks_like_location(text):
        return False
    if looks_like_title_or_skill(text) or looks_like_company(text):
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


def _candidate_name_score(value: str, idx: int, lines: List[str], linkedin_url: Optional[str] = None) -> float:
    score = 0.0
    if is_valid_person_name(value):
        score += 0.5
    score += _slug_overlap_score(value, linkedin_url) * 0.6
    next_lines = lines[idx + 1: idx + 5]
    if any(looks_like_title_or_skill(line) for line in next_lines):
        score += 0.15
    if any(looks_like_location(line) for line in next_lines):
        score += 0.15
    previous = " ".join(lines[max(0, idx - 8):idx]).lower()
    if "linkedin.com/in" in previous or "certifications" in previous or "certificações" in previous:
        score += 0.05
    if idx < 40:
        score += 0.03
    return min(score, 0.99)


def find_best_name_in_text(text: str, linkedin_url: Optional[str] = None) -> Tuple[Optional[str], float]:
    lines = [_norm(l) for l in (text or "").splitlines() if _norm(l)]
    if not lines:
        return None, 0.0

    candidates: List[Tuple[str, float]] = []
    for idx, line in enumerate(lines[:160]):
        if is_valid_person_name(line):
            candidates.append((line, _candidate_name_score(line, idx, lines, linkedin_url)))

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
        linkedin_url = _norm(linkedin_metadata.get("linkedin") or personal.get("linkedin"))

        if linkedin_name and is_valid_person_name(linkedin_name):
            if current_name != linkedin_name:
                notes.append(f"name_overridden_by_linkedin_pdf:{current_name or 'empty'}->{linkedin_name}")
            personal["name"] = linkedin_name
            personal["name_confidence"] = 0.99
        else:
            current_score = _slug_overlap_score(current_name, linkedin_url) if is_valid_person_name(current_name) else 0.0
            fallback_name, fallback_conf = find_best_name_in_text(raw_text, linkedin_url)
            fallback_score = _slug_overlap_score(fallback_name, linkedin_url) if fallback_name else 0.0

            if not is_valid_person_name(current_name):
                if fallback_name:
                    notes.append(f"name_recovered_from_text:{current_name or 'invalid'}->{fallback_name}")
                    personal["name"] = fallback_name
                    personal["name_confidence"] = max(float(personal.get("name_confidence") or 0), fallback_conf)
                else:
                    notes.append(f"invalid_name_cleared:{current_name or 'empty'}")
                    personal["name"] = None
                    personal["name_confidence"] = 0.0
            elif fallback_name and fallback_score > current_score:
                notes.append(f"name_replaced_by_slug_match:{current_name}->{fallback_name}")
                personal["name"] = fallback_name
                personal["name_confidence"] = max(float(personal.get("name_confidence") or 0), fallback_conf)

        if personal.get("name") and personal.get("location"):
            if _norm(personal["name"]).lower() == _norm(personal["location"]).lower():
                notes.append("name_equal_location_cleared")
                personal["name"] = linkedin_name if is_valid_person_name(linkedin_name) else None
                personal["name_confidence"] = 0.99 if personal.get("name") else 0.0

        linkedin_location = _norm(linkedin_metadata.get("location"))
        if linkedin_location and not personal.get("location"):
            personal["location"] = linkedin_location
            personal["location_confidence"] = 0.96
            notes.append("location_filled_from_linkedin_pdf")

        enriched_data.setdefault("metadata", {})
        enriched_data["metadata"]["identity_validation"] = {
            "notes": notes,
            "name_valid": is_valid_person_name(personal.get("name")),
            "linkedin_slug_tokens": _slug_tokens(linkedin_url),
        }
        return enriched_data

    @staticmethod
    def is_valid_person_name(value: Optional[str]) -> bool:
        return is_valid_person_name(value)
