"""
Normalizador para PDFs exportados do LinkedIn.

O export do LinkedIn costuma sair em duas colunas. Ao extrair texto do PDF,
a coluna lateral (Contato, Principais competencias, Languages, Certifications)
pode ser concatenada antes do corpo do curriculo. Isso faz importadores simples
confundirem nome, headline, skills e certificacoes.

Este modulo identifica esse layout, reconstrói campos quebrados por linha e
prependa um bloco estruturado ao texto original para que o parser regex e a
IA recebam contexto sem perder o conteudo bruto.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_LINKEDIN_STOP_SECTIONS = {
    "contato", "contact", "principais competências", "principais competencias",
    "top skills", "competências", "competencias", "skills", "languages",
    "idiomas", "certifications", "certificações", "certificacoes", "resumo",
    "summary", "experiência", "experiencia", "experience", "formação acadêmica",
    "formacao academica", "education",
}

_TECHNICAL_TERMS = {
    "gestão", "gestao", "workspace", "active", "directory", "data", "center",
    "certified", "professional", "expert", "android", "enterprise", "project",
    "manager", "senior", "ia", "digital", "transformação", "transformacao",
    "languages", "english", "certifications", "certificações", "competências",
    "competencias", "resumo", "contato", "linkedin", "personal",
}


def _strip_pdf_noise(text: str) -> str:
    """Remove caracteres invisiveis e artefatos comuns de extracao de PDF."""
    if not text:
        return ""
    cleaned = text.replace("\ufffe", "")
    cleaned = cleaned.replace("\u00ad", "")
    cleaned = cleaned.replace("\ufeff", "")
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*Page\s+\d+\s+of\s+\d+\s*$", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*P[áa]gina\s+\d+\s+de\s+\d+\s*$", "", cleaned)
    return cleaned


def _lines(text: str) -> List[str]:
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


def _section_key(line: str) -> str:
    return line.strip().lower().rstrip(":")


def _is_section(line: str) -> bool:
    return _section_key(line) in _LINKEDIN_STOP_SECTIONS


def _looks_like_email(line: str) -> bool:
    return bool(re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", line))


def _looks_like_url(line: str) -> bool:
    return bool(re.search(r"(?:https?://|www\.|linkedin\.com|github\.com)", line, re.I))


def _looks_like_location(line: str) -> bool:
    return bool(re.search(r",\s*[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç\s]+,\s*(?:Brasil|Brazil)\b", line, re.I))


def _looks_like_person_name(line: str) -> bool:
    candidate = line.strip()
    if not candidate or len(candidate) > 80 or len(candidate) < 5:
        return False
    if _is_section(candidate) or _looks_like_url(candidate) or _looks_like_email(candidate):
        return False
    if any(ch.isdigit() for ch in candidate):
        return False
    if any(sym in candidate for sym in ("|", "@", "/", "\\", ":", ";")):
        return False
    words = candidate.split()
    if len(words) < 2 or len(words) > 7:
        return False
    allowed_particles = {"de", "da", "do", "dos", "das", "e", "di", "del", "van", "von"}
    technical_hits = 0
    for word in words:
        low = word.lower().strip(".,()[]{}")
        if low in allowed_particles:
            continue
        if low in _TECHNICAL_TERMS:
            technical_hits += 1
        if not word[0].isalpha() or not word[0].isupper():
            return False
    return technical_hits == 0


def _join_broken_linkedin(lines: List[str]) -> str:
    """Reconstrói URL LinkedIn quebrada entre linhas ou por hifenização."""
    joined = "\n".join(lines)
    joined = re.sub(
        r"((?:https?://)?(?:www\.)?linkedin\.com/(?:in|pub)/)\s*\n\s*([A-Za-z0-9][A-Za-z0-9._%-]+)",
        r"\1\2",
        joined,
        flags=re.I,
    )
    joined = re.sub(
        r"((?:https?://)?(?:www\.)?linkedin\.com/(?:in|pub)/[A-Za-z0-9._%]+-)\s*\n\s*([A-Za-z0-9][A-Za-z0-9._%-]+)",
        r"\1\2",
        joined,
        flags=re.I,
    )
    joined = re.sub(r"(?i)(?<!https://)(?<!http://)(www\.linkedin\.com/[\w./%-]+)", r"https://\1", joined)
    joined = re.sub(r"(?i)(?<!https://)(?<!http://)(linkedin\.com/[\w./%-]+)", r"https://www.\1", joined)
    return joined


def _first_match(pattern: str, text: str, flags: int = re.I) -> Optional[str]:
    match = re.search(pattern, text, flags)
    return match.group(0).strip() if match else None


def _collect_between(lines: List[str], start_labels: set[str], stop_labels: set[str], hard_stop_index: Optional[int] = None) -> List[str]:
    started = False
    items: List[str] = []
    for idx, line in enumerate(lines):
        key = _section_key(line)
        if key in start_labels:
            started = True
            continue
        if not started:
            continue
        if hard_stop_index is not None and idx >= hard_stop_index:
            break
        if key in stop_labels:
            break
        if not line or _looks_like_email(line) or _looks_like_url(line):
            continue
        if _is_section(line):
            continue
        if re.match(r"^(?:Page|Página|Pagina)\s+\d+", line, re.I):
            continue
        items.append(line)
    return items


def _dedupe(items: List[str], limit: int = 50) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        normalized = re.sub(r"\s+", " ", item).strip(" -•\t")
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        out.append(normalized)
        if len(out) >= limit:
            break
    return out


def _extract_name_headline_location(lines: List[str]) -> Dict[str, Optional[str]]:
    for idx, line in enumerate(lines[:80]):
        if not _looks_like_person_name(line):
            continue
        next_line = lines[idx + 1] if idx + 1 < len(lines) else ""
        next2 = lines[idx + 2] if idx + 2 < len(lines) else ""
        previous_context = " ".join(lines[max(0, idx - 12):idx]).lower()
        likely_linkedin_body = (
            "certification" in previous_context
            or "certificações" in previous_context
            or "principais competências" in previous_context
            or "languages" in previous_context
            or "contato" in previous_context
            or "linkedin.com/in" in previous_context
        )
        if likely_linkedin_body or (next_line and not _is_section(next_line)):
            return {
                "name": line,
                "headline": next_line if next_line and not _is_section(next_line) and not _looks_like_location(next_line) else None,
                "location": next2 if _looks_like_location(next2) else (next_line if _looks_like_location(next_line) else None),
            }
    return {"name": None, "headline": None, "location": None}


def extract_linkedin_pdf_metadata(text: str) -> Dict[str, Any]:
    """Extrai metadados estruturados de um export de PDF do LinkedIn."""
    cleaned = _strip_pdf_noise(text)
    raw_lines = _lines(cleaned)
    rebuilt_text = _join_broken_linkedin(raw_lines)
    lines = _lines(rebuilt_text)

    linkedin_url = _first_match(r"https?://(?:www\.)?linkedin\.com/(?:in|pub)/[A-Za-z0-9._%/-]+", rebuilt_text)
    email = _first_match(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", rebuilt_text, flags=0)

    sites = re.findall(r"(?i)\b(?:https?://)?(?:www\.)?(?!linkedin\.com)[A-Za-z0-9-]+\.[A-Za-z]{2,}(?:/[\w./%-]*)?", rebuilt_text)
    portfolio = None
    for site in sites:
        if "@" in site or "linkedin.com" in site.lower():
            continue
        portfolio = site if site.startswith("http") else f"https://{site}"
        break

    name_data = _extract_name_headline_location(lines)
    name_idx = next((idx for idx, line in enumerate(lines) if line == name_data.get("name")), None)

    stop = {
        "languages", "idiomas", "certifications", "certificações", "certificacoes",
        "resumo", "summary", "experiência", "experiencia", "experience",
    }
    skills = _collect_between(
        lines,
        {"principais competências", "principais competencias", "top skills", "skills", "competências", "competencias"},
        stop,
        hard_stop_index=name_idx,
    )
    certifications = _collect_between(
        lines,
        {"certifications", "certificações", "certificacoes"},
        {"resumo", "summary", "experiência", "experiencia", "experience"},
        hard_stop_index=name_idx,
    )
    languages = _collect_between(
        lines,
        {"languages", "idiomas"},
        {"certifications", "certificações", "certificacoes", "resumo", "summary"},
        hard_stop_index=name_idx,
    )

    return {
        "is_linkedin_pdf": bool(linkedin_url and ("Page" in text or "Contato" in text or "Principais" in text)),
        "cleaned_text": rebuilt_text,
        "name": name_data.get("name"),
        "headline": name_data.get("headline"),
        "location": name_data.get("location"),
        "email": email.lower() if email else None,
        "linkedin": linkedin_url,
        "portfolio": portfolio,
        "skills": _dedupe(skills, limit=20),
        "languages": _dedupe(languages, limit=10),
        "certifications": _dedupe(certifications, limit=30),
    }


def build_structured_prefix(metadata: Dict[str, Any]) -> str:
    """Cria um bloco legivel para parser regex e LLM consumirem antes do texto bruto."""
    if not metadata.get("is_linkedin_pdf"):
        return ""

    lines = [
        "DADOS ESTRUTURADOS DETECTADOS - LINKEDIN PDF",
        "Origem: LinkedIn PDF Export",
    ]
    scalar_fields = [
        ("Nome", "name"),
        ("Titulo profissional", "headline"),
        ("Localizacao", "location"),
        ("Email", "email"),
        ("LinkedIn", "linkedin"),
        ("Portfolio", "portfolio"),
    ]
    for label, key in scalar_fields:
        value = metadata.get(key)
        if value:
            lines.append(f"{label}: {value}")

    for label, key in (
        ("Principais competencias", "skills"),
        ("Idiomas", "languages"),
        ("Certificacoes", "certifications"),
    ):
        values = metadata.get(key) or []
        if values:
            lines.append(f"{label}:")
            lines.extend(f"- {item}" for item in values)

    lines.append("FIM DOS DADOS ESTRUTURADOS DETECTADOS")
    return "\n".join(lines)


def normalize_linkedin_pdf_text(text: str) -> Dict[str, Any]:
    """Retorna texto enriquecido + metadados para curriculos exportados do LinkedIn."""
    metadata = extract_linkedin_pdf_metadata(text or "")
    cleaned_text = metadata.pop("cleaned_text")
    prefix = build_structured_prefix(metadata)
    normalized_text = f"{prefix}\n\n{cleaned_text}" if prefix else cleaned_text
    return {
        "text": normalized_text,
        "metadata": metadata,
        "is_linkedin_pdf": bool(metadata.get("is_linkedin_pdf")),
    }
