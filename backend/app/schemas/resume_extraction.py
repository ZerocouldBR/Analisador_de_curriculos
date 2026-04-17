"""
Schemas Pydantic para validacao da resposta de extracao de curriculo via IA.

Usado para validar o JSON retornado pelo LLM e garantir que toda a tabulacao
final seja coerente e tipada, evitando erros silenciosos causados por
respostas malformadas.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _StrictBase(BaseModel):
    """Base permissiva: ignora campos desconhecidos para nao quebrar
    quando o modelo adiciona campos novos."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class PersonalInfoSchema(_StrictBase):
    name: Optional[str] = None
    name_confidence: float = 0.0
    email: Optional[str] = None
    email_confidence: float = 0.0
    phone: Optional[str] = None
    phone_confidence: float = 0.0
    location: Optional[str] = None
    location_confidence: float = 0.0
    full_address: Optional[str] = None
    linkedin: Optional[str] = None
    linkedin_confidence: float = 0.0
    github: Optional[str] = None
    portfolio: Optional[str] = None
    birth_date: Optional[str] = None
    cpf: Optional[str] = None
    rg: Optional[str] = None
    has_photo: bool = False

    @field_validator(
        "name_confidence",
        "email_confidence",
        "phone_confidence",
        "location_confidence",
        "linkedin_confidence",
        mode="before",
    )
    @classmethod
    def _clamp_confidence(cls, v: Any) -> float:
        try:
            f = float(v) if v is not None else 0.0
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, f))


class ProfessionalObjectiveSchema(_StrictBase):
    title: Optional[str] = None
    summary: Optional[str] = None
    desired_position: Optional[str] = None
    desired_industries: List[str] = Field(default_factory=list)
    career_goals: Optional[str] = None
    confidence: float = 0.0

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp(cls, v: Any) -> float:
        try:
            f = float(v) if v is not None else 0.0
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, f))

    @field_validator("desired_industries", mode="before")
    @classmethod
    def _coerce_industries(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        if isinstance(v, list):
            return [str(x) for x in v if x]
        return []


class SalaryExpectationsSchema(_StrictBase):
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    currency: str = "BRL"
    period: str = "mensal"
    notes: Optional[str] = None
    confidence: float = 0.0

    @field_validator("minimum", "maximum", mode="before")
    @classmethod
    def _parse_money(cls, v: Any) -> Optional[float]:
        if v is None or v == "":
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            import re

            # remove R$, espacos, pontos de milhar; troca virgula por ponto
            cleaned = re.sub(r"[^0-9,.-]", "", v).replace(".", "").replace(",", ".")
            try:
                return float(cleaned) if cleaned else None
            except ValueError:
                return None
        return None

    @field_validator("currency", mode="before")
    @classmethod
    def _norm_currency(cls, v: Any) -> str:
        if not v:
            return "BRL"
        s = str(v).strip().upper()
        return s if s in {"BRL", "USD", "EUR", "GBP"} else "BRL"

    @field_validator("period", mode="before")
    @classmethod
    def _norm_period(cls, v: Any) -> str:
        if not v:
            return "mensal"
        s = str(v).strip().lower()
        if s in {"mensal", "monthly", "mes"}:
            return "mensal"
        if s in {"anual", "yearly", "ano"}:
            return "anual"
        if s in {"hora", "hourly", "por hora"}:
            return "hora"
        return "mensal"

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp(cls, v: Any) -> float:
        try:
            f = float(v) if v is not None else 0.0
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, f))


class ExperienceSchema(_StrictBase):
    company: Optional[str] = None
    title: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    achievements: List[str] = Field(default_factory=list)

    @field_validator("achievements", mode="before")
    @classmethod
    def _coerce_list(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        if isinstance(v, list):
            return [str(x) for x in v if x]
        return []


class EducationSchema(_StrictBase):
    institution: Optional[str] = None
    degree: Optional[str] = None
    field: Optional[str] = None
    start_year: Optional[str] = None
    end_year: Optional[str] = None
    status: Optional[str] = None


class SkillsSchema(_StrictBase):
    technical: List[str] = Field(default_factory=list)
    soft: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)


class LanguageSchema(_StrictBase):
    language: Optional[str] = None
    level: Optional[str] = None


class CertificationSchema(_StrictBase):
    name: Optional[str] = None
    institution: Optional[str] = None
    year: Optional[str] = None
    code: Optional[str] = None


class LicenseSchema(_StrictBase):
    type: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None


class AvailabilitySchema(_StrictBase):
    shifts: List[str] = Field(default_factory=list)
    travel: bool = False
    relocation: bool = False
    immediate_start: bool = False
    notice_period_days: Optional[int] = None
    work_mode: Optional[str] = None
    notes: Optional[str] = None


class AdditionalInfoSchema(_StrictBase):
    availability: AvailabilitySchema = Field(default_factory=AvailabilitySchema)
    equipment: List[Any] = Field(default_factory=list)
    erp_systems: List[Any] = Field(default_factory=list)
    safety_certifications: List[Any] = Field(default_factory=list)


class ResumeExtractionSchema(_StrictBase):
    """Schema completo da resposta da IA. Tudo e opcional para nao quebrar
    quando o currculo nao tem a secao - o validador posterior cuida da
    reconciliacao com o parser regex."""

    personal_info: PersonalInfoSchema = Field(default_factory=PersonalInfoSchema)
    professional_objective: ProfessionalObjectiveSchema = Field(
        default_factory=ProfessionalObjectiveSchema
    )
    salary_expectations: SalaryExpectationsSchema = Field(
        default_factory=SalaryExpectationsSchema
    )
    experiences: List[ExperienceSchema] = Field(default_factory=list)
    education: List[EducationSchema] = Field(default_factory=list)
    skills: SkillsSchema = Field(default_factory=SkillsSchema)
    languages: List[LanguageSchema] = Field(default_factory=list)
    certifications: List[CertificationSchema] = Field(default_factory=list)
    licenses: List[LicenseSchema] = Field(default_factory=list)
    additional_info: AdditionalInfoSchema = Field(default_factory=AdditionalInfoSchema)


def validate_ai_extraction(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Valida e normaliza o dict retornado pela IA.

    Retorna o dict serializado (model_dump) com defaults preenchidos.
    Nunca lanca: se a validacao falha, retorna o dict bruto para que o
    reconciliador downstream ainda tente reaproveitar.
    """
    try:
        parsed = ResumeExtractionSchema.model_validate(raw or {})
        return parsed.model_dump(mode="python")
    except Exception:  # noqa: BLE001
        return raw or {}
