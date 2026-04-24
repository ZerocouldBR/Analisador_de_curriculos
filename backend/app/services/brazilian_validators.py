"""
Validadores e normalizadores para dados brasileiros de curriculo.

Foco em:
- CPF com checksum (DV mod 11)
- Telefone normalizado para E.164 (ex: 5511999998888)
- Email normalizado (lower + strip)
- Data de nascimento com parser flexivel (dd/mm/yyyy, "15 de janeiro de 1990", etc.)
- URL do LinkedIn canonica preservando /in/ vs /pub/
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from typing import Optional

try:
    from dateutil import parser as _date_parser  # type: ignore
except ImportError:
    _date_parser = None  # type: ignore


# ============================================================
# CPF
# ============================================================

_CPF_BLACKLIST = {
    "00000000000", "11111111111", "22222222222", "33333333333",
    "44444444444", "55555555555", "66666666666", "77777777777",
    "88888888888", "99999999999",
}


def only_digits(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"\D", "", text)


def is_valid_cpf(cpf: Optional[str]) -> bool:
    """
    Valida CPF aplicando o algoritmo de DV mod 11.
    Rejeita CPFs com todos digitos iguais (000.000.000-00, 111.111.111-11, etc.).
    """
    digits = only_digits(cpf)
    if len(digits) != 11:
        return False
    if digits in _CPF_BLACKLIST:
        return False

    # Primeiro digito verificador
    total = sum(int(digits[i]) * (10 - i) for i in range(9))
    rest = (total * 10) % 11
    dv1 = rest if rest < 10 else 0
    if dv1 != int(digits[9]):
        return False

    # Segundo digito verificador
    total = sum(int(digits[i]) * (11 - i) for i in range(10))
    rest = (total * 10) % 11
    dv2 = rest if rest < 10 else 0
    if dv2 != int(digits[10]):
        return False

    return True


def format_cpf(cpf: Optional[str]) -> Optional[str]:
    """Retorna o CPF no formato 000.000.000-00 se valido, senao None."""
    digits = only_digits(cpf)
    if not is_valid_cpf(digits):
        return None
    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"


# ============================================================
# Telefone
# ============================================================

_PHONE_DIGITS_RE = re.compile(r"\D+")


def normalize_phone_br(phone: Optional[str]) -> Optional[str]:
    """
    Normaliza um telefone brasileiro para o formato E.164 (+55DDDNNNNNNNNN).

    Regras:
    - Extrai apenas digitos.
    - Se comeca com 55 e tem 12 ou 13 digitos, assume ja com codigo do pais.
    - Se tem 10 ou 11 digitos, assume DDD + numero e prefixa 55.
    - Retorna "+55..." quando valido, senao None.
    - Numero movel deve ter 11 digitos (DDD+9+8digitos); fixo 10.
    """
    if not phone:
        return None
    digits = _PHONE_DIGITS_RE.sub("", phone)

    if digits.startswith("55") and len(digits) in (12, 13):
        core = digits[2:]
    elif len(digits) in (10, 11):
        core = digits
    else:
        return None

    # core deve ter 10 (fixo) ou 11 (movel) digitos
    if len(core) not in (10, 11):
        return None

    ddd = core[:2]
    if not ddd.isdigit() or int(ddd) < 11 or int(ddd) > 99:
        return None

    # Se 11 digitos, o 3o tem que ser 9 (regra do movel brasileiro)
    if len(core) == 11 and core[2] != "9":
        return None

    return f"+55{core}"


def format_phone_br_display(phone_e164: Optional[str]) -> Optional[str]:
    """
    Converte +5511999998888 para (11) 99999-8888 para exibicao.
    Mantem a string original se nao conseguir reconhecer.
    """
    if not phone_e164:
        return None
    digits = only_digits(phone_e164)
    if digits.startswith("55"):
        digits = digits[2:]
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    return phone_e164


# ============================================================
# Email
# ============================================================

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def normalize_email(email: Optional[str]) -> Optional[str]:
    """
    Normaliza email: strip + lower. Retorna None se formato invalido.
    """
    if not email:
        return None
    normalized = email.strip().lower()
    if not _EMAIL_RE.match(normalized):
        return None
    return normalized


# ============================================================
# Data de nascimento
# ============================================================

_MONTH_NAMES = {
    "janeiro": 1, "jan": 1,
    "fevereiro": 2, "fev": 2,
    "marco": 3, "março": 3, "mar": 3,
    "abril": 4, "abr": 4,
    "maio": 5, "mai": 5,
    "junho": 6, "jun": 6,
    "julho": 7, "jul": 7,
    "agosto": 8, "ago": 8,
    "setembro": 9, "set": 9,
    "outubro": 10, "out": 10,
    "novembro": 11, "nov": 11,
    "dezembro": 12, "dez": 12,
}


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


def parse_birth_date(text: Optional[str]) -> Optional[date]:
    """
    Faz parse flexivel de uma data de nascimento.

    Aceita:
    - 15/01/1990, 15-01-1990, 15.01.1990
    - 1990-01-15
    - "15 de janeiro de 1990"
    - "jan 15, 1990"

    Retorna None se nao conseguir interpretar ou se a data resultante for
    fora de um range razoavel (ano entre 1900 e ano atual).
    """
    if not text:
        return None

    s = _strip_accents(text.strip()).lower()
    if not s:
        return None

    # Padroes numericos classicos
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            candidate = datetime.strptime(s, fmt).date()
            if _plausible_birth(candidate):
                return candidate
        except ValueError:
            pass

    # "15 de janeiro de 1990"
    m = re.search(
        r"(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})", s
    )
    if m:
        day = int(m.group(1))
        month_name = m.group(2)
        year = int(m.group(3))
        month = _MONTH_NAMES.get(month_name)
        if month:
            try:
                candidate = date(year, month, day)
                if _plausible_birth(candidate):
                    return candidate
            except ValueError:
                pass

    # Fallback dateutil (em ingles/heuristico)
    if _date_parser is not None:
        try:
            parsed = _date_parser.parse(s, dayfirst=True, fuzzy=True, default=datetime(1900, 1, 1))
            if parsed.year >= 1900:
                candidate = parsed.date()
                if _plausible_birth(candidate):
                    return candidate
        except (ValueError, TypeError, OverflowError):
            pass

    return None


def _plausible_birth(d: date) -> bool:
    today = date.today()
    if d.year < 1900:
        return False
    if d > today:
        return False
    # idade minima plausivel 14 anos
    if (today.year - d.year) < 14:
        return False
    return True


# ============================================================
# LinkedIn URL
# ============================================================

_LINKEDIN_SLUG_RE = re.compile(
    r"(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/(in|pub)/([A-Za-z0-9\-_%]+)",
    re.IGNORECASE,
)


def normalize_linkedin_url(url: Optional[str]) -> Optional[str]:
    """
    Normaliza URL do LinkedIn. Preserva o tipo de path (/in/ ou /pub/).
    Retorna None se nao reconhecer o padrao.
    """
    if not url:
        return None
    s = url.strip().rstrip("/,;.)")
    if not s:
        return None

    m = _LINKEDIN_SLUG_RE.search(s)
    if m:
        path_type = m.group(1).lower()
        slug = m.group(2).rstrip("-_")
        if len(slug) >= 3:
            return f"https://www.linkedin.com/{path_type}/{slug}"

    # Aceitar URL simples com linkedin.com no meio
    if "linkedin.com" in s.lower():
        if not s.lower().startswith("http"):
            s = "https://" + s
        return s

    return None


# ============================================================
# Nome vs email cross-validation
# ============================================================

def email_prefix_tokens(email: Optional[str]) -> set:
    """Retorna os tokens do prefixo do email (antes do @), separados por ponto/underscore/hifen."""
    if not email or "@" not in email:
        return set()
    prefix = email.split("@", 1)[0].lower()
    parts = re.split(r"[._\-+]", prefix)
    return {p for p in parts if len(p) >= 3}


def name_email_match_ratio(name: Optional[str], email: Optional[str]) -> float:
    """
    Mede o quanto o nome e o prefixo do email se sobrepoem.
    Retorna 0.0 (nenhum token em comum) ate 1.0 (todos tokens do nome no email).
    """
    if not name or not email:
        return 0.0
    tokens = email_prefix_tokens(email)
    if not tokens:
        return 0.0

    name_norm = _strip_accents(name.lower())
    # Ignorar preposicoes e abreviacoes
    ignored = {"de", "da", "do", "dos", "das", "e", "di", "del", "jr", "sr", "neto"}
    name_tokens = {w for w in re.split(r"\s+", name_norm) if len(w) >= 3 and w not in ignored}
    if not name_tokens:
        return 0.0

    matched = 0
    for nt in name_tokens:
        # Considera um token em comum se aparece como substring em algum token do email
        if any(nt in et or et in nt for et in tokens):
            matched += 1
    return matched / len(name_tokens)


# ============================================================
# Fuzzy match de nome contra texto bruto
# ============================================================

def name_appears_in_text(name: Optional[str], raw_text: Optional[str]) -> float:
    """
    Mede o quanto os tokens do nome aparecem no texto bruto (unicode-aware).
    Ignora acentos e case. Retorna de 0.0 a 1.0.
    """
    if not name or not raw_text:
        return 0.0

    name_norm = _strip_accents(name.lower())
    text_norm = _strip_accents(raw_text.lower())

    ignored = {"de", "da", "do", "dos", "das", "e", "di", "del", "jr", "sr", "neto"}
    tokens = [t for t in re.split(r"\s+", name_norm) if len(t) >= 3 and t not in ignored]
    if not tokens:
        return 0.0

    hits = 0
    for t in tokens:
        # Usar word boundary para evitar false positives em "maria" dentro de "marianas"
        if re.search(rf"\b{re.escape(t)}\b", text_norm):
            hits += 1
    return hits / len(tokens)


# ============================================================
# Localizacao brasileira (Cidade, UF / Cidade, Estado por extenso, Pais)
# ============================================================

_BR_STATE_NAME_TO_UF = {
    "acre": "AC",
    "alagoas": "AL",
    "amapa": "AP",
    "amazonas": "AM",
    "bahia": "BA",
    "ceara": "CE",
    "distrito federal": "DF",
    "espirito santo": "ES",
    "goias": "GO",
    "maranhao": "MA",
    "mato grosso": "MT",
    "mato grosso do sul": "MS",
    "minas gerais": "MG",
    "para": "PA",
    "paraiba": "PB",
    "parana": "PR",
    "pernambuco": "PE",
    "piaui": "PI",
    "rio de janeiro": "RJ",
    "rio grande do norte": "RN",
    "rio grande do sul": "RS",
    "rondonia": "RO",
    "roraima": "RR",
    "santa catarina": "SC",
    "sao paulo": "SP",
    "sergipe": "SE",
    "tocantins": "TO",
}

_BR_VALID_UFS = set(_BR_STATE_NAME_TO_UF.values())

_COUNTRY_NAMES = {
    "brasil", "brazil", "br", "portugal", "pt", "argentina", "chile", "uruguai",
    "uruguay", "paraguai", "paraguay", "estados unidos", "united states", "usa",
    "us", "canada", "canada", "mexico", "méxico", "espanha", "spain", "franca",
    "franca", "frança", "france", "alemanha", "germany", "italia", "italy", "italia",
    "reino unido", "united kingdom", "uk", "inglaterra", "england", "japao", "japan",
    "china", "india", "australia",
}


def _looks_like_country(token: str) -> bool:
    return _strip_accents(token.strip().lower()) in _COUNTRY_NAMES


def parse_brazilian_location(raw: Optional[str]) -> Optional[dict]:
    """
    Interpreta uma string de localizacao e devolve um dict normalizado.

    Aceita formatos comuns em curriculos/LinkedIn:
        - "Cidade, UF"
        - "Cidade - UF" / "Cidade/UF"
        - "Cidade, Estado por extenso, Pais" (ex: "Sao Leopoldo, Rio Grande do Sul, Brasil")
        - "Estado por extenso, Pais"
        - Apenas "Cidade" (sem UF)

    Retorna None se a entrada nao parece uma localizacao valida. Caso contrario:
        {
            "city": Optional[str],
            "state": Optional[str],       # sigla de 2 letras (UF) quando possivel
            "state_full": Optional[str],  # nome por extenso quando reconhecido
            "country": Optional[str],
            "display": str                # string canonica "Cidade, UF" ou "Cidade, UF, Pais"
        }
    """
    if not raw:
        return None

    text = re.sub(r"\s+", " ", str(raw)).strip(" \t\r\n.,;:-–—/")
    if not text or len(text) > 160:
        return None

    # Normaliza separadores alternativos para virgulas ("Cidade/UF", "Cidade - UF").
    normalized = re.sub(r"\s*[/]\s*", ", ", text)
    normalized = re.sub(r"\s*[-–—]\s*", ", ", normalized)
    segments = [seg.strip() for seg in normalized.split(",") if seg.strip()]
    if not segments:
        return None

    city: Optional[str] = None
    state: Optional[str] = None
    state_full: Optional[str] = None
    country: Optional[str] = None

    remaining = list(segments)

    # Pais geralmente vem por ultimo em exports do LinkedIn.
    if remaining and _looks_like_country(remaining[-1]):
        country = remaining.pop().strip()

    # Proximo candidato: estado (UF de 2 letras ou nome por extenso).
    if remaining:
        last = remaining[-1].strip()
        upper_only = re.fullmatch(r"[A-Za-z]{2}", last)
        if upper_only and last.upper() in _BR_VALID_UFS:
            state = last.upper()
            remaining.pop()
        else:
            key = _strip_accents(last.lower())
            if key in _BR_STATE_NAME_TO_UF:
                state = _BR_STATE_NAME_TO_UF[key]
                state_full = last.title()
                remaining.pop()

    # Exigimos ancora geografica (estado ou pais) para evitar capturar
    # listas de palavras aleatorias como "Python, Docker, AWS" ou
    # "Gestao, Lideranca, Agile" como se fossem localizacoes.
    if not state and not state_full and not country:
        return None

    # Apenas pais, sem cidade e sem estado, nao eh util para queries.
    if country and not state and not state_full and len(remaining) == 0:
        return None

    # Cidade: apenas o segmento mais proximo do estado (ultimo restante).
    # Isso descarta enderecos residuais como "Rua Foo 123" quando a linha
    # traz "Rua Foo 123, Curitiba, Parana, Brasil".
    if remaining:
        city_raw = remaining[-1].strip(" \t.-–—/")
        if city_raw and not _looks_like_country(city_raw):
            # Rejeita segmentos que sao claramente enderecos numericos
            # ou so dígitos/siglas.
            if not re.fullmatch(r"\d+", city_raw) and not re.fullmatch(r"[A-Z]{1,3}", city_raw):
                city = city_raw

    # Monta string canonica para display/armazenamento compativel com a UI.
    display_parts = []
    if city:
        display_parts.append(city)
    if state:
        display_parts.append(state)
    elif state_full:
        display_parts.append(state_full)
    if country and not display_parts:
        display_parts.append(country)
    display = ", ".join(display_parts)

    return {
        "city": city,
        "state": state,
        "state_full": state_full,
        "country": country,
        "display": display,
    }
