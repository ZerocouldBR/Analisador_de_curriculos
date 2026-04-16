"""
Modulo opcional de consultoria de carreira

Funcionalidades:
- Analise de pontos fortes e fracos do curriculo
- Sugestoes de melhorias no curriculo
- Reescrita de resumo profissional
- Sugestoes de palavras-chave para recrutamento
- Identificacao de gaps de apresentacao
- Recomendacoes para RH e candidatos

Este modulo e INDEPENDENTE do fluxo principal de extracao.
Pode ser habilitado/desabilitado via configuracao.
"""
import json
import logging
import re
from typing import Dict, Any, Optional, List

from app.core.config import settings
from app.services.llm_client import llm_client

logger = logging.getLogger(__name__)

CAREER_ADVISORY_PROMPT = """Voce e um consultor de carreira sênior especializado em curriculos brasileiros.

Analise o curriculo abaixo e forneca uma consultoria completa com:

1. **PONTUACAO GERAL** (0-100): Avalie a qualidade geral do curriculo
2. **PONTOS FORTES**: Liste 3-5 pontos positivos do curriculo
3. **PONTOS FRACOS**: Liste 3-5 areas que precisam de melhoria
4. **SUGESTOES DE MELHORIA**: Para cada ponto fraco, forneca uma sugestao pratica
5. **RESUMO PROFISSIONAL SUGERIDO**: Reescreva o resumo profissional de forma mais impactante (max 4 linhas)
6. **PALAVRAS-CHAVE SUGERIDAS**: Liste 10-15 palavras-chave que deveriam estar no curriculo para melhorar a visibilidade em recrutamento
7. **GAPS DE APRESENTACAO**: Identifique informacoes que estao faltando ou mal apresentadas
8. **RECOMENDACOES PARA RH**: O que o RH deve observar ao analisar este candidato
9. **DICAS PARA O CANDIDATO**: 3-5 dicas praticas para melhorar a apresentacao
10. **ADEQUACAO POR AREA**: Para quais areas/cargos este curriculo e mais adequado

IMPORTANTE: Seja construtivo e pratico. Foque em melhorias acionaveis.

Responda APENAS com JSON valido:
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
  "strengths": [
    {{"point": "descricao", "impact": "alto/medio/baixo"}}
  ],
  "weaknesses": [
    {{"point": "descricao", "suggestion": "como melhorar", "priority": "alta/media/baixa"}}
  ],
  "suggested_summary": "Resumo profissional reescrito...",
  "suggested_keywords": ["palavra1", "palavra2"],
  "presentation_gaps": [
    {{"gap": "descricao", "importance": "alta/media/baixa"}}
  ],
  "hr_recommendations": [
    {{"recommendation": "descricao", "context": "explicacao"}}
  ],
  "candidate_tips": [
    {{"tip": "descricao", "category": "formatacao/conteudo/estrategia"}}
  ],
  "suitable_areas": [
    {{"area": "nome da area", "fit_score": 85, "reasoning": "porque"}}
  ],
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

Responda SOMENTE com JSON valido:"""


