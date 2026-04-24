"""
Modulo opcional de consultoria de carreira.

Quando a IA externa estiver indisponivel, sem chave ou com chave invalida,
este modulo nao deve quebrar a aba nem expor erro cru do provedor ao usuario.
Ele retorna uma consultoria local estruturada para manter a funcionalidade ativa.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.llm_client import llm_client

logger = logging.getLogger(__name__)

CAREER_ADVISORY_PROMPT = """Voce e um consultor de carreira sênior especializado em curriculos brasileiros.

Analise o curriculo abaixo e gere uma consultoria completa, construtiva e acionavel.

Responda APENAS com JSON valido no formato:
{{
  "overall_score": 75,
  "score_breakdown": {{
    "formatting": 80,
    "content_quality": 70,
    "keyword_optimization": 65,
    "professional_summary": 60,
    "experience_description": 75,
    "education_presentation": 80,
    "skills_presentation": 70
  }},
  "strengths": [{{"point": "descricao", "impact": "alto/medio/baixo"}}],
  "weaknesses": [{{"point": "descricao", "suggestion": "como melhorar", "priority": "alta/media/baixa"}}],
  "suggested_summary": "Resumo profissional reescrito em ate 4 linhas...",
  "suggested_keywords": ["palavra1", "palavra2"],
  "presentation_gaps": [{{"gap": "descricao", "importance": "alta/media/baixa"}}],
  "hr_recommendations": [{{"recommendation": "descricao", "context": "explicacao"}}],
  "candidate_tips": [{{"tip": "descricao", "category": "formatacao/conteudo/estrategia"}}],
  "suitable_areas": [{{"area": "nome da area", "fit_score": 85, "reasoning": "porque"}}],
  "improvement_priority": ["item1", "item2", "item3"]
}}

