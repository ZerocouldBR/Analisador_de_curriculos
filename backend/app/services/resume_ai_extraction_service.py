"""
Servico de extracao de dados de curriculo via IA (LLM)

Utiliza a API LLM para extrair dados estruturados de curriculos
com alta precisao. Funciona como camada de enriquecimento sobre
o parsing por regex, corrigindo erros como confusao entre nome e endereco,
ou nome confundido com competencia/cargo.

Pipeline:
1. Recebe texto bruto do curriculo
2. Envia para LLM com prompt estruturado e regras anti-erro
3. Recebe JSON estruturado com todos os campos
4. Retorna dados extraidos com nivel de confianca
"""
import json
import logging
import re
from typing import Dict, Any, Optional, List

from app.core.config import settings
from app.services.llm_client import llm_client

logger = logging.getLogger(__name__)

# Prompt de extracao estruturada - altamente detalhado para evitar erros
RESUME_EXTRACTION_PROMPT = """Voce e um especialista em analise de curriculos brasileiros e internacionais (LinkedIn PDF export incluso).
Sua tarefa e extrair TODOS os dados estruturados do curriculo abaixo com MAXIMA precisao.

REGRAS CRITICAS - LEIA ATENTAMENTE:

1. NOME DO CANDIDATO (CAMPO MAIS IMPORTANTE)
   - O nome e SEMPRE um nome proprio de pessoa (ex: "Maria Silva", "Joao Santos", "Lucas Muller Rodrigues").
   - Em PDFs exportados do LinkedIn, o nome aparece geralmente na primeira pagina, no topo, grande, ANTES de "Contato", "Resumo" ou "Principais competencias".
   - NUNCA confunda com: endereco, rua, avenida, bairro, cidade, CEP.
   - NUNCA confunda com: cargo, headline profissional, email, telefone.
   - NUNCA confunda com COMPETENCIAS ou HABILIDADES: "Gestao de X", "Gestao de data center", "Active Directory", "Workspace one", "Especialista em Y", "Lideranca de equipes", "Senior Project Manager" NAO sao nomes.
   - Regra pratica: se a string contem substantivos tecnicos, verbos, preposicoes como "de/do/em/para" conectando termos tecnicos, NAO e nome.
   - Se varios candidatos a nome aparecem, escolha o que tem APENAS palavras capitalizadas sem termos tecnicos.
   - Se o documento for exportacao PDF do LinkedIn, o nome geralmente aparece SOZINHO em uma linha grande antes da secao "Contato".

2. LINKEDIN URL (EXTRAIA COM ATENCAO)
   - PROCURE padroes: "linkedin.com/in/...", "www.linkedin.com/in/...", "https://linkedin.com/in/...", ou simplesmente "linkedin.com/in/usuario".
   - Em PDFs exportados do LinkedIn, a URL aparece na secao "Contato" ou abaixo do nome, geralmente nesse formato: "www.linkedin.com/in/<slug>".
   - Atencao: a URL pode estar QUEBRADA em duas linhas - junte as linhas se a primeira termina com "linkedin.com/in/" ou "-" e a proxima comeca com letras/numeros.
   - RETORNE SEMPRE com protocolo https:// prefixado.
   - Tambem extraia GitHub (github.com/usuario) e portfolio/site pessoal (mullerrodrigues.com, etc).

3. TITULO PROFISSIONAL / HEADLINE
   - E o titulo que aparece LOGO ABAIXO do nome no topo do curriculo (ex: "Senior Project Manager", "Desenvolvedor Backend", "Gerente de Projetos").
   - NAO confunda com competencias listadas em "Principais competencias" ou "Skills".
   - Em PDFs do LinkedIn, aparece imediatamente apos o nome, antes da localizacao.

4. RESUMO PROFISSIONAL
   - Secao "Resumo", "Sobre", "Summary", "Perfil Profissional" - extraia COMPLETA.
   - Se houver multiplos paragrafos, concatene-os preservando quebras de linha (use \\n).

5. COMPETENCIAS vs TITULO
   - "Principais competencias", "Top Skills", "Key Skills" = listar em skills.technical
   - Cada item de competencia e uma skill, NAO um titulo profissional.

6. FOTO DO CANDIDATO
   - Verifique se o PDF/documento MENCIONA foto do candidato (ex: "foto no cabecalho", imagens embutidas na primeira pagina).
   - Se nao conseguir determinar, retorne "has_photo": false.

7. EXPERIENCIAS
   - Extraia TODAS as experiencias listadas, mesmo que longas.
   - Formato datas: MM/YYYY ou YYYY; "atual"/"presente" para vigente.
   - Descricao: mantenha o texto completo, nao resuma.

8. IDIOMAS
   - Extraia cada idioma com seu nivel. Em PDFs do LinkedIn, aparecem em "Languages".
   - Niveis: Nativo, Fluente, Avancado, Intermediario, Basico.

9. CERTIFICACOES
   - Extraia TODAS, mesmo que haja dezenas.
   - Para cada uma: nome, emissor quando identificavel, codigo (NR-10, PMP, etc).

10. GERAL
    - Extraia TODOS os campos disponiveis. Se nao encontrar, use null.
    - Para cada campo principal, forneca score de confianca de 0.0 a 1.0.
    - Responda APENAS com JSON valido, sem markdown, sem explicacoes.
    - NAO trunque: se faltar espaco, priorize campos pessoais e titulo; encurte descricoes longas.

FORMATO DE RESPOSTA (JSON):
{{
  "personal_info": {{
    "name": "Nome Completo da Pessoa",
    "name_confidence": 0.95,
    "email": "email@exemplo.com",
    "email_confidence": 0.99,
    "phone": "(11) 99999-9999",
    "phone_confidence": 0.95,
    "location": "Cidade, UF",
    "location_confidence": 0.9,
    "full_address": "Rua X, 123, Bairro Y, Cidade - UF, CEP 00000-000",
    "linkedin": "https://www.linkedin.com/in/perfil",
    "linkedin_confidence": 0.95,
    "github": "https://github.com/usuario",
    "portfolio": "https://portfolio.com",
    "birth_date": "01/01/1990",
    "cpf": "000.000.000-00",
    "rg": "00.000.000-0",
    "has_photo": false
  }},
  "professional_objective": {{
    "title": "Cargo ou headline profissional (ex: Senior Project Manager | IA & Transformacao Digital)",
    "summary": "Resumo profissional COMPLETO do candidato, todos os paragrafos",
    "confidence": 0.85
  }},
  "experiences": [
    {{
      "company": "Nome da Empresa",
      "title": "Cargo Ocupado",
      "start_date": "01/2020",
      "end_date": "atual",
      "location": "Cidade, UF",
      "description": "Descricao completa das atividades e responsabilidades",
      "achievements": ["Conquista 1", "Conquista 2"]
    }}
  ],
  "education": [
    {{
      "institution": "Nome da Instituicao",
      "degree": "Tipo do curso (Graduacao, Pos, MBA, etc)",
      "field": "Area do curso",
      "start_year": "2015",
      "end_year": "2019",
      "status": "Completo"
    }}
  ],
  "skills": {{
    "technical": ["Skill tecnica 1", "Skill tecnica 2"],
    "soft": ["Habilidade comportamental 1"],
    "tools": ["Ferramenta 1", "Ferramenta 2"],
    "frameworks": ["Framework 1"]
  }},
  "languages": [
    {{"language": "Portugues", "level": "Nativo"}},
    {{"language": "Ingles", "level": "Avancado"}}
  ],
  "certifications": [
    {{
      "name": "Nome da Certificacao",
      "institution": "Instituicao Emissora",
      "year": "2023",
      "code": "Codigo se houver (ex: NR-10, PMP)"
    }}
  ],
  "licenses": [
    {{"type": "CNH", "category": "B", "description": "Carteira de motorista categoria B"}}
  ],
  "additional_info": {{
    "availability": {{"shifts": [], "travel": false, "relocation": false, "immediate_start": false}},
    "equipment": [],
    "erp_systems": [],
    "safety_certifications": []
  }}
}}

CURRICULO PARA ANALISE:
---
{resume_text}
---

Responda SOMENTE com o JSON valido:"""


