"""
Provider de sourcing para importacao de CSV.

Le arquivos CSV com mapeamento de colunas configuravel
e converte para CandidateCanonicalProfile.
"""
import csv
import io
import logging
import os
from typing import Any, Dict, List, Optional

from app.services.sourcing.provider_base import (
    CandidateCanonicalProfile,
    ProviderHealthStatus,
    ProviderType,
    SourceProvider,
)
from app.services.sourcing.provider_registry import ProviderRegistry

logger = logging.getLogger(__name__)

# Mapeamento padrao de colunas CSV -> campos canonicos
DEFAULT_COLUMN_MAP = {
    "nome": "full_name",
    "name": "full_name",
    "full_name": "full_name",
    "nome_completo": "full_name",
    "email": "email",
    "e-mail": "email",
    "telefone": "phone",
    "phone": "phone",
    "celular": "phone",
    "cidade": "city",
    "city": "city",
    "estado": "state",
    "state": "state",
    "uf": "state",
    "pais": "country",
    "country": "country",
    "cargo": "current_role",
    "titulo": "current_role",
    "title": "current_role",
    "current_role": "current_role",
    "empresa": "current_company",
    "company": "current_company",
    "current_company": "current_company",
    "linkedin": "linkedin_url",
    "linkedin_url": "linkedin_url",
    "github": "github_url",
    "github_url": "github_url",
    "portfolio": "portfolio_url",
    "portfolio_url": "portfolio_url",
    "headline": "headline",
    "resumo": "about",
    "about": "about",
    "summary": "about",
    "skills": "skills",
    "habilidades": "skills",
    "senioridade": "seniority",
    "seniority": "seniority",
}


def _parse_csv_content(content: str, column_map: Dict[str, str]) -> List[CandidateCanonicalProfile]:
    """Parseia conteudo CSV e retorna lista de perfis canonicos."""
    reader = csv.DictReader(io.StringIO(content))
    profiles = []

    for row_num, row in enumerate(reader, start=1):
        mapped = {}
        for csv_col, value in row.items():
            if not csv_col or not value:
                continue
            csv_col_lower = csv_col.strip().lower()
            canonical_field = column_map.get(csv_col_lower)
            if canonical_field:
                mapped[canonical_field] = value.strip()

        if not mapped.get("full_name"):
            logger.warning(f"CSV linha {row_num}: sem nome, ignorando")
            continue

        skills = []
        if mapped.get("skills"):
            skills = [s.strip() for s in mapped["skills"].split(",") if s.strip()]

        profile = CandidateCanonicalProfile(
            full_name=mapped["full_name"],
            email=mapped.get("email"),
            phone=mapped.get("phone"),
            city=mapped.get("city"),
            state=mapped.get("state"),
            country=mapped.get("country", "Brasil"),
            linkedin_url=mapped.get("linkedin_url"),
            github_url=mapped.get("github_url"),
            portfolio_url=mapped.get("portfolio_url"),
            current_company=mapped.get("current_company"),
            current_role=mapped.get("current_role"),
            seniority=mapped.get("seniority"),
            headline=mapped.get("headline"),
            about=mapped.get("about"),
            skills=skills,
            external_id=f"csv_row_{row_num}",
            confidence=0.6,
            raw_data=dict(row),
        )
        profiles.append(profile)

    return profiles


class CSVImportProvider(SourceProvider):
    """Provider para importacao de candidatos via CSV."""

    @property
    def provider_name(self) -> str:
        return "csv_import"

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.FILE

    async def health_check(self, config: Dict[str, Any]) -> ProviderHealthStatus:
        """Verifica se o provider esta operacional."""
        return ProviderHealthStatus(
            healthy=True,
            message="CSV Import provider pronto para uso",
        )

    async def search_candidates(
        self,
        config: Dict[str, Any],
        criteria: Dict[str, Any],
        limit: int = 50,
    ) -> List[CandidateCanonicalProfile]:
        """Importa candidatos de um arquivo CSV.

        config deve conter:
            - file_path: caminho do arquivo CSV, OU
            - file_content: conteudo CSV como string
            - column_map: (opcional) mapeamento customizado de colunas
        """
        column_map = {**DEFAULT_COLUMN_MAP}
        if config.get("column_map"):
            column_map.update(config["column_map"])

        content = config.get("file_content")
        if not content and config.get("file_path"):
            file_path = config["file_path"]
            if not os.path.exists(file_path):
                logger.error(f"CSV file not found: {file_path}")
                return []
            with open(file_path, "r", encoding="utf-8-sig") as f:
                content = f.read()

        if not content:
            logger.warning("CSV: nenhum conteudo fornecido")
            return []

        profiles = _parse_csv_content(content, column_map)
        return profiles[:limit]

    async def fetch_candidate_by_external_id(
        self,
        config: Dict[str, Any],
        external_id: str,
    ) -> Optional[CandidateCanonicalProfile]:
        """Nao suportado para CSV (dados nao persistem na fonte)."""
        return None

    def normalize_candidate(self, raw_data: Dict[str, Any]) -> CandidateCanonicalProfile:
        column_map = {**DEFAULT_COLUMN_MAP}
        profiles = _parse_csv_content("", column_map)
        return profiles[0] if profiles else CandidateCanonicalProfile(full_name="N/A")


ProviderRegistry.register(CSVImportProvider())
