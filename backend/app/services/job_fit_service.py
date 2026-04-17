"""
Servico de analise de fit entre curriculo e vaga.

Usa o LLM para comparar dados enriquecidos do candidato contra
a descricao/requisitos da vaga, gerando:
- score numerico 0-100
- resumo textual
- pontos fortes vs vaga
- gaps (o que falta)
- skills matched/missing
- recomendacao (strong_match / good_match / weak_match / no_match)
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.llm_client import llm_client

logger = logging.getLogger(__name__)


FIT_ANALYSIS_PROMPT = """Voce e um recrutador senior especializado em analise de fit
entre candidatos e vagas.

Compare o CURRICULO do candidato com a DESCRICAO DA VAGA e produza uma analise
quantitativa e qualitativa.

REGRAS:
1. O "score" (0-100) deve refletir objetivamente o quanto o candidato atende
   aos requisitos da vaga: experiencia relevante, skills tecnicas, senioridade,
   formacao, localizacao, etc.
   - 90-100: match excelente, candidato ideal
   - 75-89: bom match, pequenas lacunas
   - 50-74: match parcial, gaps significativos
   - 25-49: match fraco, poucos pontos em comum
   - 0-24: sem fit para a vaga
2. Liste skills explicitamente pedidas na vaga que o candidato POSSUI
   (matched_skills) e que NAO possui (missing_skills).
3. Gere strengths (3-5 frases) com pontos em que o candidato se destaca para
   ESTA vaga especifica.
4. Gere gaps (2-4 frases) com lacunas claras em relacao ao que a vaga pede.
5. Em experience_match, comente brevemente se o tempo/tipo de experiencia
   e compativel com o nivel de senioridade pedido.
6. Em recommendation, use exatamente um dos valores:
   "strong_match", "good_match", "weak_match", "no_match".
7. Responda APENAS com JSON valido, sem markdown.

FORMATO DE RESPOSTA:
{{
  "score": 82,
  "summary": "Resumo em 1-2 frases do fit geral",
  "strengths": ["Ponto forte 1", "Ponto forte 2"],
  "gaps": ["Gap 1", "Gap 2"],
  "matched_skills": ["python", "aws"],
  "missing_skills": ["kubernetes"],
  "experience_match": "Candidato tem 7 anos de experiencia, vaga pede 5+",
  "recommendation": "good_match"
}}

VAGA:
Titulo: {job_title}
Senioridade: {seniority}
Modo de trabalho: {work_mode}
Localizacao: {location}
Skills exigidas: {skills_required}
Skills desejaveis: {skills_desired}

Descricao:
{job_description}

Requisitos:
{job_requirements}

CURRICULO DO CANDIDATO (dados estruturados):
---
{candidate_profile}
---

