"""
Servico de melhoria de perfil do candidato via IA.

Gera sugestoes de:
- Resumo profissional reescrito com mais impacto
- Bullets de experiencia no padrao STAR / impacto mensuravel
- Headline profissional mais claro

Todas as sugestoes sao RETORNADAS sem aplicar - o candidato decide
se aceita via endpoint `apply`.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.llm_client import llm_client

logger = logging.getLogger(__name__)


SUMMARY_IMPROVE_PROMPT = """Voce e um coach de carreira especialista em curriculos brasileiros.

Reescreva o resumo profissional abaixo para ficar mais impactante, claro
e orientado a valor. Regras:
1. Manter os fatos reais do candidato - NAO inventar anos, empresas ou skills.
2. Ate 4 linhas, cada uma comecando com acao ou resultado.
3. Usar numeros/metrica quando o original mencionar; nao inventar numeros.
4. Tom profissional, primeira pessoa implicita (nao usar "eu").
5. Incorporar 3-5 palavras-chave relevantes ao cargo alvo quando aplicavel.

DADOS:
- Nome: {name}
- Cargo alvo / headline: {headline}
- Resumo atual:
\"\"\"
{summary}
\"\"\"
- Principais skills tecnicas: {skills}
- Experiencias (para contexto, nao reescrever aqui):
{experiences_brief}

RESPONDA APENAS COM JSON VALIDO:
{{
  "improved_summary": "Texto reescrito...",
  "rationale": "Breve explicacao (1-2 frases) das mudancas principais"
}}"""


HEADLINE_IMPROVE_PROMPT = """Voce e um especialista em posicionamento profissional.

Reescreva o HEADLINE / titulo profissional abaixo para ficar mais claro
e comercialmente atraente. Regras:
1. Ate 10 palavras.
2. Manter fatos reais (nao inventar senioridade).
3. Pode usar estrutura "Cargo | Especialidade | Diferencial".
4. Em portugues, salvo se o original estiver em ingles.

DADOS:
- Headline atual: {headline}
- Resumo (contexto): {summary}
- Principais skills: {skills}

RESPONDA APENAS JSON:
{{
  "improved_headline": "...",
  "rationale": "..."
}}"""


EXPERIENCE_IMPROVE_PROMPT = """Voce e especialista em reescrever experiencias profissionais
para maximizar impacto em processos seletivos.

Reescreva a descricao da experiencia abaixo em formato de bullets objetivos
com frases de impacto. Regras:
1. NAO inventar dados, empresas, metricas ou tecnologias.
2. Priorizar: verbo de acao no passado + o que foi feito + resultado/contexto.
3. Entre 3 e 6 bullets. Cada um com ate 2 linhas.
4. Se o original mencionar numeros/metricas, preserve-os literalmente.
5. Eliminar redundancia. Evitar 1a pessoa.

DADOS:
- Empresa: {company}
- Cargo: {title}
- Periodo: {period}
- Descricao original:
\"\"\"
{description}
\"\"\"

RESPONDA APENAS JSON:
{{
  "improved_bullets": [
    "- Bullet 1...",
    "- Bullet 2..."
  ],
  "improved_description": "Versao em paragrafo unico (opcional, pode concatenar os bullets)",
  "rationale": "1-2 frases explicando as mudancas"
}}"""


class ProfileImprovementService:
    @staticmethod
    async def improve_summary(
        name: str,
        headline: Optional[str],
        summary: Optional[str],
        skills: List[str],
        experiences: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not settings.active_llm_api_key:
            return {"ai_available": False, "data": None}
        if not summary or not summary.strip():
            return {"ai_available": True, "data": None, "error": "summary vazio"}

        exps_brief = "\n".join(
            f"- {e.get('title','')} @ {e.get('company','')} ({e.get('start_date','?')} - {e.get('end_date','?')})"
            for e in (experiences or [])[:5]
        ) or "(sem experiencias listadas)"

        prompt = SUMMARY_IMPROVE_PROMPT.format(
            name=name or "",
            headline=headline or "nao informado",
            summary=summary[:4000],
            skills=", ".join((skills or [])[:20]) or "nao informado",
            experiences_brief=exps_brief,
        )
        return await ProfileImprovementService._ask_llm(prompt, max_tokens=800)

    @staticmethod
    async def improve_headline(
        headline: Optional[str],
        summary: Optional[str],
        skills: List[str],
    ) -> Dict[str, Any]:
        if not settings.active_llm_api_key:
            return {"ai_available": False, "data": None}
        if not headline and not summary:
            return {"ai_available": True, "data": None, "error": "sem dados para gerar headline"}

        prompt = HEADLINE_IMPROVE_PROMPT.format(
            headline=headline or "nao informado",
            summary=(summary or "")[:2000],
            skills=", ".join((skills or [])[:15]) or "nao informado",
        )
        return await ProfileImprovementService._ask_llm(prompt, max_tokens=300)

    @staticmethod
    async def improve_experience(
        company: str,
        title: str,
        period: str,
        description: str,
    ) -> Dict[str, Any]:
        if not settings.active_llm_api_key:
            return {"ai_available": False, "data": None}
        if not description or not description.strip():
            return {"ai_available": True, "data": None, "error": "descricao vazia"}

        prompt = EXPERIENCE_IMPROVE_PROMPT.format(
            company=company or "",
            title=title or "",
            period=period or "",
            description=description[:4000],
        )
        return await ProfileImprovementService._ask_llm(prompt, max_tokens=1200)

    @staticmethod
    async def _ask_llm(prompt: str, max_tokens: int = 800) -> Dict[str, Any]:
        try:
            response = await llm_client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Voce e um coach de carreira. Responda APENAS JSON valido, "
                            "sem markdown, sem texto extra."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
                max_tokens=max_tokens,
            )
            raw = (response.content or "").strip()
            if raw.startswith("```"):
                raw = re.sub(r'^```(?:json)?\s*', '', raw)
                raw = re.sub(r'\s*```$', '', raw)

            data = ProfileImprovementService._parse_json(raw)
            if data is None:
                return {"ai_available": True, "data": None, "error": "JSON invalido"}
            return {
                "ai_available": True,
                "data": data,
                "tokens_used": getattr(response, "tokens_used", 0) or 0,
                "model_used": getattr(response, "model", None) or settings.chat_model,
            }
        except Exception as e:
            logger.error(f"Improvement LLM falhou: {e}", exc_info=True)
            return {"ai_available": True, "data": None, "error": str(e)}

    @staticmethod
    def _parse_json(raw: str) -> Optional[Dict[str, Any]]:
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
