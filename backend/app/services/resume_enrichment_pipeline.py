"""
Pipeline de enriquecimento de curriculos

Orquestra as etapas de:
1. Extracao por regex (ResumeParserService)
2. Extracao por IA (ResumeAIExtractionService)
3. Validacao e reconciliacao (ResumeAIExtractionService.validate_extraction)
4. Scoring de confianca (ResumeValidationService)
5. Consultoria de carreira opcional (CareerAdvisoryService)

Retorna estrutura enriquecida padronizada para o frontend.
"""
import logging
import asyncio
from typing import Dict, Any, Optional

from app.services.resume_parser_service import ResumeParserService
from app.services.resume_ai_extraction_service import ResumeAIExtractionService
from app.services.resume_validation_service import ResumeValidationService
from app.services.career_advisory_service import CareerAdvisoryService

logger = logging.getLogger(__name__)


class ResumeEnrichmentPipeline:
    """
    Pipeline completo de extracao, validacao e enriquecimento de curriculos.
    """

    @staticmethod
    async def process(
        text: str,
        enable_ai: bool = True,
        enable_career_advisory: bool = False,
        extraction_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executa pipeline completo de processamento.

        Args:
            text: Texto bruto do curriculo
            enable_ai: Habilitar extracao por IA (requer OpenAI API key)
            enable_career_advisory: Habilitar modulo de consultoria
            extraction_metadata: Metadados da extracao (ex: ocr_confidence,
                                 pages_with_ocr). Usado para alertar sobre OCR ruim.

        Returns:
            Dict com dados enriquecidos, validacao e metadados
        """
        result = {
            "extraction_method": "regex",
            "ai_enhanced": False,
            "career_advisory": None,
            "data": {},
            "validation": {},
            "metadata": {},
        }

        # ETAPA 1: Extracao por regex (sempre executa, e rapida)
        logger.info("Pipeline: Etapa 1 - Extracao por regex")
        regex_data = ResumeParserService.parse_resume(text)

        # ETAPA 2: Extracao por IA (se habilitado)
        ai_result = None
        if enable_ai:
            logger.info("Pipeline: Etapa 2 - Extracao por IA")
            try:
                ai_result = await ResumeAIExtractionService.extract_with_ai(
                    text, regex_data
                )
            except Exception as e:
                logger.error(f"Pipeline: Erro na extracao por IA: {e}")
                ai_result = {"ai_available": False, "data": None, "error": str(e)}

        # ETAPA 3: Validacao e reconciliacao
        logger.info("Pipeline: Etapa 3 - Validacao e reconciliacao")
        if ai_result and ai_result.get("ai_available") and ai_result.get("data"):
            validated = await ResumeAIExtractionService.validate_extraction(
                regex_data, ai_result, text
            )
            result["extraction_method"] = "ai_validated"
            result["ai_enhanced"] = True
            enriched_data = validated["data"]
            result["metadata"]["ai_model"] = ai_result.get("model_used")
            result["metadata"]["ai_tokens"] = ai_result.get("tokens_used", 0)
            result["metadata"]["validation_notes"] = validated.get("validation_notes", [])
        else:
            # Fallback: converter dados do regex para formato enriquecido
            enriched_data = ResumeEnrichmentPipeline._convert_regex_to_enriched(regex_data)
            result["extraction_method"] = "regex_only"
            if ai_result and ai_result.get("error"):
                result["metadata"]["ai_error"] = ai_result["error"]

        result["data"] = enriched_data

        # ETAPA 4: Scoring de confianca (considerando metadata de OCR)
        logger.info("Pipeline: Etapa 4 - Scoring de confianca")
        validation = ResumeValidationService.validate_resume_data(
            enriched_data, text, extraction_metadata=extraction_metadata,
        )
        result["validation"] = validation
        if extraction_metadata:
            result["metadata"]["extraction"] = {
                k: v for k, v in extraction_metadata.items()
                if k in {"ocr_confidence", "pages_with_ocr", "pages_with_text",
                         "pages_processed", "language", "extraction_method"}
            }

        # ETAPA 5: Consultoria de carreira (opcional)
        if enable_career_advisory:
            logger.info("Pipeline: Etapa 5 - Consultoria de carreira")
            try:
                advisory = await CareerAdvisoryService.generate_advisory(
                    enriched_data, text
                )
                if advisory.get("available") and advisory.get("data"):
                    result["career_advisory"] = advisory["data"]
                    result["metadata"]["advisory_tokens"] = advisory.get("tokens_used", 0)
                else:
                    # Gerar dicas rapidas por heuristica
                    quick_tips = CareerAdvisoryService.generate_quick_tips(enriched_data)
                    result["career_advisory"] = {"quick_tips": quick_tips}
            except Exception as e:
                logger.error(f"Pipeline: Erro na consultoria: {e}")
                quick_tips = CareerAdvisoryService.generate_quick_tips(enriched_data)
                result["career_advisory"] = {"quick_tips": quick_tips}

        # Estruturar resposta final
        result["metadata"]["fields_extracted"] = validation.get("fields_extracted", 0)
        result["metadata"]["overall_confidence"] = validation.get("overall_confidence", 0)
        result["metadata"]["quality_label"] = validation.get("quality_label", "desconhecido")

        return result

    @staticmethod
    def process_sync_with_metadata(
        text: str,
        extraction_metadata: Optional[Dict[str, Any]] = None,
        enable_ai: bool = True,
        enable_career_advisory: bool = False,
    ) -> Dict[str, Any]:
        """Versao sync que aceita extraction_metadata (para uso em Celery)."""
        return ResumeEnrichmentPipeline._run_sync(
            text=text,
            enable_ai=enable_ai,
            enable_career_advisory=enable_career_advisory,
            extraction_metadata=extraction_metadata,
        )

    @staticmethod
    def _run_sync(
        text: str,
        enable_ai: bool = True,
        enable_career_advisory: bool = False,
        extraction_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Invoca process() de forma sincrona (Celery-friendly)."""
        coro_kwargs = dict(
            text=text,
            enable_ai=enable_ai,
            enable_career_advisory=enable_career_advisory,
            extraction_metadata=extraction_metadata,
        )
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        ResumeEnrichmentPipeline.process(**coro_kwargs),
                    )
                    return future.result(timeout=120)
            return loop.run_until_complete(
                ResumeEnrichmentPipeline.process(**coro_kwargs)
            )
        except RuntimeError:
            return asyncio.run(
                ResumeEnrichmentPipeline.process(**coro_kwargs)
            )

    @staticmethod
    def process_sync(
        text: str,
        enable_ai: bool = True,
        enable_career_advisory: bool = False,
    ) -> Dict[str, Any]:
        """
        Versao sincrona do pipeline (para uso em Celery tasks).
        Retrocompativel - sem extraction_metadata.
        """
        return ResumeEnrichmentPipeline._run_sync(
            text=text,
            enable_ai=enable_ai,
            enable_career_advisory=enable_career_advisory,
            extraction_metadata=None,
        )

    @staticmethod
    def _convert_regex_to_enriched(regex_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Converte dados do parser regex para o formato enriquecido padronizado.
        """
        personal = regex_data.get("personal_info", {})

        # Converter skills de lista para dict categorizado
        raw_skills = regex_data.get("skills", [])
        skills_dict = {
            "technical": raw_skills,
            "soft": [],
            "tools": [],
            "frameworks": [],
        }

        # Converter certifications de lista de strings para lista de dicts
        raw_certs = regex_data.get("certifications", [])
        cert_list = []
        for cert in raw_certs:
            if isinstance(cert, str):
                cert_list.append({"name": cert, "institution": None, "year": None, "code": None})
            elif isinstance(cert, dict):
                cert_list.append(cert)

        # Converter education para formato padronizado
        raw_edu = regex_data.get("education", [])
        edu_list = []
        for edu in raw_edu:
            if isinstance(edu, dict):
                edu_list.append({
                    "institution": edu.get("institution"),
                    "degree": edu.get("degree"),
                    "field": None,
                    "start_year": None,
                    "end_year": edu.get("year"),
                    "status": None,
                })

        # Converter licenses
        raw_licenses = regex_data.get("licenses", [])

        return {
            "personal_info": {
                "name": personal.get("name"),
                "name_confidence": 0.7 if personal.get("name") else 0.0,
                "email": personal.get("email"),
                "email_confidence": 0.9 if personal.get("email") else 0.0,
                "phone": personal.get("phone"),
                "phone_confidence": 0.85 if personal.get("phone") else 0.0,
                "location": personal.get("location"),
                "location_confidence": 0.7 if personal.get("location") else 0.0,
                "full_address": None,
                "linkedin": personal.get("linkedin"),
                "github": personal.get("github"),
                "portfolio": None,
                "cpf": personal.get("cpf"),
                "rg": personal.get("rg"),
                "birth_date": personal.get("birth_date"),
            },
            "professional_objective": {
                "title": None,
                "summary": regex_data.get("summary"),
                "confidence": 0.6 if regex_data.get("summary") else 0.0,
            },
            "experiences": regex_data.get("experiences", []),
            "education": edu_list,
            "skills": skills_dict,
            "languages": regex_data.get("languages", []),
            "certifications": cert_list,
            "licenses": raw_licenses,
            "additional_info": {
                "availability": regex_data.get("availability", {}),
                "equipment": regex_data.get("equipment", []),
                "erp_systems": regex_data.get("erp_systems", []),
                "safety_certifications": regex_data.get("safety_certs", []),
            },
        }
