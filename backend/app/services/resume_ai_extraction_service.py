"""
Servico de extracao de dados de curriculo via IA (LLM)

Utiliza a API OpenAI para extrair dados estruturados de curriculos
com alta precisao. Funciona como camada de enriquecimento sobre
o parsing por regex, corrigindo erros como confusao entre nome e endereco.

Pipeline:
1. Recebe texto bruto do curriculo
2. Envia para LLM com prompt estruturado
3. Recebe JSON estruturado com todos os campos
4. Retorna dados extraidos com nivel de confianca
"""
import json
import logging
import re
from typing import Dict, Any, Optional

from app.core.config import settings
from app.services.llm_client import llm_client

logger = logging.getLogger(__name__)

# Prompt de extracao estruturada - altamente detalhado para evitar erros
RESUME_EXTRACTION_PROMPT = """Voce e um especialista em analise de curriculos brasileiros.
Sua tarefa e extrair TODOS os dados estruturados do curriculo abaixo.

REGRAS CRITICAS:
1. O NOME do candidato e SEMPRE um nome proprio de pessoa (ex: "Maria Silva", "Joao Santos").
   - NUNCA confunda endereco, rua, avenida, bairro, cidade ou CEP com o nome.
   - NUNCA confunda cargo, titulo profissional, email ou telefone com o nome.
   - O nome geralmente aparece no TOPO do curriculo, em destaque.
   - Se o nome estiver em uma linha que contem numeros, virgulas seguidas de estado (SP, RJ),
     palavras como "Rua", "Av.", "Bairro", "CEP", isso NAO e um nome.
2. ENDERECO contem: rua/avenida + numero + bairro + cidade + estado + CEP.
3. CARGO/OBJETIVO aparece proximo ao nome, geralmente abaixo.
4. Extraia TODOS os campos disponiveis. Se nao encontrar um campo, use null.
5. Para cada campo principal, forneca um score de confianca de 0.0 a 1.0.

Responda APENAS com JSON valido, sem markdown, sem explicacoes.

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
    "linkedin": "https://linkedin.com/in/perfil",
    "github": "https://github.com/usuario",
    "portfolio": "https://portfolio.com",
    "birth_date": "01/01/1990",
    "cpf": "000.000.000-00",
    "rg": "00.000.000-0"
  }},
  "professional_objective": {{
    "title": "Cargo ou titulo profissional desejado",
    "summary": "Resumo profissional completo do candidato",
    "confidence": 0.85
  }},
  "experiences": [
    {{
      "company": "Nome da Empresa",
      "title": "Cargo Ocupado",
      "start_date": "01/2020",
      "end_date": "atual",
      "location": "Cidade, UF",
      "description": "Descricao das atividades e responsabilidades",
      "achievements": ["Conquista 1", "Conquista 2"]
    }}
  ],
  "education": [
    {{
      "institution": "Nome da Instituicao",
      "degree": "Tipo do curso (Graduacao, Pos, etc)",
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
      "code": "Codigo se houver (ex: NR-10)"
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

        try:
            # Limitar texto para nao exceder limite de tokens
            truncated = text[:12000] if len(text) > 12000 else text

            prompt = RESUME_EXTRACTION_PROMPT.format(resume_text=truncated)

            response = await llm_client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Voce e um extrator de dados de curriculos. "
                            "Responda APENAS com JSON valido, sem markdown."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=4000,
            )

            raw = response.content.strip()

            # Limpar possivel markdown wrapping
            if raw.startswith("```"):
                raw = re.sub(r'^```(?:json)?\s*', '', raw)
                raw = re.sub(r'\s*```$', '', raw)

            ai_data = json.loads(raw)

            return {
                "ai_available": True,
                "data": ai_data,
                "model_used": settings.chat_model,
                "tokens_used": response.usage.total_tokens if response.usage else 0,
            }

        except json.JSONDecodeError as e:
            logger.error(f"Erro ao parsear JSON da IA: {e}")
            return {"ai_available": True, "data": None, "error": f"JSON invalido: {e}"}
        except Exception as e:
            logger.error(f"Erro na extracao por IA: {e}")
            return {"ai_available": True, "data": None, "error": str(e)}

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

        # --- OUTROS CAMPOS PESSOAIS ---
        for field in ["linkedin", "github", "portfolio", "cpf", "rg", "birth_date"]:
            ai_val = ai_personal.get(field)
            regex_val = regex_personal.get(field)
            validated_personal[field] = ai_val or regex_val

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
        e realmente um nome de pessoa e nao um endereco ou outro campo.
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

        def _is_valid_name(text: str) -> bool:
            if not text:
                return False
            text = text.strip()
            # Nome deve ter pelo menos 2 palavras
            words = text.split()
            if len(words) < 2:
                return False
            # Nome nao pode ser muito longo (mais de 6 palavras e suspeito)
            if len(words) > 8:
                return False
            # Nao pode conter numeros
            if re.search(r'\d', text):
                return False
            # Nao pode conter caracteres especiais de endereco
            if re.search(r'[@#$%&*!?/\\|{}[\]<>]', text):
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

        # Caso 2: Nome da IA e na verdade um endereco
        if ai_name and _is_address(ai_name):
            # IA errou - tentar regex
            if regex_name and _is_valid_name(regex_name) and not _is_address(regex_name):
                return {
                    "value": regex_name.strip(),
                    "confidence": 0.7,
                    "source": "regex_fallback",
                    "note": f"IA confundiu nome com endereco ('{ai_name}'). Usando regex.",
                }
            # Ambos falharam - tentar primeira linha do texto
            fallback_name = ResumeAIExtractionService._extract_name_from_first_lines(raw_text)
            if fallback_name:
                return {
                    "value": fallback_name,
                    "confidence": 0.5,
                    "source": "heuristic_fallback",
                    "note": "Ambos parser (IA e regex) falharam na extracao do nome.",
                }
            return {
                "value": ai_name.strip(),
                "confidence": 0.2,
                "source": "ai_low_confidence",
                "note": "Nome pode estar incorreto - possivel endereco.",
            }

        # Caso 3: IA nao forneceu nome - usar regex
        if not ai_name and regex_name:
            if _is_valid_name(regex_name) and not _is_address(regex_name):
                return {
                    "value": regex_name.strip(),
                    "confidence": 0.75,
                    "source": "regex",
                }
            elif _is_address(regex_name):
                fallback = ResumeAIExtractionService._extract_name_from_first_lines(raw_text)
                return {
                    "value": fallback or regex_name.strip(),
                    "confidence": 0.3 if not fallback else 0.5,
                    "source": "heuristic_fallback",
                    "note": f"Regex confundiu nome com endereco ('{regex_name}').",
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
    def _extract_name_from_first_lines(text: str) -> Optional[str]:
        """
        Heuristica robusta para extrair nome das primeiras linhas.

        Aplica filtros agressivos contra enderecos, emails, telefones, etc.
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
            'certificação', 'idioma', 'dados', 'curriculo',
            'curriculum', 'vitae', 'perfil', 'profissional',
            'contato', 'informacoes', 'informações', 'educacao',
            'educação', 'competencias', 'competências', 'qualificacoes',
            'qualificações', 'sobre', 'endereco', 'endereço',
        }

        lines = [line.strip() for line in text.split('\n') if line.strip()]

        for line in lines[:15]:
            # Pular linhas muito curtas ou muito longas
            if len(line) < 5 or len(line) > 60:
                continue
            # Pular linhas com numeros
            if re.search(r'\d', line):
                continue
            # Pular linhas com caracteres especiais
            if re.search(r'[!@#$%^&*()=+\[\]{}<>|\\/:;,.]', line):
                continue
            # Pular se contem palavras de endereco
            line_words_lower = {w.lower().rstrip('.') for w in line.split()}
            if line_words_lower & address_words:
                continue
            # Pular cabecalhos de secao
            if line_words_lower & section_words:
                continue
            # Pular emails e URLs
            if '@' in line or 'http' in line.lower() or '.com' in line.lower():
                continue
            # Pular se termina com UF (Cidade, SP)
            if re.search(r',\s*[A-Z]{2}\s*$', line):
                continue
            # Deve ter pelo menos 2 palavras
            words = line.split()
            if len(words) < 2:
                continue
            # Primeira palavra deve comecar com maiuscula
            if not words[0][0].isupper():
                continue
            # Parece um nome valido
            return line

        return None
