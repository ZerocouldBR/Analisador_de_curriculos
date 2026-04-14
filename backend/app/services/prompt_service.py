"""
Servico de gerenciamento de prompts do sistema

Carrega prompts do LLM e Chat a partir do banco de dados (DB overrides)
com fallback para os valores padrao definidos em config.py.

Usa cache em memoria com TTL de 60 segundos para evitar
consultas ao banco a cada request.
"""
import time
import logging
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)


class PromptService:
    """
    Servico centralizado para acesso a prompts e keywords de dominio.

    Prioridade: DB overrides > env vars > code defaults (via config.py)
    Cache TTL: 60 segundos
    """

    _cache: Dict = {}
    _cache_timestamp: float = 0
    _cache_ttl: int = 60  # seconds

    @classmethod
    def _is_cache_valid(cls) -> bool:
        """Verifica se o cache ainda e valido"""
        return (
            cls._cache
            and (time.time() - cls._cache_timestamp) < cls._cache_ttl
        )

    @classmethod
    def _load_overrides(cls, db: Session) -> Dict:
        """Carrega overrides do banco de dados"""
        try:
            from app.services.settings_service import SettingsService
            return SettingsService.get_system_config_overrides(db)
        except Exception as e:
            logger.warning(f"Erro ao carregar overrides do DB: {e}")
            return {}

    @classmethod
    def _get_effective_value(cls, key: str, overrides: Dict) -> str:
        """Retorna valor efetivo: DB override > config.py default"""
        if key in overrides:
            return overrides[key]
        return getattr(settings, key, "")

    @classmethod
    def _get_all_prompts(cls, db: Session) -> Dict:
        """Carrega todos os prompts com cache"""
        if cls._is_cache_valid():
            return cls._cache

        overrides = cls._load_overrides(db)

        cls._cache = {
            "llm_prompts": {
                "general": cls._get_effective_value("prompt_llm_general", overrides),
                "production": cls._get_effective_value("prompt_llm_production", overrides),
                "logistics": cls._get_effective_value("prompt_llm_logistics", overrides),
                "quality": cls._get_effective_value("prompt_llm_quality", overrides),
            },
            "chat_prompts": {
                "default": cls._get_effective_value("prompt_chat_default", overrides),
                "job_analysis": cls._get_effective_value("prompt_chat_job_analysis", overrides),
            },
            "domain_keywords": {
                "production": cls._get_effective_list("domain_keywords_production", overrides),
                "logistics": cls._get_effective_list("domain_keywords_logistics", overrides),
                "quality": cls._get_effective_list("domain_keywords_quality", overrides),
            },
        }
        cls._cache_timestamp = time.time()

        return cls._cache

    @classmethod
    def _get_effective_list(cls, key: str, overrides: Dict) -> List[str]:
        """Retorna lista efetiva: DB override > config.py default"""
        if key in overrides:
            val = overrides[key]
            if isinstance(val, list):
                return val
            if isinstance(val, str):
                return [x.strip() for x in val.split(",") if x.strip()]
        return getattr(settings, key, [])

    # ================================================================
    # API Publica
    # ================================================================

    @classmethod
    def get_llm_prompt(cls, db: Session, domain: str) -> str:
        """
        Retorna o prompt LLM para um dominio especifico.

        Args:
            db: Sessao do banco
            domain: "general", "production", "logistics" ou "quality"

        Returns:
            Texto do prompt
        """
        prompts = cls._get_all_prompts(db)
        return prompts["llm_prompts"].get(domain, prompts["llm_prompts"]["general"])

    @classmethod
    def get_llm_prompts(cls, db: Session) -> Dict[str, str]:
        """Retorna todos os prompts LLM"""
        prompts = cls._get_all_prompts(db)
        return prompts["llm_prompts"]

    @classmethod
    def get_chat_prompt(cls, db: Session, prompt_type: str = "default") -> str:
        """
        Retorna o prompt do chat.

        Args:
            db: Sessao do banco
            prompt_type: "default" ou "job_analysis"

        Returns:
            Texto do prompt
        """
        prompts = cls._get_all_prompts(db)
        return prompts["chat_prompts"].get(prompt_type, prompts["chat_prompts"]["default"])

    @classmethod
    def get_domain_keywords(cls, db: Session) -> Dict[str, List[str]]:
        """
        Retorna keywords de dominio para deteccao automatica.

        Returns:
            Dict com listas de keywords por dominio (production, logistics, quality)
        """
        prompts = cls._get_all_prompts(db)
        return prompts["domain_keywords"]

    @classmethod
    def invalidate_cache(cls):
        """Invalida o cache, forcando recarga na proxima consulta"""
        cls._cache = {}
        cls._cache_timestamp = 0
        logger.info("Cache de prompts invalidado")
