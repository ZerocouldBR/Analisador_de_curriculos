"""
Normalizador para PDFs exportados do LinkedIn.

O export do LinkedIn costuma sair em duas colunas. Ao extrair texto do PDF,
a coluna lateral (Contato, Principais competencias, Languages, Certifications)
pode ser concatenada antes do corpo do curriculo. Este normalizador reconstrói
o cabeçalho do perfil, corrige URLs quebradas e usa o slug do LinkedIn como
sinal forte para validar o nome real do candidato.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

_LINKEDIN_STOP_SECTIONS = {
    "contato", "contact", "principais competências", "principais competencias",
    "top skills", "competências", "competencias", "skills", "languages",
    "idiomas", "certifications", "certificações", "certificacoes", "resumo",
    "summary", "experiência", "experiencia", "experience", "formação acadêmica",
    "formacao academica", "education", "activity", "atividade", "publications",
}

_TECHNICAL_TERMS = {
    "gestão", "gestao", "workspace", "active", "directory", "data", "center",
    "certified", "certification", "professional", "expert", "android", "enterprise",
    "project", "manager", "senior", "sênior", "ia", "digital", "transformação",
    "transformacao", "languages", "english", "certifications", "certificações",
    "competências", "competencias", "resumo", "contato", "linkedin", "personal",
    "leadership", "pmo", "cloud", "analytics", "business", "intelligence",
    "tecnologia", "technology", "ltda", "ltpa", "inc", "sa", "s/a", "company",
    "empresa", "consultoria", "solutions", "solution", "sistemas", "system",
}

_HEADLINE_TERMS = {
    "analista", "assistente", "arquiteto", "cientista", "consultor", "coordenador",
    "desenvolvedor", "diretor", "engenheiro", "especialista", "gerente", "gestor",
    "head", "lead", "leader", "manager", "project", "product", "program", "senior",
    "sênior", "supervisor", "tech", "ti", "ia", "dados", "data", "cloud", "digital",
    "transformação", "transformacao", "pmo", "cto", "cio", "scrum", "agile",
}

_COMPANY_SUFFIX_TERMS = {
    "ltda", "ltpa", "sa", "s/a", "inc", "corp", "corporation", "company", "empresa",
    "tecnologia", "technology", "consultoria", "solutions", "sistemas", "system",
}

_ALLOWED_PARTICLES = {"de", "da", "do", "dos", "das", "e", "di", "del", "van", "von"}


def _strip_accents(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", value or "") if not unicodedata.combining(ch))


def _tokenize(value: str) -> List[str]:
    clean = _strip_accents(value).lower()
    return [t for t in re.split(r"[^a-z0-9]+", clean) if t]


def _strip_pdf_noise(text: str) -> str:
    if not text:
        return ""
    cleaned = text.replace("\ufffe", "").replace("\u00ad", "").replace("\ufeff", "")
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*Page\s+\d+\s+of\s+\d+\s*$", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*P[áa]gina\s+\d+\s+de\s+\d+\s*$", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*\d+\s*/\s*\d+\s*$", "", cleaned)
    return cleaned


def _lines(text: str) -> List[str]:
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


def _section_key(line: str) -> str:
    return line.strip().lower().rstrip(":")


def _is_section(line: str) -> bool:
    return _section_key(line) in _LINKEDIN_STOP_SECTIONS


def _looks_like_email(line: str) -> bool:
    return bool(re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", line))


def _looks_like_any_url(line: str) -> bool:
    return bool(re.search(r"(?:https?://|www\.|[A-Za-z0-9-]+\.[A-Za-z]{2,})", line, re.I))


def _looks_like_url(line: str) -> bool:
    return bool(re.search(r"(?:https?://|www\.|linkedin\.com|github\.com)", line, re.I))


def _looks_like_page_marker(line: str) -> bool:
    return bool(re.match(r"^(?:Page|Página|Pagina)\s+\d+\s+(?:of|de)\s+\d+$", line.strip(), re.I))


def _looks_like_location(line: str) -> bool:
    value = line.strip()
    if not value:
        return False
    if re.search(r",\s*[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç\s]+,\s*(?:Brasil|Brazil)\b", value, re.I):
        return True
    if value.count(",") >= 2 and re.search(r"\b(?:Brasil|Brazil)\b", value, re.I):
        return True
    if re.fullmatch(r"[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç\s.'-]+\s*(?:,|-|–)\s*[A-Z]{2}", value):
        return True
    if value.lower() in {"brasil", "brazil"}:
        return True
    return False


def _looks_like_professional_headline(line: str) -> bool:
    value = line.strip()
    if not value or _is_section(value) or _looks_like_location(value) or _looks_like_page_marker(value):
        return False
    if "|" in value:
        return True
    words = {w.strip(".,;:()[]{}|/").lower() for w in value.split()}
    return bool(words & _HEADLINE_TERMS)


def _looks_like_company_name(value: str) -> bool:
    tokens = set(_tokenize(value))
    return bool(tokens & _COMPANY_SUFFIX_TERMS)


def _looks_like_person_name(line: str) -> bool:
    candidate = line.strip()
    if not candidate or len(candidate) > 80 or len(candidate) < 5:
        return False
    if _is_section(candidate) or _looks_like_url(candidate) or _looks_like_email(candidate):
        return False
    if _looks_like_location(candidate) or _looks_like_page_marker(candidate):
        return False
    if _looks_like_company_name(candidate):
        return False
    if any(ch.isdigit() for ch in candidate):
        return False
    if any(sym in candidate for sym in ("|", "@", "/", "\\", ":", ";")):
        return False
    words = candidate.split()
    if len(words) < 2 or len(words) > 7:
        return False
    for word in words:
        low = word.lower().strip(".,()[]{}")
        if low in _ALLOWED_PARTICLES:
            continue
        if low in _TECHNICAL_TERMS:
            return False
        if not word[0].isalpha() or not word[0].isupper():
            return False
    return True


def _clean_linkedin_url(value: str) -> Optional[str]:
    candidate = re.sub(r"\s*\(LinkedIn\).*", "", value or "", flags=re.I)
    candidate = re.sub(r"\s+", "", candidate)
    candidate = re.sub(r"(?i)^www\.", "https://www.", candidate)
    candidate = re.sub(r"(?i)^(?<!https://)(?<!http://)linkedin\.com", "https://www.linkedin.com", candidate)
    candidate = re.sub(r"(?i)^(?<!https://)(?<!http://)www\.linkedin\.com", "https://www.linkedin.com", candidate)
    match = re.search(r"https?://(?:www\.)?linkedin\.com/(?:in|pub)/[A-Za-z0-9._%-]+", candidate, re.I)
    if not match:
        return None
    url = match.group(0).rstrip(".-_/ ")
    return re.sub(r"^http://", "https://", url, flags=re.I)


def _canonical_linkedin_url_from_lines(lines: List[str]) -> Optional[str]:
    """Extrai LinkedIn mesmo quando a URL quebra em linhas.

    Para em qualquer nova URL/site que nao seja LinkedIn, evitando grudar portfolio
    no slug do perfil.
    """
    for idx, line in enumerate(lines):
        if "linkedin.com/" not in line.lower():
            continue
        parts = [line]
        for nxt in lines[idx + 1: idx + 6]:
            nxt_clean = nxt.strip()
            key = _section_key(nxt_clean)
            if key in _LINKEDIN_STOP_SECTIONS or _looks_like_email(nxt_clean):
                break
            if "linkedin.com/" in nxt_clean.lower():
                break
            if _looks_like_any_url(nxt_clean):
                break
            if "(" in nxt_clean and "linkedin" not in nxt_clean.lower():
                break
            if re.match(r"^[A-Za-z0-9_-]+(?:\s*\(LinkedIn\))?$", nxt_clean, re.I):
                parts.append(nxt_clean)
                continue
            break
        url = _clean_linkedin_url("".join(parts))
        if url:
            return url
    return None


def _join_broken_linkedin(lines: List[str]) -> str:
    joined = "\n".join(lines)
    canonical = _canonical_linkedin_url_from_lines(lines)
    if canonical:
        joined = f"{canonical}\n{joined}"
    joined = re.sub(r"((?:https?://)?(?:www\.)?linkedin\.com/(?:in|pub)/)\s*\n\s*([A-Za-z0-9][A-Za-z0-9_-]+)", r"\1\2", joined, flags=re.I)
    joined = re.sub(r"((?:https?://)?(?:www\.)?linkedin\.com/(?:in|pub)/[A-Za-z0-9_-]+-)\s*\n\s*([A-Za-z0-9][A-Za-z0-9_-]+)", r"\1\2", joined, flags=re.I)
    joined = re.sub(r"(?i)(?<!https://)(?<!http://)(www\.linkedin\.com/[\w./%-]+)", r"https://\1", joined)
    joined = re.sub(r"(?i)(?<!https://)(?<!http://)(linkedin\.com/[\w./%-]+)", r"https://www.\1", joined)
    return joined


def _first_match(pattern: str, text: str, flags: int = re.I) -> Optional[str]:
    match = re.search(pattern, text, flags)
    return match.group(0).strip() if match else None


def _find_first_section_index(lines: List[str], labels: set[str]) -> Optional[int]:
    for idx, line in enumerate(lines):
        if _section_key(line) in labels:
            return idx
    return None


def _slug_tokens(linkedin_url: Optional[str]) -> List[str]:
    if not linkedin_url:
        return []
    match = re.search(r"linkedin\.com/(?:in|pub)/([^/?#\s]+)", linkedin_url, re.I)
    if not match:
        return []
    return [t for t in _tokenize(match.group(1)) if not t.isdigit() and len(t) > 1]


def _score_name_against_slug(name: str, slug_tokens: List[str]) -> float:
    if not slug_tokens or not _looks_like_person_name(name):
        return 0.0
    name_tokens = set(_tokenize(name))
    usable_slug = {t for t in slug_tokens if len(t) > 1 and not t.isdigit()}
    if not usable_slug:
        return 0.0
    return len(name_tokens & usable_slug) / max(len(name_tokens), 1)


def _extract_linkedin_profile_header(lines: List[str], linkedin_url: Optional[str] = None) -> Dict[str, Optional[str]]:
    slug = _slug_tokens(linkedin_url)
    resumo_idx = _find_first_section_index(lines, {"resumo", "summary"})
    search_end = resumo_idx if resumo_idx is not None else min(len(lines), 140)
    search_start = max(0, search_end - 25)
    clean_window = [l for l in lines[search_start:search_end] if not _looks_like_page_marker(l) and not _is_section(l)]

    best: Tuple[Optional[str], Optional[str], Optional[str], float] = (None, None, None, 0.0)
    for idx, line in enumerate(clean_window):
        if not _looks_like_person_name(line):
            continue
        after = clean_window[idx + 1: idx + 5]
        location = next((l for l in after if _looks_like_location(l)), None)
        headline_parts = [l for l in after if l and not _looks_like_location(l) and not _looks_like_person_name(l)]
        headline = " ".join(headline_parts).strip() or None
        score = 0.45
        if any(_looks_like_professional_headline(h) for h in after):
            score += 0.2
        if location:
            score += 0.15
        score += min(_score_name_against_slug(line, slug), 1.0) * 0.5
        if score > best[3]:
            best = (line, headline, location, score)

    if best[0] and best[3] >= 0.55:
        return {"name": best[0], "headline": best[1], "location": best[2]}
    return {"name": None, "headline": None, "location": best[2]}


def _extract_name_headline_location(lines: List[str], linkedin_url: Optional[str] = None) -> Dict[str, Optional[str]]:
    anchored = _extract_linkedin_profile_header(lines, linkedin_url)
    if anchored.get("name"):
        return anchored

    slug = _slug_tokens(linkedin_url)
    best: Tuple[Optional[str], Optional[str], Optional[str], float] = (None, None, None, 0.0)
    for idx, line in enumerate(lines[:140]):
        if not _looks_like_person_name(line):
            continue
        next_lines = lines[idx + 1:idx + 5]
        location = next((l for l in next_lines if _looks_like_location(l)), None)
        headline = " ".join(l for l in next_lines if l and not _looks_like_location(l) and not _is_section(l)) or None
        score = 0.2 + _score_name_against_slug(line, slug) * 0.7
        if any(_looks_like_professional_headline(l) for l in next_lines):
            score += 0.2
        if location:
            score += 0.1
        if score > best[3]:
            best = (line, headline, location, score)

    if best[0] and best[3] >= 0.45:
        return {"name": best[0], "headline": best[1], "location": best[2]}
    return {"name": None, "headline": None, "location": anchored.get("location")}


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
        if _is_section(line) or _looks_like_page_marker(line):
            continue
        items.append(line)
    return items


def _dedupe(items: List[str], limit: int = 50) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        normalized = re.sub(r"\s+", " ", item).strip(" -•\t")
        key = normalized.lower()
        if not normalized or key in seen or _looks_like_page_marker(normalized):
            continue
        seen.add(key)
        out.append(normalized)
        if len(out) >= limit:
            break
    return out


def _extract_portfolio(lines: List[str], linkedin_url: Optional[str]) -> Optional[str]:
    for line in lines:
        if _looks_like_email(line) or "linkedin.com" in line.lower():
            continue
        matches = re.findall(r"(?i)(?:https?://)?(?:www\.)?[A-Za-z0-9-]+\.[A-Za-z]{2,}(?:/[\w./%-]*)?", line)
        for site in matches:
            clean = site.strip().rstrip(".,;) ")
            if not clean or "linkedin.com" in clean.lower() or clean.lower() in {"https", "http", "www.https"}:
                continue
            clean_url = clean if re.match(r"https?://", clean, re.I) else f"https://{clean}"
            if linkedin_url and clean_url.lower() == linkedin_url.lower():
                continue
            return clean_url
    return None


def extract_linkedin_pdf_metadata(text: str) -> Dict[str, Any]:
    cleaned = _strip_pdf_noise(text)
    raw_lines = _lines(cleaned)
    canonical_url = _canonical_linkedin_url_from_lines(raw_lines)
    rebuilt_text = _join_broken_linkedin(raw_lines)
    lines = _lines(rebuilt_text)

    linkedin_url = canonical_url or _first_match(r"https?://(?:www\.)?linkedin\.com/(?:in|pub)/[A-Za-z0-9_-]+", rebuilt_text)
    email = _first_match(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", rebuilt_text, flags=0)
    portfolio = _extract_portfolio(raw_lines, linkedin_url)

    name_data = _extract_name_headline_location(lines, linkedin_url)
    name_idx = next((idx for idx, line in enumerate(lines) if line == name_data.get("name")), None)

    stop = {"languages", "idiomas", "certifications", "certificações", "certificacoes", "resumo", "summary", "experiência", "experiencia", "experience"}
    skills = _collect_between(lines, {"principais competências", "principais competencias", "top skills", "skills", "competências", "competencias"}, stop, hard_stop_index=name_idx)
    certifications = _collect_between(lines, {"certifications", "certificações", "certificacoes"}, {"resumo", "summary", "experiência", "experiencia", "experience"}, hard_stop_index=name_idx)
    languages = _collect_between(lines, {"languages", "idiomas"}, {"certifications", "certificações", "certificacoes", "resumo", "summary"}, hard_stop_index=name_idx)

    return {
        "is_linkedin_pdf": bool(linkedin_url and ("Page" in text or "Contato" in text or "Principais" in text or "Languages" in text or "Certifications" in text)),
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
        "layout_detected": "linkedin_two_column_pdf" if linkedin_url else None,
    }


def build_structured_prefix(metadata: Dict[str, Any]) -> str:
    if not metadata.get("is_linkedin_pdf"):
        return ""
    lines = ["DADOS ESTRUTURADOS DETECTADOS - LINKEDIN PDF", "Origem: LinkedIn PDF Export", "Layout: duas colunas reconstruido"]
    for label, key in (("Nome", "name"), ("Titulo profissional", "headline"), ("Localizacao", "location"), ("Email", "email"), ("LinkedIn", "linkedin"), ("Portfolio", "portfolio")):
        value = metadata.get(key)
        if value:
            lines.append(f"{label}: {value}")
    for label, key in (("Principais competencias", "skills"), ("Idiomas", "languages"), ("Certificacoes", "certifications")):
        values = metadata.get(key) or []
        if values:
            lines.append(f"{label}:")
            lines.extend(f"- {item}" for item in values)
    lines.append("FIM DOS DADOS ESTRUTURADOS DETECTADOS")
    return "\n".join(lines)


def normalize_linkedin_pdf_text(text: str) -> Dict[str, Any]:
    metadata = extract_linkedin_pdf_metadata(text or "")
    cleaned_text = metadata.pop("cleaned_text")
    prefix = build_structured_prefix(metadata)
    normalized_text = f"{prefix}\n\n{cleaned_text}" if prefix else cleaned_text
    return {"text": normalized_text, "metadata": metadata, "is_linkedin_pdf": bool(metadata.get("is_linkedin_pdf"))}