# Padroes que indicam que um texto e uma COMPETENCIA/HABILIDADE, nao um nome
_COMPETENCY_PATTERNS = [
    r'\bgest[aã]o\s+d[eo]\b',           # Gestao de...
    r'\b(?:gerenciamento|administra[çc][aã]o)\s+d[eo]\b',
    r'\b(?:especialista|especializado)\s+em\b',
    r'\b(?:lideran[çc]a|coordena[çc][aã]o)\s+(?:de|em)\b',
    r'\b(?:desenvolvimento|desenvolvedor)\s+(?:de|em|web|mobile|backend|frontend)\b',
    r'\b(?:engenheiro|analista|gerente|diretor|coordenador|supervisor|operador|assistente)\s+(?:de|em)\b',
    r'\bsenior\s+(?:project|software|data|product)\b',
    r'\b(?:project|product|program)\s+manager\b',
    r'\b(?:active\s+directory|workspace\s+one|data\s+center)\b',
    r'\bsap\s+\w+\b',                    # SAP PP, SAP MM
    r'\b(?:aws|azure|gcp|google\s+cloud)\b',
    r'\b(?:python|java|javascript|typescript|react|angular|vue)\b',
    r'\bPMO\s+Leadership\b',
    r'\binteligencia\s+artificial\b',
    r'\bmachine\s+learning\b',
]