Responda SOMENTE com o JSON valido:"""


class JobFitService:
    """Analisa o fit de um candidato com uma vaga."""

    @staticmethod
    async def analyze_fit(
        job: Dict[str, Any],
        candidate_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Executa a analise via LLM.

        Args:
            job: dict com title, description, requirements, skills_required, etc.
            candidate_profile: dict enriquecido (vindo de CandidateProfile ou
                               EnrichmentPipeline). Pode ser o proprio JSON salvo.

        Returns:
            Dict com ai_available, data, tokens_used, error (quando houver).
        """
        if not settings.active_llm_api_key:
            logger.warning("LLM API key nao configurada - fit analysis indisponivel")
            return {"ai_available": False, "data": None}

        try:
            profile_str = JobFitService._serialize_candidate_profile(candidate_profile)

            prompt = FIT_ANALYSIS_PROMPT.format(
                job_title=job.get("title", ""),
                seniority=job.get("seniority_level", "nao especificado"),
                work_mode=job.get("work_mode", "nao especificado"),
                location=job.get("location", "nao especificado"),
                skills_required=", ".join(job.get("skills_required", []) or []) or "nao especificado",
                skills_desired=", ".join(job.get("skills_desired", []) or []) or "nao especificado",
                job_description=(job.get("description") or "")[:6000],
                job_requirements=(job.get("requirements") or "")[:3000],
                candidate_profile=profile_str[:10000],
            )

            response = await llm_client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Voce e um especialista em fit de candidatos. "
                            "Responda APENAS com JSON valido, sem markdown."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=2000,
            )

            raw = (response.content or "").strip()
            if raw.startswith("```"):
                raw = re.sub(r'^```(?:json)?\s*', '', raw)
                raw = re.sub(r'\s*```$', '', raw)

            data = JobFitService._robust_json_parse(raw)
            if data is None:
                return {"ai_available": True, "data": None, "error": "JSON invalido"}

            # Garantir tipos esperados
            data["score"] = int(data.get("score", 0) or 0)
            data["score"] = max(0, min(100, data["score"]))
            data.setdefault("summary", "")
            data.setdefault("strengths", [])
            data.setdefault("gaps", [])
            data.setdefault("matched_skills", [])
            data.setdefault("missing_skills", [])
            data.setdefault("experience_match", None)
            if data.get("recommendation") not in {
                "strong_match", "good_match", "weak_match", "no_match"
            }:
                data["recommendation"] = JobFitService._infer_recommendation(data["score"])

            return {
                "ai_available": True,
                "data": data,
                "tokens_used": getattr(response, "tokens_used", 0) or 0,
                "model_used": getattr(response, "model", None) or settings.chat_model,
            }

        except Exception as e:
            logger.error(f"Erro na analise de fit: {e}", exc_info=True)
            return {"ai_available": True, "data": None, "error": str(e)}

    @staticmethod
    def _serialize_candidate_profile(profile: Dict[str, Any]) -> str:
        """Serializa o perfil de forma compacta para caber no prompt."""
        try:
            # Se veio no formato enriquecido (com "data"), desembrulha
            if isinstance(profile, dict) and "data" in profile and isinstance(profile["data"], dict):
                profile = profile["data"]

            simplified: Dict[str, Any] = {}
            if "personal_info" in profile:
                pi = profile["personal_info"]
                simplified["personal"] = {
                    "name": pi.get("name"),
                    "location": pi.get("location"),
                }
            if "professional_objective" in profile:
                po = profile["professional_objective"] or {}
                simplified["title"] = po.get("title")
                simplified["summary"] = po.get("summary")
            if "experiences" in profile:
                exps = profile["experiences"] or []
                simplified["experiences"] = [
                    {
                        "company": e.get("company"),
                        "title": e.get("title"),
                        "start_date": e.get("start_date"),
                        "end_date": e.get("end_date"),
                        "description": (e.get("description") or "")[:500],
                    }
                    for e in exps[:10] if isinstance(e, dict)
                ]
            if "education" in profile:
                simplified["education"] = profile["education"][:5]
            if "skills" in profile:
                simplified["skills"] = profile["skills"]
            if "languages" in profile:
                simplified["languages"] = profile["languages"]
            if "certifications" in profile:
                simplified["certifications"] = [
                    c.get("name") if isinstance(c, dict) else str(c)
                    for c in (profile["certifications"] or [])
                ][:15]

            return json.dumps(simplified, ensure_ascii=False)
        except Exception:
            return json.dumps(profile, ensure_ascii=False, default=str)

    @staticmethod
    def _robust_json_parse(raw: str) -> Optional[Dict[str, Any]]:
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        start = raw.find('{')
        if start == -1:
            return None
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(raw)):
            ch = raw[i]
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(raw[start:i + 1])
                    except json.JSONDecodeError:
                        return None
        return None

    @staticmethod
    def _infer_recommendation(score: int) -> str:
        if score >= 80:
            return "strong_match"
        if score >= 60:
            return "good_match"
        if score >= 35:
            return "weak_match"
        return "no_match"
