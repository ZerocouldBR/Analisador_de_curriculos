"""
Servico para parsing estruturado de curriculos

Extrai informacoes como:
- Dados pessoais (nome, email, telefone)
- Experiencias profissionais
- Formacao academica
- Skills (TI, producao, logistica, qualidade)
- Idiomas
- Certificacoes (incluindo NRs, ISO, Lean)
- Habilitacoes (CNH, MOPP)
- Turnos e disponibilidade
- Equipamentos e maquinas
"""
import re
from typing import Optional, Dict, Any
from datetime import datetime
from dateutil.parser import parse as parse_date


class ResumeParserService:
    """
    Servico para parsing estruturado de curriculos

    Suporta perfis de TI, producao, logistica, qualidade e industria
    """

    @staticmethod
    def parse_resume(text: str) -> Dict[str, Any]:
        """
        Faz parsing completo de um curriculo

        Args:
            text: Texto do curriculo

        Returns:
            Dict com informacoes estruturadas
        """
        resume_data = {
            "personal_info": ResumeParserService.extract_personal_info(text),
            "experiences": ResumeParserService.extract_experiences(text),
            "education": ResumeParserService.extract_education(text),
            "skills": ResumeParserService.extract_skills(text),
            "languages": ResumeParserService.extract_languages(text),
            "certifications": ResumeParserService.extract_certifications(text),
            "summary": ResumeParserService.extract_summary(text),
            # Campos especificos para producao e logistica
            "licenses": ResumeParserService.extract_licenses(text),
            "safety_certs": ResumeParserService.extract_safety_certifications(text),
            "equipment": ResumeParserService.extract_equipment_skills(text),
            "availability": ResumeParserService.extract_availability(text),
            "erp_systems": ResumeParserService.extract_erp_systems(text),
        }

        return resume_data

    @staticmethod
    def extract_personal_info(text: str) -> Dict[str, Optional[str]]:
        """Extrai informacoes pessoais com deteccao melhorada"""
        info = {
            "name": None,
            "email": None,
            "phone": None,
            "location": None,
            "linkedin": None,
            "github": None,
            "cpf": None,
            "rg": None,
            "birth_date": None,
        }

        # Email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, text)
        if email_match:
            info["email"] = email_match.group()

        # Telefone (formatos brasileiros - mais abrangente)
        phone_patterns = [
            r'\+55\s*\(?\d{2}\)?\s*\d{4,5}[\s.-]?\d{4}',
            r'\(\d{2}\)\s*\d{4,5}[\s.-]?\d{4}',
            r'\b\d{2}\s*\d{4,5}[\s.-]?\d{4}\b',
            r'(?:tel(?:efone)?|cel(?:ular)?|fone|whatsapp|wpp|contato)[\s.:]+\+?5?5?\s*\(?\d{2}\)?\s*\d{4,5}[\s.-]?\d{4}',
        ]

        for pattern in phone_patterns:
            phone_match = re.search(pattern, text, re.IGNORECASE)
            if phone_match:
                info["phone"] = phone_match.group().strip()
                break

        # LinkedIn - com varias variacoes e correcao de quebras de linha
        # Primeiro normaliza o texto unindo URLs quebradas
        ln_normalized = re.sub(
            r'(linkedin\.com/in/[A-Za-z0-9\-_]*)\s*\n\s*([A-Za-z0-9\-_]+)',
            r'\1\2', text, flags=re.IGNORECASE,
        )
        linkedin_patterns = [
            r'https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/[A-Za-z0-9\-_%]+',
            r'(?:[a-z]{2,3}\.)?linkedin\.com/in/[A-Za-z0-9\-_%]+',
            r'https?://(?:[a-z]{2,3}\.)?linkedin\.com/pub/[A-Za-z0-9\-_%]+',
        ]
        for pattern in linkedin_patterns:
            linkedin_match = re.search(pattern, ln_normalized, re.IGNORECASE)
            if linkedin_match:
                url = linkedin_match.group().rstrip('/,;.)')
                # Extrair slug canonico
                slug_match = re.search(
                    r'linkedin\.com/(?:in|pub)/([A-Za-z0-9\-_%]+)', url, re.IGNORECASE,
                )
                if slug_match:
                    slug = slug_match.group(1).rstrip('-_')
                    if len(slug) >= 3:
                        info["linkedin"] = f"https://www.linkedin.com/in/{slug}"
                        break
                if not url.startswith('http'):
                    url = f"https://{url}"
                info["linkedin"] = url
                break

        # GitHub
        github_pattern = r'(?:https?://)?(?:www\.)?github\.com/[\w-]+'
        github_match = re.search(github_pattern, text, re.IGNORECASE)
        if github_match:
            url = github_match.group()
            if not url.startswith('http'):
                url = f"https://{url}"
            info["github"] = url

        # CPF
        cpf_pattern = r'\b\d{3}[.\s]?\d{3}[.\s]?\d{3}[-.\s]?\d{2}\b'
        cpf_match = re.search(cpf_pattern, text)
        if cpf_match:
            info["cpf"] = cpf_match.group().strip()

        # RG
        rg_patterns = [
            r'(?:RG|identidade|registro\s+geral)[\s.:]+(\d{1,2}[.\s]?\d{3}[.\s]?\d{3}[-.\s]?\d{1,2})',
            r'\b(\d{2}\.\d{3}\.\d{3}-\d{1,2})\b',
        ]
        for pattern in rg_patterns:
            rg_match = re.search(pattern, text, re.IGNORECASE)
            if rg_match:
                info["rg"] = rg_match.group(1).strip() if rg_match.lastindex else rg_match.group().strip()
                break

        # Data de nascimento (mais padroes)
        birth_patterns = [
            r'(?:nascimento|data\s+de\s+nascimento|born|nasc\.?|d\.?\s*n\.?|dt\.?\s*nasc\.?)[\s:]+(\d{2}[/.-]\d{2}[/.-]\d{4})',
            r'(\d{2}[/.-]\d{2}[/.-]\d{4})\s*(?:\(?\s*\d+\s*anos\s*\)?)',
            r'(?:nascido\s+em|nascida\s+em)[\s:]+(\d{2}[/.-]\d{2}[/.-]\d{4})',
        ]
        for pattern in birth_patterns:
            birth_match = re.search(pattern, text, re.IGNORECASE)
            if birth_match:
                info["birth_date"] = birth_match.group(1).strip()
                break

        # Nome - Estrategia robusta com protecao contra enderecos e competencias
        name = None

        # Palavras que indicam ENDERECO (nunca devem estar em um nome)
        _address_words = {
            'rua', 'r.', 'avenida', 'av.', 'av', 'alameda', 'al.', 'al',
            'travessa', 'tv.', 'tv', 'praca', 'praça', 'pca.', 'pca',
            'estrada', 'estr.', 'estr', 'rodovia', 'rod.', 'rod',
            'bairro', 'bro.', 'cep', 'endereco', 'endereço',
            'quadra', 'lote', 'bloco', 'conjunto', 'condominio', 'condomínio',
            'apartamento', 'apto', 'apto.', 'casa', 'sala', 'andar',
            'nº', 'numero', 'número', 'n.',
        }

        # Palavras de cabecalho de secao
        _section_headers = {
            'experiencia', 'experiência', 'formacao', 'formação',
            'habilidades', 'objetivo', 'resumo', 'certificacao',
            'certificação', 'idioma', 'idiomas', 'languages',
            'dados', 'curriculo', 'currículo',
            'curriculum', 'vitae', 'perfil', 'profissional', 'resume',
            'contato', 'contact', 'informacoes', 'informações',
            'educacao', 'educação', 'education',
            'competencias', 'competências', 'competences', 'skills',
            'qualificacoes', 'qualificações',
            'sobre', 'endereco', 'endereço',
            'certifications', 'certificações', 'certificacoes',
            'summary',
        }

        # Padroes que indicam competencias/titulos (nunca sao nomes)
        _competency_patterns = [
            r'\bgest[aã]o\s+d[eo]\b',
            r'\b(?:gerenciamento|administra[çc][aã]o)\s+d[eo]\b',
            r'\b(?:especialista|especializado)\s+em\b',
            r'\b(?:lideran[çc]a|coordena[çc][aã]o)\s+(?:de|em)\b',
            r'\b(?:project|product|program)\s+manager\b',
            r'\b(?:active\s+directory|workspace\s+one|data\s+center)\b',
            r'\bsenior\s+(?:project|software|data|product)\b',
            r'\b(?:desenvolvedor|engenheiro|analista|gerente|diretor|coordenador)\s+(?:de|em)\b',
        ]

        def _looks_like_competency(text_line: str) -> bool:
            for pattern in _competency_patterns:
                if re.search(pattern, text_line, re.IGNORECASE):
                    return True
            return False

        def _looks_like_address(text_line: str) -> bool:
            """Detecta se uma linha parece ser endereco."""
            lower = text_line.lower().strip()
            # Contem palavras tipicas de endereco
            words_in_line = {w.rstrip('.,;:') for w in lower.split()}
            if words_in_line & _address_words:
                return True
            # Contem CEP (00000-000)
            if re.search(r'\b\d{5}[-.]?\d{3}\b', text_line):
                return True
            # Termina com UF (ex: ", SP" ou "- SP")
            if re.search(r'[,\-–]\s*[A-Z]{2}\s*$', text_line):
                return True
            # Contem "nº" ou numero de endereco
            if re.search(r'\bnº?\s*\d+', lower):
                return True
            # Contem virgula + cidade/estado pattern
            if re.search(r',\s*\w+\s*[-–]\s*[A-Z]{2}', text_line):
                return True
            return False

        def _is_valid_person_name(candidate_name: str) -> bool:
            """Valida se parece nome de pessoa."""
            if not candidate_name:
                return False
            words = candidate_name.split()
            if len(words) < 2:
                return False
            if len(words) > 8:
                return False
            if re.search(r'\d', candidate_name):
                return False
            if re.search(r'[@#$%&*!?/\\|{}[\]<>]', candidate_name):
                return False
            if _looks_like_address(candidate_name):
                return False
            if _looks_like_competency(candidate_name):
                return False
            # Pipe tipico em headline profissional
            if '|' in candidate_name:
                return False
            # Preposicoes aceitaveis em nomes
            preps = {'de', 'da', 'do', 'dos', 'das', 'e', 'di', 'del'}
            for word in words:
                if word.lower() not in preps and not word[0].isalpha():
                    return False
            return True

        # 1. Tentar extrair nome de campos rotulados
        name_label_patterns = [
            r'(?:nome\s*(?:completo)?|name)[\s:]+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõçA-ZÁÉÍÓÚÂÊÔÃÕÇ\s]+)',
            r'(?:candidato|candidata)[\s:]+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõçA-ZÁÉÍÓÚÂÊÔÃÕÇ\s]+)',
        ]
        for pattern in name_label_patterns:
            name_match = re.search(pattern, text, re.IGNORECASE)
            if name_match:
                candidate_name = name_match.group(1).strip()
                if _is_valid_person_name(candidate_name):
                    name = candidate_name[:60]
                    break

        # 2. Se nao encontrou rotulado, tentar primeira linha significativa
        if not name:
            lines = [line.strip() for line in text.split('\n') if line.strip()]

            for line in lines[:25]:
                # Pular linhas muito curtas ou muito longas
                if len(line) < 5 or len(line) > 60:
                    continue
                # Pular linhas com numeros (telefone, CPF, endereco)
                if re.search(r'\d', line):
                    continue
                # Pular linhas com caracteres especiais
                if re.search(r'[!@#$%^&*()=+\[\]{}<>\\/:;]', line):
                    continue
                # Pular enderecos (deteccao aprimorada)
                if _looks_like_address(line):
                    continue
                # Pular competencias/titulos profissionais
                if _looks_like_competency(line):
                    continue
                # Pular cabecalhos de secao
                line_words_lower = {w.lower().rstrip('.,;:') for w in line.split()}
                if line_words_lower & _section_headers:
                    continue
                # Pular linhas que sao emails ou URLs
                low = line.lower()
                if '@' in line or 'http' in low or '.com' in low or 'linkedin' in low:
                    continue
                # Pular linhas com virgula (provavelmente endereco ou lista)
                if ',' in line:
                    continue
                # Pular headline com pipe "|"
                if '|' in line:
                    continue
                # Verificar se parece um nome valido
                if _is_valid_person_name(line):
                    name = line
                    break

        if name:
            # Limpar nome: remover titulos e prefixos
            name = re.sub(r'^(?:Sr\.?|Sra\.?|Dr\.?|Dra\.?|Prof\.?)\s+', '', name, flags=re.IGNORECASE)
            info["name"] = name.strip()

        # Localizacao (mais padroes)
        location_patterns = [
            r'(?:endereço|endereco|moradia|resido|residência|residencia|localização|localizacao)[\s:]+(.+?)(?:\n|$)',
            r'([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç\s]+),\s*([A-Z]{2})\b',
            r'([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç\s]+)\s+[-–]\s+([A-Z]{2})\b',
            r'(?:cidade|city|local)[\s:]+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç\s]+)',
        ]

        for pattern in location_patterns:
            location_match = re.search(pattern, text)
            if location_match:
                loc = location_match.group().strip()
                # Nao confundir com cabecalhos de experiencia
                if len(loc) < 80 and not any(h in loc.lower() for h in ['experiencia', 'formacao']):
                    info["location"] = loc
                    break

        return info

    @staticmethod
    def _find_section(text: str, keywords: list, next_keywords: list = None) -> str:
        """
        Encontra e retorna o conteudo de uma secao do curriculo.
        Usa busca flexivel que funciona mesmo com formatacao inconsistente.
        """
        section_start = -1
        for keyword in keywords:
            # Busca flexivel - aceita com ou sem \n, com : ou sem
            patterns = [
                rf'\n\s*{re.escape(keyword)}\s*[:\-]?\s*\n',
                rf'\n\s*{re.escape(keyword)}\s*[:\-]?\s*$',
                rf'^\s*{re.escape(keyword)}\s*[:\-]?\s*\n',
                rf'\n\s*{re.escape(keyword.upper())}\s*[:\-]?\s*\n',
            ]
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                if match:
                    section_start = match.end()
                    break
            if section_start != -1:
                break

        if section_start == -1:
            return ""

        # Encontrar fim da secao
        default_next = [
            'formação', 'formacao', 'educação', 'educacao', 'education',
            'habilidades', 'skills', 'idiomas', 'languages',
            'certificações', 'certificacoes', 'cursos',
            'dados pessoais', 'habilitações', 'habilitacoes',
            'competências', 'competencias', 'qualificações', 'qualificacoes',
            'objetivo', 'resumo', 'perfil', 'referencias',
        ]
        next_kws = next_keywords or default_next

        section_end = len(text)
        for keyword in next_kws:
            patterns = [
                rf'\n\s*{re.escape(keyword)}\s*[:\-]?\s*\n',
                rf'\n\s*{re.escape(keyword.upper())}\s*[:\-]?\s*\n',
            ]
            for pattern in patterns:
                match = re.search(pattern, text[section_start:], re.IGNORECASE | re.MULTILINE)
                if match:
                    candidate_end = section_start + match.start()
                    if candidate_end < section_end:
                        section_end = candidate_end
                    break

        return text[section_start:section_end]

    @staticmethod
    def extract_experiences(text: str) -> list[Dict[str, Any]]:
        """Extrai experiencias profissionais com deteccao melhorada"""
        experiences = []

        experience_keywords = [
            'experiência profissional',
            'experiencia profissional',
            'experiências profissionais',
            'experiencias profissionais',
            'experiência',
            'experiencia',
            'histórico profissional',
            'historico profissional',
            'experience',
            'work experience',
            'employment',
            'atividades profissionais',
        ]

        experience_text = ResumeParserService._find_section(text, experience_keywords)
        if not experience_text:
            # Fallback: tentar busca direta
            section_start = -1
            for keyword in experience_keywords:
                pattern = rf'\n\s*{re.escape(keyword)}\s*\n'
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    section_start = match.end()
                    break

            if section_start == -1:
                return experiences

            next_section_keywords = [
                'formação', 'formacao', 'educação', 'educacao', 'education',
                'habilidades', 'skills', 'idiomas', 'languages',
                'certificações', 'certificacoes', 'cursos',
                'dados pessoais', 'habilitações', 'habilitacoes',
            ]

            section_end = len(text)
            for keyword in next_section_keywords:
                pattern = rf'\n\s*{re.escape(keyword)}\s*\n'
                match = re.search(pattern, text[section_start:], re.IGNORECASE)
                if match:
                    section_end = section_start + match.start()
                    break

            experience_text = text[section_start:section_end]

        date_patterns = [
            r'(\d{2}/\d{4})\s*[-–a]\s*(\d{2}/\d{4}|atual|presente|current|atualmente)',
            r'(\d{2}/\d{2}/\d{4})\s*[-–a]\s*(\d{2}/\d{2}/\d{4}|atual|presente|current|atualmente)',
            r'(\d{4})\s*[-–a]\s*(\d{4}|atual|presente|current|atualmente)',
            r'(\w+[./]\d{4})\s*[-–a]\s*(\w+[./]\d{4}|atual|presente|current|atualmente)',
            r'(\w+\s+(?:de\s+)?\d{4})\s*[-–a]\s*(\w+\s+(?:de\s+)?\d{4}|atual|presente|current|atualmente)',
            r'(?:desde|from)\s+(\d{2}/\d{4}|\d{4})',
            r'(\d{2}\.\d{4})\s*[-–a]\s*(\d{2}\.\d{4}|atual|presente|current|atualmente)',
        ]

        lines = experience_text.split('\n')
        current_exp = None

        for line in lines:
            line = line.strip()

            if not line:
                if current_exp and current_exp.get('company'):
                    experiences.append(current_exp)
                    current_exp = None
                continue

            for pattern in date_patterns:
                date_match = re.search(pattern, line, re.IGNORECASE)
                if date_match:
                    if current_exp:
                        experiences.append(current_exp)

                    current_exp = {
                        "title": None,
                        "company": None,
                        "start_date": date_match.group(1),
                        "end_date": date_match.group(2),
                        "description": [],
                    }
                    break

            if current_exp:
                if not current_exp["title"]:
                    current_exp["title"] = line
                elif not current_exp["company"]:
                    current_exp["company"] = line
                else:
                    if line.startswith(('-', '•', '*', '–')):
                        line = line[1:].strip()
                    current_exp["description"].append(line)

        if current_exp and current_exp.get('company'):
            experiences.append(current_exp)

        for exp in experiences:
            exp["description"] = "\n".join(exp["description"])

        return experiences

    @staticmethod
    def extract_education(text: str) -> list[Dict[str, Any]]:
        """Extrai formacao academica"""
        education = []

        education_keywords = [
            'formação acadêmica',
            'formacao academica',
            'formação',
            'formacao',
            'educação',
            'educacao',
            'education',
            'academic background',
            'escolaridade',
        ]

        section_start = -1
        for keyword in education_keywords:
            pattern = rf'\n\s*{re.escape(keyword)}\s*\n'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                section_start = match.end()
                break

        if section_start == -1:
            return education

        next_section_keywords = [
            'experiência', 'experiencia', 'experience',
            'habilidades', 'skills', 'idiomas', 'languages',
            'certificações', 'certificacoes', 'projetos',
        ]

        section_end = len(text)
        for keyword in next_section_keywords:
            pattern = rf'\n\s*{re.escape(keyword)}\s*\n'
            match = re.search(pattern, text[section_start:], re.IGNORECASE)
            if match:
                section_end = section_start + match.start()
                break

        education_text = text[section_start:section_end]

        degree_patterns = [
            r'(bacharelado|graduação|graduacao|ensino superior|bachelor)',
            r'(mestrado|mestre|master)',
            r'(doutorado|phd|ph\.d)',
            r'(especialização|especializacao|pós-graduação|pos-graduacao|mba)',
            r'(técnico|tecnico|tecnólogo|tecnologo)',
            r'(ensino médio|ensino medio|segundo grau|2º grau)',
            r'(ensino fundamental|primeiro grau|1º grau)',
            r'(curso técnico|curso tecnico)',
            r'(engenharia)',
            r'(licenciatura)',
        ]

        lines = education_text.split('\n')

        for i, line in enumerate(lines):
            line = line.strip()

            if not line:
                continue

            for pattern in degree_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    edu_entry = {
                        "degree": line,
                        "institution": None,
                        "year": None,
                        "description": []
                    }

                    if i + 1 < len(lines):
                        edu_entry["institution"] = lines[i + 1].strip()

                    if i + 2 < len(lines):
                        year_match = re.search(r'\d{4}', lines[i + 2])
                        if year_match:
                            edu_entry["year"] = year_match.group()

                    education.append(edu_entry)
                    break

        return education

    @staticmethod
    def extract_skills(text: str) -> list[str]:
        """Extrai skills tecnicas e comportamentais"""
        skills = []

        skills_keywords = [
            'habilidades',
            'competências',
            'competencias',
            'skills',
            'conhecimentos',
            'tecnologias',
            'qualificações',
            'qualificacoes',
        ]

        section_start = -1
        for keyword in skills_keywords:
            pattern = rf'\n\s*{re.escape(keyword)}\s*\n'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                section_start = match.end()
                break

        if section_start == -1:
            return skills

        next_section_keywords = [
            'experiência', 'experiencia', 'formação', 'formacao',
            'idiomas', 'certificações', 'certificacoes', 'projetos',
        ]

        section_end = len(text)
        for keyword in next_section_keywords:
            pattern = rf'\n\s*{re.escape(keyword)}\s*\n'
            match = re.search(pattern, text[section_start:], re.IGNORECASE)
            if match:
                section_end = section_start + match.start()
                break

        skills_text = text[section_start:section_end]

        lines = skills_text.split('\n')

        for line in lines:
            line = line.strip()

            if not line:
                continue

            line = re.sub(r'^[-•*–]\s*', '', line)

            if ',' in line or '|' in line or ';' in line:
                separators = [',', '|', ';']
                for sep in separators:
                    if sep in line:
                        parts = [p.strip() for p in line.split(sep)]
                        skills.extend([p for p in parts if p and len(p) > 1])
                        break
            else:
                if len(line) > 1:
                    skills.append(line)

        return skills

    @staticmethod
    def extract_languages(text: str) -> list[Dict[str, str]]:
        """Extrai idiomas e niveis"""
        languages = []

        language_names = [
            'português', 'portugues', 'inglês', 'ingles', 'espanhol', 'francês', 'frances',
            'alemão', 'alemao', 'italiano', 'chinês', 'chines', 'japonês', 'japones',
            'coreano', 'árabe', 'arabe', 'libras',
            'portuguese', 'english', 'spanish', 'french', 'german',
            'italian', 'chinese', 'japanese', 'korean', 'arabic'
        ]

        levels = [
            'nativo', 'fluente', 'avançado', 'avancado', 'intermediário', 'intermediario',
            'básico', 'basico', 'iniciante',
            'native', 'fluent', 'advanced', 'intermediate', 'basic', 'beginner',
        ]

        for language in language_names:
            pattern = rf'{language}\s*[:\-–]?\s*({"|".join(levels)})?'
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for match in matches:
                lang_entry = {
                    "language": match.group().split(':')[0].split('-')[0].strip(),
                    "level": match.group(1) if match.group(1) else "Nao especificado"
                }
                # Evitar duplicatas
                if not any(l["language"].lower() == lang_entry["language"].lower()
                          for l in languages):
                    languages.append(lang_entry)

        return languages

    @staticmethod
    def extract_certifications(text: str) -> list[str]:
        """Extrai certificacoes"""
        certifications = []

        cert_keywords = [
            'certificações',
            'certificacoes',
            'certificados',
            'certifications',
            'cursos',
            'cursos complementares',
            'treinamentos',
        ]

        section_start = -1
        for keyword in cert_keywords:
            pattern = rf'\n\s*{re.escape(keyword)}\s*\n'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                section_start = match.end()
                break

        if section_start == -1:
            return certifications

        next_section_keywords = [
            'experiência', 'experiencia', 'formação', 'formacao',
            'habilidades', 'idiomas', 'projetos', 'dados pessoais',
        ]

        section_end = len(text)
        for keyword in next_section_keywords:
            pattern = rf'\n\s*{re.escape(keyword)}\s*\n'
            match = re.search(pattern, text[section_start:], re.IGNORECASE)
            if match:
                section_end = section_start + match.start()
                break

        cert_text = text[section_start:section_end]

        lines = cert_text.split('\n')

        for line in lines:
            line = line.strip()

            if not line or len(line) < 5:
                continue

            line = re.sub(r'^[-•*–]\s*', '', line)

            certifications.append(line)

        return certifications

    @staticmethod
    def extract_summary(text: str) -> Optional[str]:
        """Extrai resumo/objetivo profissional"""
        summary_keywords = [
            'resumo',
            'resumo profissional',
            'objetivo',
            'objetivo profissional',
            'sobre',
            'sobre mim',
            'perfil',
            'perfil profissional',
            'summary',
            'objective',
            'about',
            'profile',
        ]

        for keyword in summary_keywords:
            pattern = rf'\n\s*{re.escape(keyword)}\s*\n(.*?)\n\n'
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()

        return None

    # ================================================================
    # Campos Especificos: Producao e Logistica
    # ================================================================

    @staticmethod
    def extract_licenses(text: str) -> list[Dict[str, str]]:
        """
        Extrai habilitacoes e licencas

        - CNH (Carteira Nacional de Habilitacao) com categoria
        - MOPP (Movimentacao de Produtos Perigosos)
        - Curso de empilhadeira
        - Outras licencas
        """
        licenses = []

        # CNH com categoria
        cnh_patterns = [
            r'CNH\s*[:\-–]?\s*(?:categoria\s*)?([A-E](?:/[A-E])*(?:\s*[A-E])*)',
            r'(?:carteira\s+(?:de\s+)?(?:habilitação|habilitacao|motorista))\s*[:\-–]?\s*(?:categoria\s*)?([A-E](?:/[A-E])*)',
            r'(?:habilitação|habilitacao)\s*[:\-–]?\s*(?:categoria\s*)?([A-E](?:/[A-E])*)',
            r'(?:categoria)\s*[:\-–]?\s*([A-E](?:/[A-E])*)',
        ]

        for pattern in cnh_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                category = match.group(1).upper().strip()
                licenses.append({
                    "type": "CNH",
                    "category": category,
                    "description": f"Carteira Nacional de Habilitacao - Categoria {category}"
                })
                break

        # Verificar menção simples de CNH
        if not licenses:
            if re.search(r'\bCNH\b', text):
                licenses.append({
                    "type": "CNH",
                    "category": "nao especificada",
                    "description": "Carteira Nacional de Habilitacao"
                })

        # MOPP
        if re.search(r'\bMOPP\b', text, re.IGNORECASE):
            licenses.append({
                "type": "MOPP",
                "category": None,
                "description": "Movimentacao de Produtos Perigosos"
            })

        # Curso de empilhadeira
        empilhadeira_patterns = [
            r'(?:curso\s+(?:de\s+)?)?(?:operador\s+(?:de\s+)?)?empilhadeira',
            r'empilhadeirista',
            r'operação\s+(?:de\s+)?empilhadeira',
        ]
        for pattern in empilhadeira_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                licenses.append({
                    "type": "Empilhadeira",
                    "category": None,
                    "description": "Operador de Empilhadeira"
                })
                break

        # Ponte rolante
        if re.search(r'ponte\s+rolante', text, re.IGNORECASE):
            licenses.append({
                "type": "Ponte Rolante",
                "category": None,
                "description": "Operador de Ponte Rolante"
            })

        return licenses

    @staticmethod
    def extract_safety_certifications(text: str) -> list[Dict[str, str]]:
        """
        Extrai certificacoes de seguranca do trabalho

        - NRs (Normas Regulamentadoras)
        - CIPA
        - Brigadista
        - Trabalho em altura
        - Espaco confinado
        """
        safety_certs = []

        # NRs especificas
        nr_patterns = [
            (r'NR[\s-]?0?5\b', "NR-05", "CIPA - Comissao Interna de Prevencao de Acidentes"),
            (r'NR[\s-]?0?6\b', "NR-06", "Equipamento de Protecao Individual (EPI)"),
            (r'NR[\s-]?10\b', "NR-10", "Seguranca em Instalacoes e Servicos em Eletricidade"),
            (r'NR[\s-]?11\b', "NR-11", "Transporte, Movimentacao, Armazenagem e Manuseio de Materiais"),
            (r'NR[\s-]?12\b', "NR-12", "Seguranca no Trabalho em Maquinas e Equipamentos"),
            (r'NR[\s-]?13\b', "NR-13", "Caldeiras, Vasos de Pressao e Tubulacoes"),
            (r'NR[\s-]?17\b', "NR-17", "Ergonomia"),
            (r'NR[\s-]?18\b', "NR-18", "Seguranca e Saude no Trabalho na Industria da Construcao"),
            (r'NR[\s-]?20\b', "NR-20", "Seguranca com Inflamaveis e Combustiveis"),
            (r'NR[\s-]?33\b', "NR-33", "Seguranca e Saude nos Trabalhos em Espacos Confinados"),
            (r'NR[\s-]?35\b', "NR-35", "Trabalho em Altura"),
        ]

        for pattern, nr_code, description in nr_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                safety_certs.append({
                    "code": nr_code,
                    "description": description
                })

        # Generico - capturar qualquer NR
        generic_nr = re.findall(r'NR[\s-]?(\d{1,2})\b', text, re.IGNORECASE)
        for nr_num in generic_nr:
            nr_code = f"NR-{int(nr_num):02d}"
            if not any(s["code"] == nr_code for s in safety_certs):
                safety_certs.append({
                    "code": nr_code,
                    "description": f"Norma Regulamentadora {nr_code}"
                })

        # CIPA
        if re.search(r'\bCIPA\b', text) and not any(s["code"] == "NR-05" for s in safety_certs):
            safety_certs.append({
                "code": "CIPA",
                "description": "Comissao Interna de Prevencao de Acidentes"
            })

        # Brigadista / Brigada de incendio
        if re.search(r'brigad(?:ist|a\s+de\s+incêndio|a\s+de\s+incendio)', text, re.IGNORECASE):
            safety_certs.append({
                "code": "Brigadista",
                "description": "Brigada de Incendio"
            })

        # Primeiros socorros
        if re.search(r'primeiros\s+socorros', text, re.IGNORECASE):
            safety_certs.append({
                "code": "Primeiros Socorros",
                "description": "Curso de Primeiros Socorros"
            })

        # Trabalho em altura (mesmo sem NR-35 explicita)
        if re.search(r'trabalho\s+em\s+altura', text, re.IGNORECASE):
            if not any(s["code"] == "NR-35" for s in safety_certs):
                safety_certs.append({
                    "code": "NR-35",
                    "description": "Trabalho em Altura"
                })

        # Espaco confinado (mesmo sem NR-33 explicita)
        if re.search(r'espa[çc]o\s+confinado', text, re.IGNORECASE):
            if not any(s["code"] == "NR-33" for s in safety_certs):
                safety_certs.append({
                    "code": "NR-33",
                    "description": "Seguranca em Espacos Confinados"
                })

        return safety_certs

    @staticmethod
    def extract_equipment_skills(text: str) -> list[Dict[str, str]]:
        """
        Extrai habilidades com equipamentos e maquinas

        - Empilhadeira (tipos)
        - CNC, Torno, Fresa
        - Ponte rolante
        - Equipamentos de medicao
        - Ferramentas especificas
        """
        equipment = []

        # Mapeamento de equipamentos
        equipment_patterns = {
            # Movimentacao de materiais
            "Empilhadeira": [
                r'empilhadeira(?:\s+(?:eletrica|a\s+gas|contrabalancada|retratil|trilateral))?',
            ],
            "Paleteira": [r'paleteira', r'transpaleteira', r'carrinho\s+hidraulico'],
            "Ponte Rolante": [r'ponte\s+rolante', r'talha'],

            # Usinagem
            "Torno CNC": [r'torno\s+cnc', r'torno\s+mecanico'],
            "Fresa CNC": [r'fresa\s+cnc', r'fresadora', r'centro\s+de\s+usinagem'],
            "CNC": [r'\bcnc\b(?!\s+(?:torno|fresa))'],
            "Retifica": [r'retifica(?:dora)?'],

            # Soldagem
            "Solda MIG": [r'solda(?:gem)?\s+mig', r'mig/mag'],
            "Solda TIG": [r'solda(?:gem)?\s+tig'],
            "Solda Eletrica": [r'solda(?:gem)?\s+(?:eletrica|eletrodo)', r'soldador'],

            # Injecao/Prensa
            "Injetora": [r'injetora', r'injecao\s+(?:plastica)?', r'maquina\s+injetora'],
            "Prensa": [r'prensa(?:\s+(?:hidraulica|mecanica|excêntrica))?'],
            "Extrusora": [r'extrusora', r'extrusao'],

            # Medicao
            "Paquimetro": [r'paquimetro', r'paquímetro'],
            "Micrometro": [r'micrometro', r'micrômetro'],
            "Relogio Comparador": [r'relogio\s+comparador'],
            "Projetor de Perfil": [r'projetor\s+de\s+perfil'],
            "Trena": [r'\btrena\b'],
            "Calibrador": [r'calibrador', r'calibracao'],

            # Outros
            "Compressor": [r'compressor'],
            "Esmeril": [r'esmeril', r'esmerilhadeira'],
            "Furadeira": [r'furadeira(?:\s+(?:de\s+bancada|radial))?'],
        }

        text_lower = text.lower()

        for equip_name, patterns in equipment_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    equipment.append({
                        "name": equip_name,
                        "detail": match.group().strip()
                    })
                    break

        return equipment

    @staticmethod
    def extract_availability(text: str) -> Dict[str, Any]:
        """
        Extrai informacoes de disponibilidade

        - Turnos (1o, 2o, 3o turno)
        - Disponibilidade para viagens
        - Disponibilidade para mudanca
        - Horario
        """
        availability = {
            "shifts": [],
            "travel": None,
            "relocation": None,
            "schedule": None,
            "immediate_start": None,
        }

        text_lower = text.lower()

        # Turnos
        shift_patterns = [
            (r'1[ºo°]?\s*turno', "1o turno"),
            (r'2[ºo°]?\s*turno', "2o turno"),
            (r'3[ºo°]?\s*turno', "3o turno"),
            (r'turno\s+(?:da\s+)?manhã', "1o turno"),
            (r'turno\s+(?:da\s+)?tarde', "2o turno"),
            (r'turno\s+(?:da\s+)?noite', "3o turno"),
            (r'turno\s+administrativo', "administrativo"),
            (r'escala\s+(?:6x1|12x36|5x2|5x1|4x2)', None),
            (r'todos\s+(?:os\s+)?turnos', "todos"),
            (r'qualquer\s+turno', "todos"),
        ]

        for pattern, shift_name in shift_patterns:
            match = re.search(pattern, text_lower)
            if match:
                if shift_name:
                    availability["shifts"].append(shift_name)
                else:
                    availability["shifts"].append(match.group().strip())

        # Viagens
        if re.search(r'disponibilidade\s+para\s+viag', text_lower):
            availability["travel"] = True
        elif re.search(r'(?:sem|nao\s+(?:tem|possui))\s+disponibilidade\s+para\s+viag', text_lower):
            availability["travel"] = False

        # Mudanca
        if re.search(r'disponibilidade\s+para\s+mudan[çc]a', text_lower):
            availability["relocation"] = True

        # Disponibilidade imediata
        if re.search(r'disponibilidade\s+imediata|disponível\s+imediatamente|inicio\s+imediato',
                      text_lower):
            availability["immediate_start"] = True

        return availability

    @staticmethod
    def extract_erp_systems(text: str) -> list[Dict[str, str]]:
        """
        Extrai sistemas ERP e software industrial mencionados

        - SAP (modulos)
        - TOTVS/Protheus
        - Oracle
        - WMS
        - MES
        """
        systems = []

        erp_patterns = {
            "SAP": {
                "base": r'\bSAP\b',
                "modules": [
                    (r'SAP\s+(?:modulo\s+)?PP', "PP - Planejamento de Producao"),
                    (r'SAP\s+(?:modulo\s+)?MM', "MM - Gestao de Materiais"),
                    (r'SAP\s+(?:modulo\s+)?SD', "SD - Vendas e Distribuicao"),
                    (r'SAP\s+(?:modulo\s+)?WM', "WM - Warehouse Management"),
                    (r'SAP\s+(?:modulo\s+)?QM', "QM - Gestao da Qualidade"),
                    (r'SAP\s+(?:modulo\s+)?PM', "PM - Manutencao"),
                    (r'SAP\s+(?:modulo\s+)?FI', "FI - Financeiro"),
                    (r'SAP\s+(?:modulo\s+)?CO', "CO - Controladoria"),
                    (r'SAP\s+(?:modulo\s+)?HR', "HR - Recursos Humanos"),
                ]
            },
            "TOTVS": {
                "base": r'\b(?:TOTVS|Protheus|Datasul|Microsiga)\b',
                "modules": []
            },
            "Oracle ERP": {
                "base": r'\bOracle\s+(?:ERP|EBS|Cloud)\b',
                "modules": []
            },
            "Senior": {
                "base": r'\bSenior\s+(?:Sistemas|ERP)?\b',
                "modules": []
            },
        }

        for system_name, config in erp_patterns.items():
            if re.search(config["base"], text, re.IGNORECASE):
                entry = {
                    "system": system_name,
                    "modules": []
                }

                for pattern, module_desc in config.get("modules", []):
                    if re.search(pattern, text, re.IGNORECASE):
                        entry["modules"].append(module_desc)

                systems.append(entry)

        # WMS
        if re.search(r'\bWMS\b', text, re.IGNORECASE):
            systems.append({"system": "WMS", "modules": ["Warehouse Management System"]})

        # MES
        if re.search(r'\bMES\b', text):
            systems.append({"system": "MES", "modules": ["Manufacturing Execution System"]})

        # Excel avancado (comum em producao)
        if re.search(r'excel\s+avan[çc]ado|VBA|macros?\s+excel|tabela\s+din[aâ]mica',
                      text, re.IGNORECASE):
            systems.append({"system": "Excel Avancado", "modules": ["Macros/VBA/Tabelas Dinamicas"]})

        return systems
