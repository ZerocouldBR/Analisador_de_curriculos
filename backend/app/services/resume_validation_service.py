"""
Servico de validacao e scoring de confianca para dados de curriculos

Responsabilidades:
- Validar coerencia entre campos extraidos
- Detectar erros comuns (nome = endereco, email invalido, etc.)
- Calcular score de confianca por campo e geral
- Gerar alertas e sugestoes de correcao
"""
import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Indicadores de endereco brasileiro
ADDRESS_PATTERNS = [
    r'\b(?:rua|r\.)\s+\w',
    r'\b(?:avenida|av\.)\s+\w',
    r'\b(?:alameda|al\.)\s+\w',
    r'\b(?:travessa|tv\.)\s+\w',
    r'\b(?:praça|praca|pca\.)\s+\w',
    r'\b(?:estrada|estr\.)\s+\w',
    r'\b(?:rodovia|rod\.)\s+\w',
    r'\b(?:bairro)\s',
    r'\bCEP\b',
    r'\b\d{5}[-.]?\d{3}\b',
    r'\bnº?\s*\d+',
    r',\s*[A-Z]{2}\s*$',
    r'\b\d{2,}\b',
    r'\b(?:quadra|lote|bloco|conjunto|apt[o.]?|sala|andar)\b',
]

# Indicadores de competencia/titulo profissional - NUNCA podem ser nomes
COMPETENCY_PATTERNS = [
    r'\bgest[aã]o\s+d[eo]\b',
    r'\b(?:gerenciamento|administra[çc][aã]o)\s+d[eo]\b',
    r'\b(?:especialista|especializado)\s+em\b',
    r'\b(?:lideran[çc]a|coordena[çc][aã]o)\s+(?:de|em)\b',
    r'\b(?:desenvolvedor|desenvolvimento)\s+(?:de|em|web|mobile|backend|frontend)\b',
    r'\b(?:engenheiro|analista|gerente|diretor|coordenador|supervisor|operador|assistente)\s+(?:de|em)\b',
    r'\b(?:senior|junior|pleno)\s+(?:project|software|data|product)\b',
    r'\b(?:project|product|program)\s+manager\b',
    r'\b(?:active\s+directory|workspace\s+one|data\s+center)\b',
    r'\bsap\s+\w+\b',
]

# Preposicoes validas em nomes brasileiros
NAME_PREPOSITIONS = {'de', 'da', 'do', 'dos', 'das', 'e', 'di', 'del'}