DADOS DO CURRICULO:
---
Nome: {name}
Cargo/Objetivo: {objective}
Resumo: {summary}
Experiencias: {experiences}
Formacao: {education}
Skills: {skills}
Idiomas: {languages}
Certificacoes: {certifications}
---
"""

_AUTH_ERROR_PATTERNS = (
    "invalid x-api-key",
    "authentication_error",
    "incorrect api key",
    "invalid api key",
    "401",
    "unauthorized",
    "api key nao configurada",
    "api key não configurada",
)


class CareerAdvisoryService:
    """Servico de consultoria de carreira com fallback local."""

    @staticmethod
    def _is_auth_error(error: Exception | str) -> bool:
        text = str(error).lower()
        return any(pattern in text for pattern in _AUTH_ERROR_PATTERNS)

    @staticmethod
    def _safe_error_message(error: Exception | str) -> str:
        if CareerAdvisoryService._is_auth_error(error):
            return (
                "Consultoria por IA indisponivel: chave do provedor LLM invalida "
                "ou nao configurada. A consultoria basica local foi gerada automaticamente."
            )
        return "Consultoria por IA indisponivel no momento. A consultoria basica local foi gerada automaticamente."

    @staticmethod
    def _extract_all_skills(resume_data: Dict[str, Any]) -> List[str]:
        skills = resume_data.get("skills", {}) or {}
        values: List[str] = []
        if isinstance(skills, dict):
            for key in ("technical", "soft", "tools", "frameworks"):
                raw = skills.get(key, []) or []
                values.extend(str(item).strip() for item in raw if str(item).strip())
        elif isinstance(skills, list):
            values.extend(str(item).strip() for item in skills if str(item).strip())
        seen = set()
        out = []
        for value in values:
            key = value.lower()
            if key not in seen:
                seen.add(key)
                out.append(value)
        return out

    @staticmethod
    def _format_resume_data(resume_data: Dict[str, Any]) -> Dict[str, str]:
        personal = resume_data.get("personal_info", {}) or {}
        professional = resume_data.get("professional_objective", {}) or {}
        experiences = resume_data.get("experiences", []) or []
        education = resume_data.get("education", []) or []
        languages = resume_data.get("languages", []) or []
        certifications = resume_data.get("certifications", []) or []

        exp_text = ""
        for exp in experiences:
            if isinstance(exp, dict):
                exp_text += (
                    f"- {exp.get('title') or exp.get('role') or 'N/A'} na "
                    f"{exp.get('company') or exp.get('company_name') or 'N/A'} "
                    f"({exp.get('start_date', '?')} a {exp.get('end_date', '?')})\n"
                    f"  {exp.get('description', '')}\n"
                )
        edu_text = ""
        for edu in education:
            if isinstance(edu, dict):
                edu_text += f"- {edu.get('degree', 'N/A')} - {edu.get('institution', 'N/A')} ({edu.get('end_year') or edu.get('year', '?')})\n"
        lang_text = ", ".join(
            f"{l.get('language', 'N/A')} ({l.get('level', 'N/A')})" for l in languages if isinstance(l, dict)
        )
        cert_text = ", ".join(c.get("name", "") if isinstance(c, dict) else str(c) for c in certifications if c)
        skills = CareerAdvisoryService._extract_all_skills(resume_data)

        return {
            "name": personal.get("name") or "Nao informado",
            "objective": professional.get("title") or professional.get("desired_position") or "Nao informado",
            "summary": professional.get("summary") or "Nao informado",
            "experiences": exp_text or "Nao informado",
            "education": edu_text or "Nao informado",
            "skills": ", ".join(skills) if skills else "Nao informado",
            "languages": lang_text or "Nao informado",
            "certifications": cert_text or "Nao informado",
        }

    @staticmethod
    async def generate_advisory(resume_data: Dict[str, Any], raw_text: str = "") -> Dict[str, Any]:
        """Gera consultoria por IA ou fallback local estruturado."""
        if not settings.active_llm_api_key:
            return {
                "available": True,
                "data": CareerAdvisoryService.generate_local_advisory(resume_data),
                "tokens_used": 0,
                "model_used": "local-heuristic",
                "fallback": True,
                "error": "LLM nao configurado. Consultoria basica local gerada.",
            }

        try:
            prompt = CAREER_ADVISORY_PROMPT.format(**CareerAdvisoryService._format_resume_data(resume_data))
            response = await llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": "Voce e um consultor de carreira. Responda APENAS com JSON valido, sem markdown."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
                max_tokens=4000,
            )
            raw = (response.content or "").strip()
            if raw.startswith("```"):
                raw = re.sub(r'^```(?:json)?\s*', '', raw)
                raw = re.sub(r'\s*```$', '', raw)
            advisory_data = CareerAdvisoryService._parse_json_robust(raw)
            if advisory_data is None:
                raise ValueError("Resposta da IA nao retornou JSON valido")
            return {
                "available": True,
                "data": advisory_data,
                "tokens_used": getattr(response, "tokens_used", 0) or 0,
                "model_used": getattr(response, "model", None) or settings.chat_model,
                "fallback": False,
            }
        except Exception as e:
            logger.warning("Consultoria IA indisponivel; fallback local acionado: %s", e)
            return {
                "available": True,
                "data": CareerAdvisoryService.generate_local_advisory(resume_data),
                "tokens_used": 0,
                "model_used": "local-heuristic",
                "fallback": True,
                "error": CareerAdvisoryService._safe_error_message(e),
            }

    @staticmethod
    def _parse_json_robust(raw: str) -> Optional[Dict[str, Any]]:
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass
        start = raw.find("{")
        if start < 0:
            return None
        depth = 0
        in_string = False
        escape = False
        for idx in range(start, len(raw)):
            char = raw[idx]
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(raw[start:idx + 1])
                        return parsed if isinstance(parsed, dict) else None
                    except json.JSONDecodeError:
                        return None
        return None

    @staticmethod
    def generate_local_advisory(resume_data: Dict[str, Any]) -> Dict[str, Any]:
        personal = resume_data.get("personal_info", {}) or {}
        professional = resume_data.get("professional_objective", {}) or {}
        experiences = resume_data.get("experiences", []) or []
        education = resume_data.get("education", []) or []
        languages = resume_data.get("languages", []) or []
        certifications = resume_data.get("certifications", []) or []
        skills = CareerAdvisoryService._extract_all_skills(resume_data)
        quick_tips = CareerAdvisoryService.generate_quick_tips(resume_data)

        summary = professional.get("summary") or ""
        score = 45
        score += 5 if personal.get("name") else 0
        score += 8 if personal.get("email") else 0
        score += 8 if personal.get("phone") else 0
        score += 6 if personal.get("linkedin") else 0
        score += 10 if len(summary) >= 80 else (5 if summary else 0)
        score += min(12, len(experiences) * 4)
        score += 5 if education else 0
        score += 10 if len(skills) >= 8 else (5 if skills else 0)
        score += 3 if languages else 0
        score += 3 if certifications else 0
        score = max(0, min(score, 100))

        strengths = []
        if professional.get("title"):
            strengths.append({"point": "Titulo/headline profissional identificado.", "impact": "medio"})
        if experiences:
            strengths.append({"point": "Historico profissional identificado para analise de trajetoria.", "impact": "alto"})
        if skills:
            strengths.append({"point": f"Foram identificadas {len(skills)} competencias/palavras-chave.", "impact": "medio"})
        if personal.get("linkedin"):
            strengths.append({"point": "Perfil LinkedIn informado para validacao profissional.", "impact": "medio"})
        if not strengths:
            strengths.append({"point": "Curriculo processado e disponivel para revisao inicial.", "impact": "baixo"})

        weaknesses = [
            {"point": t.get("tip", "Ponto de melhoria."), "suggestion": t.get("tip", "Revise este item."), "priority": t.get("priority", "media")}
            for t in quick_tips[:5]
        ] or [{"point": "Boa cobertura dos campos principais.", "suggestion": "Inclua metricas e resultados nas experiencias.", "priority": "baixa"}]

        name = personal.get("name") or "candidato"
        title = professional.get("title") or professional.get("desired_position") or "profissional"
        suggested_summary = (
            f"{name} e um {title} com experiencia alinhada ao perfil apresentado no curriculo. "
            "Recomenda-se destacar resultados mensuraveis, principais tecnologias/metodologias e impacto gerado."
        )

        keywords: List[str] = []
        for item in skills + [professional.get("title") or "", "gestao", "projetos", "resultados", "lideranca"]:
            value = str(item).strip()
            if value and value.lower() not in {k.lower() for k in keywords}:
                keywords.append(value)
            if len(keywords) >= 15:
                break

        return {
            "overall_score": score,
            "score_breakdown": {
                "formatting": 70,
                "content_quality": min(90, 45 + len(experiences) * 10 + (10 if summary else 0)),
                "keyword_optimization": min(90, 35 + len(skills) * 5),
                "professional_summary": 80 if len(summary) >= 80 else (55 if summary else 25),
                "experience_description": 80 if experiences else 25,
                "education_presentation": 75 if education else 35,
                "skills_presentation": 80 if len(skills) >= 8 else 45,
            },
            "strengths": strengths[:5],
            "weaknesses": weaknesses,
            "suggested_summary": suggested_summary,
            "suggested_keywords": keywords,
            "presentation_gaps": [{"gap": t.get("tip", "Melhoria de apresentacao"), "importance": t.get("priority", "media")} for t in quick_tips[:5]],
            "hr_recommendations": [
                {"recommendation": "Validar experiencias mais recentes e resultados entregues.", "context": "Consultoria local gerada porque a IA externa nao esta disponivel."},
                {"recommendation": "Conferir aderencia do cargo atual com a vaga-alvo.", "context": "Use headline, experiencias e skills extraidas para entrevista direcionada."},
            ],
            "candidate_tips": [{"tip": t.get("tip", "Revise o curriculo."), "category": t.get("category", "conteudo")} for t in quick_tips[:5]],
            "suitable_areas": [{"area": professional.get("title") or "Area compativel com as competencias extraidas", "fit_score": min(90, max(50, score)), "reasoning": "Estimativa local baseada em titulo, experiencias, competencias e certificacoes extraidas."}],
            "improvement_priority": [t.get("tip", "Revisar curriculo") for t in quick_tips[:3]] or ["Adicionar metricas nas experiencias", "Ajustar palavras-chave para a vaga-alvo", "Revisar clareza do resumo profissional"],
            "metadata": {"source": "local_heuristic_fallback", "llm_available": False},
        }

    @staticmethod
    def generate_quick_tips(resume_data: Dict[str, Any]) -> List[Dict[str, str]]:
        tips: List[Dict[str, str]] = []
        personal = resume_data.get("personal_info", {}) or {}
        professional = resume_data.get("professional_objective", {}) or {}
        experiences = resume_data.get("experiences", []) or []
        education = resume_data.get("education", []) or []
        languages = resume_data.get("languages", []) or []
        skills = CareerAdvisoryService._extract_all_skills(resume_data)

        summary = professional.get("summary")
        if not summary:
            tips.append({"tip": "Adicione um resumo profissional de 3-4 linhas no inicio do curriculo.", "category": "conteudo", "priority": "alta"})
        elif len(summary) < 50:
            tips.append({"tip": "Seu resumo profissional esta muito curto. Expanda para 3-4 linhas.", "category": "conteudo", "priority": "media"})
        if not personal.get("email"):
            tips.append({"tip": "Inclua um email profissional no curriculo.", "category": "contato", "priority": "alta"})
        if not personal.get("phone"):
            tips.append({"tip": "Inclua um numero de telefone atualizado.", "category": "contato", "priority": "alta"})
        if not personal.get("linkedin"):
            tips.append({"tip": "Adicione o link do seu perfil LinkedIn.", "category": "contato", "priority": "media"})
        if not experiences:
            tips.append({"tip": "Inclua suas experiencias profissionais com datas, cargos e descricoes.", "category": "conteudo", "priority": "alta"})
        else:
            for exp in experiences:
                if isinstance(exp, dict) and not exp.get("description"):
                    tips.append({"tip": f"Adicione descricao de atividades para a experiencia em '{exp.get('company', 'empresa')}'.", "category": "conteudo", "priority": "media"})
                    break
        if not education:
            tips.append({"tip": "Inclua sua formacao academica.", "category": "conteudo", "priority": "media"})
        if len(skills) < 5:
            tips.append({"tip": "Liste pelo menos 8-10 competencias tecnicas e comportamentais.", "category": "conteudo", "priority": "media"})
        if not languages:
            tips.append({"tip": "Inclua seus idiomas e niveis de proficiencia.", "category": "conteudo", "priority": "media"})
        return tips
