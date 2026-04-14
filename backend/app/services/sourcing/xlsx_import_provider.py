"""
Provider de sourcing para importacao de XLSX.

Le arquivos Excel (.xlsx) com mapeamento de colunas configuravel
e converte para CandidateCanonicalProfile.
"""
import logging
import os
from typing import Any, Dict, List, Optional

from app.services.sourcing.provider_base import (
    CandidateCanonicalProfile,
    ProviderHealthStatus,
    ProviderType,
    SourceProvider,
)
from app.services.sourcing.csv_import_provider import DEFAULT_COLUMN_MAP
from app.services.sourcing.provider_registry import ProviderRegistry

logger = logging.getLogger(__name__)


def _parse_xlsx_content(file_path: str, column_map: Dict[str, str]) -> List[CandidateCanonicalProfile]:
    """Parseia arquivo XLSX e retorna lista de perfis canonicos."""
    try:
        import openpyxl
    except ImportError:
        logger.error("openpyxl nao instalado. Execute: pip install openpyxl")
        return []

    if not os.path.exists(file_path):
        logger.error(f"XLSX file not found: {file_path}")
        return []

    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    ws = wb.active
    if ws is None:
        logger.error("XLSX: nenhuma planilha ativa encontrada")
        return []

    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        logger.warning("XLSX: arquivo sem dados (apenas cabecalho ou vazio)")
        return []

    headers = [str(h).strip().lower() if h else "" for h in rows[0]]
    profiles = []

    for row_num, row in enumerate(rows[1:], start=2):
        mapped = {}
        for col_idx, value in enumerate(row):
            if col_idx >= len(headers) or not headers[col_idx] or value is None:
                continue
            header = headers[col_idx]
            canonical_field = column_map.get(header)
            if canonical_field:
                mapped[canonical_field] = str(value).strip()

        if not mapped.get("full_name"):
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
            external_id=f"xlsx_row_{row_num}",
            confidence=0.6,
            raw_data={headers[i]: str(v) if v else "" for i, v in enumerate(row) if i < len(headers)},
        )
        profiles.append(profile)

    wb.close()
    return profiles


class XLSXImportProvider(SourceProvider):
    """Provider para importacao de candidatos via Excel (.xlsx)."""

    @property
    def provider_name(self) -> str:
        return "xlsx_import"

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.FILE

    async def health_check(self, config: Dict[str, Any]) -> ProviderHealthStatus:
        try:
            import openpyxl  # noqa: F401
            return ProviderHealthStatus(
                healthy=True,
                message="XLSX Import provider pronto para uso",
            )
        except ImportError:
            return ProviderHealthStatus(
                healthy=False,
                message="openpyxl nao instalado",
            )

    async def search_candidates(
        self,
        config: Dict[str, Any],
        criteria: Dict[str, Any],
        limit: int = 50,
    ) -> List[CandidateCanonicalProfile]:
        """Importa candidatos de um arquivo XLSX.

        config deve conter:
            - file_path: caminho do arquivo XLSX
            - column_map: (opcional) mapeamento customizado de colunas
        """
        file_path = config.get("file_path")
        if not file_path:
            logger.warning("XLSX: nenhum file_path fornecido")
            return []

        column_map = {**DEFAULT_COLUMN_MAP}
        if config.get("column_map"):
            column_map.update(config["column_map"])

        profiles = _parse_xlsx_content(file_path, column_map)
        return profiles[:limit]

    async def fetch_candidate_by_external_id(
        self,
        config: Dict[str, Any],
        external_id: str,
    ) -> Optional[CandidateCanonicalProfile]:
        return None


ProviderRegistry.register(XLSXImportProvider())