class ResumeAIExtractionService:
    """
    Servico de extracao de curriculo usando IA/LLM.

    Usado como camada de refinamento apos o parsing por regex,
    ou como metodo primario quando disponivel.
    """

    @staticmethod
    async def extract_with_ai(
        text: str,
        regex_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Extrai dados do curriculo usando LLM.

        Args:
            text: Texto bruto do curriculo
            regex_data: Dados extraidos por regex (para comparacao)

        Returns:
            Dict com dados extraidos e confianca
        """
        if not settings.active_llm_api_key:
            logger.warning(f"{settings.llm_provider.value} API key nao configurada - pulando extracao por IA")
            return {"ai_available": False, "data": None}

        # Estrategia multi-pass: primeira tentativa com texto mais completo (ate 24k),
        # em caso de falha faz retry com texto reduzido.
        attempts = [
            {"chars": 24000, "max_tokens": 8000},
            {"chars": 16000, "max_tokens": 6000},
            {"chars": 10000, "max_tokens": 4000},
        ]

        last_error: Optional[str] = None

        for attempt_idx, cfg in enumerate(attempts):
            try:
                truncated = text[: cfg["chars"]] if len(text) > cfg["chars"] else text

                prompt = RESUME_EXTRACTION_PROMPT.format(resume_text=truncated)

                response = await llm_client.chat_completion(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Voce e um extrator especializado de dados de curriculos. "
                                "Siga ESTRITAMENTE as regras do prompt. "
                                "Responda APENAS com JSON valido, sem markdown, sem comentarios."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.0,
                    max_tokens=cfg["max_tokens"],
                )

                raw = (response.content or "").strip()

                # Limpar possivel markdown wrapping
                if raw.startswith("```"):
                    raw = re.sub(r'^```(?:json)?\s*', '', raw)
                    raw = re.sub(r'\s*```$', '', raw)

                # Extrair o primeiro bloco JSON balanceado (LLMs as vezes adicionam texto extra)
                ai_data = ResumeAIExtractionService._parse_json_robust(raw)

                if ai_data is None:
                    last_error = "JSON nao encontrado na resposta"
                    logger.warning(
                        f"Tentativa {attempt_idx + 1}: IA nao retornou JSON parseavel. Retrying..."
                    )
                    continue

                return {
                    "ai_available": True,
                    "data": ai_data,
                    "model_used": getattr(response, "model", None) or settings.chat_model,
                    "tokens_used": getattr(response, "tokens_used", 0) or 0,
                    "input_tokens": getattr(response, "input_tokens", 0) or 0,
                    "output_tokens": getattr(response, "output_tokens", 0) or 0,
                    "attempt": attempt_idx + 1,
                }

            except json.JSONDecodeError as e:
                last_error = f"JSON invalido: {e}"
                logger.error(f"Tentativa {attempt_idx + 1}: erro ao parsear JSON da IA: {e}")
                continue
            except Exception as e:
                last_error = str(e)
                logger.error(f"Tentativa {attempt_idx + 1}: erro na extracao por IA: {e}")
                continue

        return {"ai_available": True, "data": None, "error": last_error or "Todas as tentativas falharam"}

    @staticmethod
    def _parse_json_robust(raw: str) -> Optional[Dict[str, Any]]:
        """
        Parser JSON robusto que aceita respostas com texto extra antes/depois do JSON.
        Procura o primeiro objeto JSON balanceado.
        """
        if not raw:
            return None

        # Tentativa direta
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Procurar primeiro '{' e parsear com contador de chaves
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
                    candidate = raw[start : i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        return None
        return None

    @staticmethod
    async def validate_extraction(
        regex_data: Dict[str, Any],
        ai_data: Dict[str, Any],
        raw_text: str,
    ) -> Dict[str, Any]:
        """
        Valida e reconcilia dados extraidos por regex vs IA.

        Prioriza dados da IA quando ha divergencia, mas usa heuristicas
        para detectar quando o regex acertou e a IA errou.

        Args:
            regex_data: Dados do parser por regex
            ai_data: Dados do parser por IA
            raw_text: Texto bruto original

        Returns:
            Dict com dados validados e reconciliados
        """
        if not ai_data or not ai_data.get("data"):
            return {
                "source": "regex_only",
                "data": regex_data,
                "validation_notes": ["IA indisponivel - usando apenas regex"],
            }

        ai = ai_data["data"]
        notes = []

        # Reconciliar personal_info
        ai_personal = ai.get("personal_info", {})
        regex_personal = regex_data.get("personal_info", {})

        validated_personal = {}

        # --- NOME: campo mais critico ---
        ai_name = ai_personal.get("name")
        regex_name = regex_personal.get("name")
        ai_name_conf = ai_personal.get("name_confidence", 0.5)

        name_result = ResumeAIExtractionService._validate_name(
            ai_name, regex_name, ai_name_conf, raw_text
        )
        validated_personal["name"] = name_result["value"]
        validated_personal["name_confidence"] = name_result["confidence"]
        validated_personal["name_source"] = name_result["source"]
        if name_result.get("note"):
            notes.append(name_result["note"])

        # --- EMAIL ---
        ai_email = ai_personal.get("email")
        regex_email = regex_personal.get("email")
        if ai_email and re.match(r'^[^@]+@[^@]+\.[^@]+$', ai_email):
            validated_personal["email"] = ai_email
            validated_personal["email_confidence"] = ai_personal.get("email_confidence", 0.95)
        elif regex_email:
            validated_personal["email"] = regex_email
            validated_personal["email_confidence"] = 0.9
        else:
            validated_personal["email"] = None
            validated_personal["email_confidence"] = 0.0

        # --- TELEFONE ---
        ai_phone = ai_personal.get("phone")
        regex_phone = regex_personal.get("phone")
        validated_personal["phone"] = ai_phone or regex_phone
        validated_personal["phone_confidence"] = ai_personal.get("phone_confidence", 0.9) if ai_phone else (0.85 if regex_phone else 0.0)

        # --- LOCALIZACAO ---
        ai_location = ai_personal.get("location")
        regex_location = regex_personal.get("location")
        validated_personal["location"] = ai_location or regex_location
        validated_personal["location_confidence"] = ai_personal.get("location_confidence", 0.85) if ai_location else (0.7 if regex_location else 0.0)
        validated_personal["full_address"] = ai_personal.get("full_address")

        # --- LINKEDIN URL (com normalizacao e confianca) ---
        ai_linkedin = ResumeAIExtractionService._normalize_linkedin_url(
            ai_personal.get("linkedin")
        )
        regex_linkedin = ResumeAIExtractionService._normalize_linkedin_url(
            regex_personal.get("linkedin")
        )
        # Fallback: buscar diretamente no texto bruto
        fallback_linkedin = ResumeAIExtractionService._find_linkedin_in_text(raw_text)

        chosen_linkedin = ai_linkedin or regex_linkedin or fallback_linkedin
        validated_personal["linkedin"] = chosen_linkedin
        if chosen_linkedin:
            validated_personal["linkedin_confidence"] = (
                ai_personal.get("linkedin_confidence", 0.9) if ai_linkedin else 0.85
            )
        else:
            validated_personal["linkedin_confidence"] = 0.0

        # --- OUTROS CAMPOS PESSOAIS ---
        for field in ["github", "portfolio", "cpf", "rg", "birth_date"]:
            ai_val = ai_personal.get(field)
            regex_val = regex_personal.get(field)
            validated_personal[field] = ai_val or regex_val

        # --- FOTO DO CANDIDATO ---
        validated_personal["has_photo"] = bool(ai_personal.get("has_photo"))

        # Reconciliar demais secoes (priorizar IA)
        validated = {
            "personal_info": validated_personal,
            "professional_objective": ai.get("professional_objective", {
                "title": None,
                "summary": regex_data.get("summary"),
                "confidence": 0.5,
            }),
            "experiences": ai.get("experiences", regex_data.get("experiences", [])),
            "education": ai.get("education", regex_data.get("education", [])),
            "skills": ai.get("skills", {
                "technical": regex_data.get("skills", []),
                "soft": [],
                "tools": [],
                "frameworks": [],
            }),
            "languages": ai.get("languages", regex_data.get("languages", [])),
            "certifications": ai.get("certifications") or regex_data.get("certifications", []),
            "licenses": ai.get("licenses", regex_data.get("licenses", [])),
            "additional_info": ai.get("additional_info", {
                "availability": regex_data.get("availability", {}),
                "equipment": regex_data.get("equipment", []),
                "erp_systems": regex_data.get("erp_systems", []),
                "safety_certifications": regex_data.get("safety_certs", []),
            }),
        }

        return {
            "source": "ai_validated",
            "data": validated,
            "validation_notes": notes,
            "model_used": ai_data.get("model_used"),
            "tokens_used": ai_data.get("tokens_used", 0),
        }

    @staticmethod
    def _validate_name(
        ai_name: Optional[str],
        regex_name: Optional[str],
        ai_confidence: float,
        raw_text: str,
    ) -> Dict[str, Any]:
        """
        Validacao especifica para o campo nome.

        Aplica multiplas heuristicas para garantir que o nome extraido
        e realmente um nome de pessoa e nao um endereco, competencia ou cargo.
        """
        # Indicadores de que um texto e endereco, nao nome
        address_indicators = [
            r'\b(?:rua|r\.)\s',
            r'\b(?:avenida|av\.)\s',
            r'\b(?:alameda|al\.)\s',
            r'\b(?:travessa|tv\.)\s',
            r'\b(?:praca|pca\.)\s',
            r'\b(?:estrada|estr\.)\s',
            r'\b(?:rodovia|rod\.)\s',
            r'\b(?:bairro|bro\.)\s',
            r'\b(?:cep|CEP)\b',
            r'\b\d{5}[-.]?\d{3}\b',  # CEP
            r'\bnº?\s*\d+',  # Numero de endereco
            r',\s*[A-Z]{2}\s*$',  # Virgula seguida de UF no final
            r'\b\d{2,}\b',  # Numeros com 2+ digitos
        ]

        def _is_address(text: str) -> bool:
            if not text:
                return False
            text_lower = text.lower().strip()
            for pattern in address_indicators:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    return True
            return False

        def _is_competency_or_title(text: str) -> bool:
            """Detecta se um texto parece competencia, skill ou titulo tecnico, nao nome."""
            if not text:
                return False
            for pattern in _COMPETENCY_PATTERNS:
                if re.search(pattern, text, re.IGNORECASE):
                    return True
            # Detectar termos em ingles tecnico que nunca sao nomes
            tech_terms = {
                'manager', 'engineer', 'developer', 'analyst', 'specialist',
                'director', 'lead', 'senior', 'junior', 'pleno',
                'data', 'cloud', 'security', 'devops', 'scrum',
            }
            words_lower = {w.lower().rstrip('.,;:') for w in text.split()}
            if len(words_lower & tech_terms) >= 1:
                # Pode ser nome como "Junior Silva" - verificar se maior parte e nome proprio
                non_tech = [w for w in text.split()
                            if w.lower().rstrip('.,;:') not in tech_terms]
                # Se menos de 2 palavras nao-tecnicas, parece titulo
                if len(non_tech) < 2:
                    return True
            return False

        def _is_valid_name(text: str) -> bool:
            if not text:
                return False
            text = text.strip()
            # Nome deve ter pelo menos 2 palavras
            words = text.split()
            if len(words) < 2:
                return False
            # Nome nao pode ser muito longo (mais de 8 palavras e suspeito)
            if len(words) > 8:
                return False
            # Nao pode conter numeros
            if re.search(r'\d', text):
                return False
            # Nao pode conter caracteres especiais de endereco
            if re.search(r'[@#$%&*!?/\\|{}[\]<>]', text):
                return False
            # Nao pode ser competencia/titulo tecnico
            if _is_competency_or_title(text):
                return False
            # Cada palavra deve comecar com letra (maiuscula idealmente)
            # mas aceitamos preposicoes em minuscula (de, da, do, dos, das, e)
            prepositions = {'de', 'da', 'do', 'dos', 'das', 'e', 'di', 'del'}
            for word in words:
                if word.lower() not in prepositions and not word[0].isalpha():
                    return False
            return True

        # Caso 1: IA forneceu nome com boa confianca e passa validacao
        if ai_name and ai_confidence >= 0.7 and _is_valid_name(ai_name) and not _is_address(ai_name):
            return {
                "value": ai_name.strip(),
                "confidence": min(ai_confidence, 0.98),
                "source": "ai",
            }

        # Caso 2a: Nome da IA e na verdade um endereco
        # Caso 2b: Nome da IA e uma competencia/titulo (ex: "Gestao de data center")
        ai_is_bad = ai_name and (_is_address(ai_name) or _is_competency_or_title(ai_name))
        if ai_is_bad:
            reason = "endereco" if _is_address(ai_name) else "competencia/titulo"
            # IA errou - tentar regex
            if regex_name and _is_valid_name(regex_name) and not _is_address(regex_name) and not _is_competency_or_title(regex_name):
                return {
                    "value": regex_name.strip(),
                    "confidence": 0.7,
                    "source": "regex_fallback",
                    "note": f"IA confundiu nome com {reason} ('{ai_name}'). Usando regex.",
                }
            # Ambos falharam - tentar primeira linha do texto
            fallback_name = ResumeAIExtractionService._extract_name_from_first_lines(raw_text)
            if fallback_name:
                return {
                    "value": fallback_name,
                    "confidence": 0.5,
                    "source": "heuristic_fallback",
                    "note": f"IA confundiu nome com {reason}; usando heuristica de primeira linha.",
                }
            return {
                "value": ai_name.strip(),
                "confidence": 0.2,
                "source": "ai_low_confidence",
                "note": f"Nome pode estar incorreto - possivel {reason}.",
            }

        # Caso 3: IA nao forneceu nome - usar regex
        if not ai_name and regex_name:
            if _is_valid_name(regex_name) and not _is_address(regex_name) and not _is_competency_or_title(regex_name):
                return {
                    "value": regex_name.strip(),
                    "confidence": 0.75,
                    "source": "regex",
                }
            elif _is_address(regex_name) or _is_competency_or_title(regex_name):
                fallback = ResumeAIExtractionService._extract_name_from_first_lines(raw_text)
                return {
                    "value": fallback or regex_name.strip(),
                    "confidence": 0.3 if not fallback else 0.5,
                    "source": "heuristic_fallback",
                    "note": f"Regex confundiu nome com endereco/competencia ('{regex_name}').",
                }

        # Caso 4: Nenhum forneceu nome
        if not ai_name and not regex_name:
            fallback = ResumeAIExtractionService._extract_name_from_first_lines(raw_text)
            return {
                "value": fallback,
                "confidence": 0.4 if fallback else 0.0,
                "source": "heuristic_fallback" if fallback else "none",
                "note": "Nome nao identificado por nenhum metodo.",
            }

        # Caso default: IA com baixa confianca
        if ai_name and _is_valid_name(ai_name):
            return {
                "value": ai_name.strip(),
                "confidence": max(ai_confidence, 0.5),
                "source": "ai_low_confidence",
            }

        return {
            "value": ai_name or regex_name,
            "confidence": 0.3,
            "source": "uncertain",
            "note": "Baixa confianca na extracao do nome.",
        }

    @staticmethod
    def _normalize_linkedin_url(url: Optional[str]) -> Optional[str]:
        """
        Normaliza URL do LinkedIn para formato canonico https://www.linkedin.com/in/<slug>.
        Aceita variacoes: com/sem protocolo, com/sem www, com/sem barra final.
        """
        if not url or not isinstance(url, str):
            return None
        url = url.strip().rstrip('/,;.)')
        if not url:
            return None

        # Extrair slug (parte apos /in/)
        match = re.search(
            r'(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/(?:in|pub)/([A-Za-z0-9\-_%]+)',
            url,
            re.IGNORECASE,
        )
        if match:
            slug = match.group(1).rstrip('-_')
            if len(slug) >= 3:
                return f"https://www.linkedin.com/in/{slug}"

        # Se a URL mencionada nao tem /in/ mas menciona linkedin.com, manter como foi fornecida
        if 'linkedin.com' in url.lower():
            if not url.lower().startswith('http'):
                url = 'https://' + url
            return url

        return None

    @staticmethod
    def _find_linkedin_in_text(text: str) -> Optional[str]:
        """
        Busca URL do LinkedIn no texto bruto, lidando com quebras de linha.
        PDFs as vezes quebram URLs em multiplas linhas.
        """
        if not text:
            return None

        # Juntar linhas que terminam com hifen ou com 'linkedin.com/in/' incompletos
        normalized = re.sub(r'(linkedin\.com/in/[A-Za-z0-9\-_]*)\s*\n\s*([A-Za-z0-9\-_]+)',
                           r'\1\2', text, flags=re.IGNORECASE)
        normalized = re.sub(r'([A-Za-z0-9\-_]+)-\s*\n\s*([A-Za-z0-9\-_]+)',
                           r'\1-\2', normalized)

        # Padroes aceitos
        patterns = [
            r'https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/[A-Za-z0-9\-_%]+',
            r'(?:[a-z]{2,3}\.)?linkedin\.com/in/[A-Za-z0-9\-_%]+',
            r'https?://(?:[a-z]{2,3}\.)?linkedin\.com/pub/[A-Za-z0-9\-_%]+',
        ]
        for pattern in patterns:
            match = re.search(pattern, normalized, re.IGNORECASE)
            if match:
                return ResumeAIExtractionService._normalize_linkedin_url(match.group(0))

        return None

    @staticmethod
    def _extract_name_from_first_lines(text: str) -> Optional[str]:
        """
        Heuristica robusta para extrair nome das primeiras linhas.

        Aplica filtros agressivos contra enderecos, emails, telefones,
        competencias e titulos profissionais. Suporta PDFs do LinkedIn.
        """
        address_words = {
            'rua', 'avenida', 'av', 'alameda', 'al', 'travessa', 'tv',
            'praca', 'pca', 'estrada', 'estr', 'rodovia', 'rod',
            'bairro', 'bro', 'cep', 'endereco', 'endereço',
            'quadra', 'lote', 'bloco', 'conjunto', 'condominio',
            'apartamento', 'apto', 'casa', 'sala', 'andar',
        }
        section_words = {
            'experiencia', 'experiência', 'formacao', 'formação',
            'habilidades', 'objetivo', 'resumo', 'certificacao',
            'certificação', 'idioma', 'idiomas', 'languages',
            'dados', 'curriculo', 'curriculum', 'vitae',
            'perfil', 'profissional', 'resume',
            'contato', 'contact', 'informacoes', 'informações',
            'educacao', 'educação', 'education',
            'competencias', 'competências', 'competences', 'skills',
            'qualificacoes', 'qualificações',
            'sobre', 'endereco', 'endereço',
            'certifications', 'certificações', 'certificacoes',
            'summary',
        }

        def _looks_like_competency(line: str) -> bool:
            for pattern in _COMPETENCY_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    return True
            return False

        lines = [line.strip() for line in text.split('\n') if line.strip()]

        for line in lines[:25]:
            # Pular linhas muito curtas ou muito longas
            if len(line) < 5 or len(line) > 60:
                continue
            # Pular linhas com numeros
            if re.search(r'\d', line):
                continue
            # Pular linhas com caracteres especiais de endereco/contato
            if re.search(r'[!@#$%^&*()=+\[\]{}<>|\\/:;]', line):
                continue
            # Pular se contem palavras de endereco
            line_words_lower = {w.lower().rstrip('.,;:') for w in line.split()}
            if line_words_lower & address_words:
                continue
            # Pular cabecalhos de secao
            if line_words_lower & section_words:
                continue
            # Pular emails e URLs
            low = line.lower()
            if '@' in line or 'http' in low or '.com' in low or 'linkedin' in low or 'github' in low:
                continue
            # Pular se termina com UF (Cidade, SP)
            if re.search(r',\s*[A-Z]{2}\s*$', line):
                continue
            # Pular competencias/titulos tecnicos
            if _looks_like_competency(line):
                continue
            # Pular se tem pipe "|" (muito comum em headlines profissionais)
            if '|' in line:
                continue
            # Deve ter pelo menos 2 palavras
            words = line.split()
            if len(words) < 2:
                continue
            # Primeira palavra deve comecar com maiuscula
            if not words[0][0].isupper():
                continue
            # TODAS as palavras (exceto preposicoes) devem comecar com maiuscula - nome proprio
            preps = {'de', 'da', 'do', 'dos', 'das', 'e', 'di', 'del'}
            non_prep = [w for w in words if w.lower() not in preps]
            if not all(w[0].isupper() for w in non_prep if w):
                continue
            # Parece um nome valido
            return line

        return None