class ResumeValidationService:
    """
    Valida e pontua a confiabilidade dos dados extraidos de curriculos.
    """

    @staticmethod
    def validate_resume_data(
        data: Dict[str, Any],
        raw_text: str = "",
        extraction_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executa validacao completa dos dados extraidos.

        Args:
            data: Dados extraidos do curriculo (formato enriquecido)
            raw_text: Texto bruto original para validacao cruzada
            extraction_metadata: Metadados da extracao (ex: ocr_confidence, pages_with_ocr).
                                 Usado para alertar sobre OCR com baixa confianca.

        Returns:
            Dict com dados validados, scores e alertas
        """
        personal = data.get("personal_info", {})
        alerts = []
        field_scores = {}

        # Alerta de OCR de baixa qualidade (afeta todos os dados extraidos)
        if extraction_metadata:
            ocr_conf = extraction_metadata.get("ocr_confidence")
            pages_with_ocr = extraction_metadata.get("pages_with_ocr", 0) or 0
            if ocr_conf is not None and pages_with_ocr > 0 and ocr_conf < 0.6:
                alerts.append({
                    "field": "document",
                    "type": "low_ocr_confidence",
                    "severity": "high" if ocr_conf < 0.4 else "medium",
                    "message": (
                        f"OCR com baixa confianca ({ocr_conf:.0%}) em {pages_with_ocr} "
                        "pagina(s). Dados extraidos podem conter erros - recomenda-se "
                        "revisao manual."
                    ),
                })

        # 1. Validar nome
        name_result = ResumeValidationService._validate_name_field(
            personal.get("name"), raw_text
        )
        field_scores["name"] = name_result["confidence"]
        if name_result.get("alert"):
            alerts.append(name_result["alert"])

        # 2. Validar email
        email_result = ResumeValidationService._validate_email_field(
            personal.get("email")
        )
        field_scores["email"] = email_result["confidence"]
        if email_result.get("alert"):
            alerts.append(email_result["alert"])

        # 3. Validar telefone
        phone_result = ResumeValidationService._validate_phone_field(
            personal.get("phone")
        )
        field_scores["phone"] = phone_result["confidence"]
        if phone_result.get("alert"):
            alerts.append(phone_result["alert"])

        # 3b. Validar LinkedIn
        linkedin_result = ResumeValidationService._validate_linkedin_field(
            personal.get("linkedin")
        )
        field_scores["linkedin"] = linkedin_result["confidence"]
        if linkedin_result.get("alert"):
            alerts.append(linkedin_result["alert"])

        # 4. Validar experiencias
        exp_result = ResumeValidationService._validate_experiences(
            data.get("experiences", [])
        )
        field_scores["experiences"] = exp_result["confidence"]
        alerts.extend(exp_result.get("alerts", []))

        # 5. Validar formacao
        edu_result = ResumeValidationService._validate_education(
            data.get("education", [])
        )
        field_scores["education"] = edu_result["confidence"]
        alerts.extend(edu_result.get("alerts", []))

        # 6. Validar skills
        skills = data.get("skills", {})
        if isinstance(skills, dict):
            all_skills = (
                skills.get("technical", []) +
                skills.get("soft", []) +
                skills.get("tools", []) +
                skills.get("frameworks", [])
            )
        elif isinstance(skills, list):
            all_skills = skills
        else:
            all_skills = []
        field_scores["skills"] = min(1.0, len(all_skills) * 0.1) if all_skills else 0.0

        # 7. Validar idiomas
        languages = data.get("languages", [])
        field_scores["languages"] = 0.9 if languages else 0.0

        # 8. Validar certificacoes
        certifications = data.get("certifications", [])
        field_scores["certifications"] = 0.9 if certifications else 0.0

        # 9. Validacao cruzada: coerencia entre campos
        cross_alerts = ResumeValidationService._cross_validate(data, raw_text)
        alerts.extend(cross_alerts)

        # Calcular score geral (agora inclui LinkedIn)
        weights = {
            "name": 0.22,
            "email": 0.13,
            "phone": 0.08,
            "linkedin": 0.05,
            "experiences": 0.20,
            "education": 0.10,
            "skills": 0.10,
            "languages": 0.05,
            "certifications": 0.07,
        }

        overall_score = sum(
            field_scores.get(field, 0) * weight
            for field, weight in weights.items()
        )

        # Classificar qualidade
        if overall_score >= 0.8:
            quality_label = "alta"
        elif overall_score >= 0.5:
            quality_label = "media"
        else:
            quality_label = "baixa"

        return {
            "overall_confidence": round(overall_score, 3),
            "quality_label": quality_label,
            "field_confidence": {k: round(v, 3) for k, v in field_scores.items()},
            "alerts": alerts,
            "alerts_count": len(alerts),
            "fields_extracted": sum(1 for v in field_scores.values() if v > 0),
            "total_fields": len(field_scores),
        }

    @staticmethod
    def _validate_name_field(name: Optional[str], raw_text: str) -> Dict[str, Any]:
        """Valida se o campo nome e realmente um nome de pessoa."""
        if not name:
            return {"confidence": 0.0, "alert": {
                "field": "name",
                "type": "missing",
                "severity": "high",
                "message": "Nome do candidato nao foi identificado.",
            }}

        name = name.strip()

        # Verificar se e um endereco
        name_lower = name.lower()
        for pattern in ADDRESS_PATTERNS:
            if re.search(pattern, name_lower, re.IGNORECASE):
                return {"confidence": 0.1, "alert": {
                    "field": "name",
                    "type": "address_as_name",
                    "severity": "critical",
                    "message": f"O nome '{name}' parece ser um endereco, nao um nome de pessoa.",
                    "suggestion": "Verifique o documento original e corrija manualmente.",
                }}

        # Verificar se e uma competencia/titulo
        for pattern in COMPETENCY_PATTERNS:
            if re.search(pattern, name, re.IGNORECASE):
                return {"confidence": 0.1, "alert": {
                    "field": "name",
                    "type": "competency_as_name",
                    "severity": "critical",
                    "message": f"O nome '{name}' parece ser uma competencia ou titulo profissional, nao um nome de pessoa.",
                    "suggestion": "Reprocesse o documento - o extrator confundiu competencias com nome.",
                }}

        # Verificar formato basico de nome
        words = name.split()
        if len(words) < 2:
            return {"confidence": 0.4, "alert": {
                "field": "name",
                "type": "incomplete",
                "severity": "medium",
                "message": f"Nome '{name}' parece incompleto (apenas uma palavra).",
                "suggestion": "Verifique se o nome completo foi extraido.",
            }}

        # Verificar se contem numeros
        if re.search(r'\d', name):
            return {"confidence": 0.2, "alert": {
                "field": "name",
                "type": "has_numbers",
                "severity": "high",
                "message": f"Nome '{name}' contem numeros - provavel erro de extracao.",
            }}

        # Verificar se contem caracteres invalidos
        if re.search(r'[@#$%&*!?/\\|{}[\]<>]', name):
            return {"confidence": 0.2, "alert": {
                "field": "name",
                "type": "invalid_chars",
                "severity": "high",
                "message": f"Nome '{name}' contem caracteres invalidos.",
            }}

        # Nome muito longo
        if len(words) > 8:
            return {"confidence": 0.5, "alert": {
                "field": "name",
                "type": "too_long",
                "severity": "low",
                "message": f"Nome com {len(words)} palavras pode conter informacoes extras.",
            }}

        # Verificar capitalizacao
        has_proper_caps = all(
            w[0].isupper() or w.lower() in NAME_PREPOSITIONS
            for w in words if w
        )

        if not has_proper_caps:
            return {"confidence": 0.6, "alert": {
                "field": "name",
                "type": "capitalization",
                "severity": "low",
                "message": f"Nome '{name}' tem capitalizacao inconsistente.",
            }}

        # Nome valido
        return {"confidence": 0.9}

    @staticmethod
    def _validate_email_field(email: Optional[str]) -> Dict[str, Any]:
        """Valida formato do email."""
        if not email:
            return {"confidence": 0.0}

        if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return {"confidence": 0.95}

        return {"confidence": 0.3, "alert": {
            "field": "email",
            "type": "invalid_format",
            "severity": "medium",
            "message": f"Email '{email}' tem formato invalido.",
        }}

    @staticmethod
    def _validate_phone_field(phone: Optional[str]) -> Dict[str, Any]:
        """Valida formato do telefone brasileiro."""
        if not phone:
            return {"confidence": 0.0}

        # Extrair apenas digitos
        digits = re.sub(r'\D', '', phone)

        if len(digits) >= 10 and len(digits) <= 13:
            return {"confidence": 0.9}

        return {"confidence": 0.5, "alert": {
            "field": "phone",
            "type": "unusual_format",
            "severity": "low",
            "message": f"Telefone '{phone}' tem formato incomum.",
        }}

    @staticmethod
    def _validate_linkedin_field(url: Optional[str]) -> Dict[str, Any]:
        """Valida URL do LinkedIn."""
        if not url:
            return {"confidence": 0.0}

        url_str = str(url).strip()
        if not url_str:
            return {"confidence": 0.0}

        # URL canonica com /in/
        if re.match(r'^https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/[\w\-_%]+', url_str, re.IGNORECASE):
            return {"confidence": 0.95}

        # URL com /pub/
        if re.match(r'^https?://(?:[a-z]{2,3}\.)?linkedin\.com/pub/[\w\-_%]+', url_str, re.IGNORECASE):
            return {"confidence": 0.85}

        # Parcial ou nao padrao
        if 'linkedin.com' in url_str.lower():
            return {"confidence": 0.5, "alert": {
                "field": "linkedin",
                "type": "partial_url",
                "severity": "low",
                "message": f"URL do LinkedIn '{url_str}' pode estar incompleta.",
            }}

        return {"confidence": 0.2, "alert": {
            "field": "linkedin",
            "type": "invalid_format",
            "severity": "medium",
            "message": f"URL do LinkedIn '{url_str}' tem formato invalido.",
        }}

    @staticmethod
    def _validate_experiences(experiences: list) -> Dict[str, Any]:
        """Valida lista de experiencias."""
        if not experiences:
            return {"confidence": 0.0, "alerts": []}

        alerts = []
        valid_count = 0

        for i, exp in enumerate(experiences):
            if isinstance(exp, dict):
                has_company = bool(exp.get("company"))
                has_title = bool(exp.get("title"))
                if has_company and has_title:
                    valid_count += 1
                elif has_company or has_title:
                    valid_count += 0.5
                    alerts.append({
                        "field": f"experiences[{i}]",
                        "type": "incomplete",
                        "severity": "low",
                        "message": f"Experiencia {i+1} incompleta: falta {'cargo' if not has_title else 'empresa'}.",
                    })

        confidence = min(1.0, (valid_count / max(len(experiences), 1)) * 0.9)
        return {"confidence": round(confidence, 2), "alerts": alerts}

    @staticmethod
    def _validate_education(education: list) -> Dict[str, Any]:
        """Valida lista de formacao."""
        if not education:
            return {"confidence": 0.0, "alerts": []}

        alerts = []
        valid_count = 0

        for i, edu in enumerate(education):
            if isinstance(edu, dict):
                has_institution = bool(edu.get("institution"))
                has_degree = bool(edu.get("degree"))
                if has_institution or has_degree:
                    valid_count += 1

        confidence = min(1.0, (valid_count / max(len(education), 1)) * 0.9)
        return {"confidence": round(confidence, 2), "alerts": alerts}

    @staticmethod
    def _cross_validate(data: Dict[str, Any], raw_text: str) -> List[Dict]:
        """Validacao cruzada entre campos para detectar inconsistencias."""
        alerts = []
        personal = data.get("personal_info", {})
        name = personal.get("name", "")
        email = personal.get("email", "")
        location = personal.get("location", "")

        # Verificar se nome aparece no texto bruto (fuzzy match unicode-aware)
        if name and raw_text:
            from app.services.brazilian_validators import (
                name_appears_in_text,
                name_email_match_ratio,
            )
            ratio = name_appears_in_text(name, raw_text)
            if ratio < 0.5:
                alerts.append({
                    "field": "name",
                    "type": "not_in_text",
                    "severity": "medium" if ratio < 0.25 else "low",
                    "message": (
                        f"Nome extraido '{name}' tem baixa correspondencia "
                        f"com o texto original ({ratio:.0%} dos tokens encontrados)."
                    ),
                })

            # Cross-validate nome vs email prefix
            if email:
                email_ratio = name_email_match_ratio(name, email)
                if email_ratio < 0.3:
                    alerts.append({
                        "field": "name",
                        "type": "mismatch_with_email",
                        "severity": "medium",
                        "message": (
                            f"Nome '{name}' tem baixa sobreposicao com o email "
                            f"'{email}' ({email_ratio:.0%}). Verifique se o nome esta correto."
                        ),
                    })

        # Verificar se email aparece no texto bruto (case-insensitive + trim)
        if email and raw_text and email.lower().strip() not in raw_text.lower():
            alerts.append({
                "field": "email",
                "type": "not_in_text",
                "severity": "low",
                "message": "Email extraido nao encontrado no texto original.",
            })

        # Validar CPF com checksum mod 11
        cpf = personal.get("cpf")
        if cpf:
            from app.services.brazilian_validators import is_valid_cpf
            if not is_valid_cpf(cpf):
                alerts.append({
                    "field": "cpf",
                    "type": "invalid_checksum",
                    "severity": "high",
                    "message": f"CPF '{cpf}' nao passa na validacao de checksum (mod 11).",
                })

        # Verificar se localizacao foi extraida como nome
        if name and location and name.lower() == location.lower():
            alerts.append({
                "field": "name",
                "type": "same_as_location",
                "severity": "critical",
                "message": "Nome e localizacao sao identicos - provavel erro de extracao.",
            })

        # Verificar experiencias sem datas
        experiences = data.get("experiences", [])
        for i, exp in enumerate(experiences):
            if isinstance(exp, dict) and not exp.get("start_date"):
                alerts.append({
                    "field": f"experiences[{i}]",
                    "type": "no_dates",
                    "severity": "low",
                    "message": f"Experiencia '{exp.get('company', 'N/A')}' sem datas.",
                })

        return alerts