class CareerAdvisoryService:
    """
    Modulo de consultoria de carreira.

    Separado do fluxo principal de extracao, pode ser
    habilitado/desabilitado conforme necessidade.
    """

    @staticmethod
    async def generate_advisory(
        resume_data: Dict[str, Any],
        raw_text: str = "",
    ) -> Dict[str, Any]:
        """
        Gera analise e recomendacoes de carreira baseadas no curriculo.

        Args:
            resume_data: Dados estruturados do curriculo
            raw_text: Texto bruto do curriculo (opcional, para contexto adicional)

        Returns:
            Dict com analise completa e recomendacoes
        """
        if not settings.openai_api_key:
            return {
                "available": False,
                "error": "API key OpenAI nao configurada",
                "data": None,
            }

        try:
            personal = resume_data.get("personal_info", {})
            professional = resume_data.get("professional_objective", {})

            # Preparar dados para o prompt
            name = personal.get("name", "Nao informado")
            objective = professional.get("title", "Nao informado")
            summary = professional.get("summary", "Nao informado")

            # Formatar experiencias
            experiences_list = resume_data.get("experiences", [])
            exp_text = ""
            for exp in experiences_list:
                if isinstance(exp, dict):
                    exp_text += (
                        f"- {exp.get('title', 'N/A')} na {exp.get('company', 'N/A')} "
                        f"({exp.get('start_date', '?')} a {exp.get('end_date', '?')})\n"
                        f"  {exp.get('description', '')}\n"
                    )
            if not exp_text:
                exp_text = "Nao informado"

            # Formatar formacao
            education_list = resume_data.get("education", [])
            edu_text = ""
            for edu in education_list:
                if isinstance(edu, dict):
                    edu_text += (
                        f"- {edu.get('degree', 'N/A')} - "
                        f"{edu.get('institution', 'N/A')} "
                        f"({edu.get('end_year') or edu.get('year', '?')})\n"
                    )
            if not edu_text:
                edu_text = "Nao informado"

            # Formatar skills
            skills = resume_data.get("skills", {})
            if isinstance(skills, dict):
                all_skills = (
                    skills.get("technical", []) +
                    skills.get("soft", []) +
                    skills.get("tools", []) +
                    skills.get("frameworks", [])
                )
                skills_text = ", ".join(all_skills) if all_skills else "Nao informado"
            elif isinstance(skills, list):
                skills_text = ", ".join(skills) if skills else "Nao informado"
            else:
                skills_text = "Nao informado"

            # Formatar idiomas
            languages = resume_data.get("languages", [])
            lang_text = ", ".join(
                f"{l.get('language', 'N/A')} ({l.get('level', 'N/A')})"
                for l in languages if isinstance(l, dict)
            ) or "Nao informado"

            # Formatar certificacoes
            certifications = resume_data.get("certifications", [])
            cert_text = ", ".join(
                c.get("name", c) if isinstance(c, dict) else str(c)
                for c in certifications
            ) or "Nao informado"

            prompt = CAREER_ADVISORY_PROMPT.format(
                name=name,
                objective=objective,
                summary=summary,
                experiences=exp_text,
                education=edu_text,
                skills=skills_text,
                languages=lang_text,
                certifications=cert_text,
            )

            response = await llm_client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Voce e um consultor de carreira especializado. "
                            "Responda APENAS com JSON valido, sem markdown."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
                max_tokens=4000,
            )

            raw = response.content.strip()

            # Limpar possivel markdown
            if raw.startswith("```"):
                raw = re.sub(r'^```(?:json)?\s*', '', raw)
                raw = re.sub(r'\s*```$', '', raw)

            advisory_data = json.loads(raw)

            return {
                "available": True,
                "data": advisory_data,
                "tokens_used": response.usage.total_tokens if response.usage else 0,
                "model_used": settings.chat_model,
            }

        except json.JSONDecodeError as e:
            logger.error(f"Erro ao parsear JSON da consultoria: {e}")
            return {
                "available": True,
                "data": None,
                "error": f"Resposta da IA invalida: {e}",
            }
        except Exception as e:
            logger.error(f"Erro na consultoria de carreira: {e}")
            return {
                "available": True,
                "data": None,
                "error": str(e),
            }

    @staticmethod
    def generate_quick_tips(resume_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Gera dicas rapidas sem usar IA (heuristicas).
        Util quando a API nao esta disponivel.

        Args:
            resume_data: Dados estruturados do curriculo

        Returns:
            Lista de dicas rapidas
        """
        tips = []
        personal = resume_data.get("personal_info", {})
        professional = resume_data.get("professional_objective", {})
        experiences = resume_data.get("experiences", [])
        education = resume_data.get("education", [])
        skills = resume_data.get("skills", {})
        languages = resume_data.get("languages", [])

        # Verificar resumo profissional
        summary = professional.get("summary")
        if not summary:
            tips.append({
                "tip": "Adicione um resumo profissional de 3-4 linhas no inicio do curriculo.",
                "category": "conteudo",
                "priority": "alta",
            })
        elif len(summary) < 50:
            tips.append({
                "tip": "Seu resumo profissional esta muito curto. Expanda para 3-4 linhas.",
                "category": "conteudo",
                "priority": "media",
            })

        # Verificar email
        if not personal.get("email"):
            tips.append({
                "tip": "Inclua um email profissional no curriculo.",
                "category": "contato",
                "priority": "alta",
            })

        # Verificar telefone
        if not personal.get("phone"):
            tips.append({
                "tip": "Inclua um numero de telefone atualizado.",
                "category": "contato",
                "priority": "alta",
            })

        # Verificar LinkedIn
        if not personal.get("linkedin"):
            tips.append({
                "tip": "Adicione o link do seu perfil LinkedIn.",
                "category": "contato",
                "priority": "media",
            })

        # Verificar experiencias
        if not experiences:
            tips.append({
                "tip": "Inclua suas experiencias profissionais com datas, cargos e descricoes.",
                "category": "conteudo",
                "priority": "alta",
            })
        else:
            for exp in experiences:
                if isinstance(exp, dict) and not exp.get("description"):
                    tips.append({
                        "tip": f"Adicione descricao de atividades para a experiencia em '{exp.get('company', 'empresa')}'.",
                        "category": "conteudo",
                        "priority": "media",
                    })
                    break

        # Verificar formacao
        if not education:
            tips.append({
                "tip": "Inclua sua formacao academica.",
                "category": "conteudo",
                "priority": "media",
            })

        # Verificar skills
        if isinstance(skills, dict):
            all_skills = skills.get("technical", []) + skills.get("soft", [])
        elif isinstance(skills, list):
            all_skills = skills
        else:
            all_skills = []

        if len(all_skills) < 5:
            tips.append({
                "tip": "Liste pelo menos 8-10 competencias tecnicas e comportamentais.",
                "category": "conteudo",
                "priority": "media",
            })

        # Verificar idiomas
        if not languages:
            tips.append({
                "tip": "Inclua seus idiomas e niveis de proficiencia.",
                "category": "conteudo",
                "priority": "media",
            })

        return tips
