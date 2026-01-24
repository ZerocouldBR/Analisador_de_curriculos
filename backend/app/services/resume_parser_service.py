import re
from typing import Optional, Dict, Any
from datetime import datetime
from dateutil.parser import parse as parse_date


class ResumeParserService:
    """
    Serviço para parsing estruturado de currículos

    Extrai informações como:
    - Dados pessoais (nome, email, telefone)
    - Experiências profissionais
    - Formação acadêmica
    - Skills
    - Idiomas
    - Certificações
    """

    @staticmethod
    def parse_resume(text: str) -> Dict[str, Any]:
        """
        Faz parsing completo de um currículo

        Args:
            text: Texto do currículo

        Returns:
            Dict com informações estruturadas
        """
        resume_data = {
            "personal_info": ResumeParserService.extract_personal_info(text),
            "experiences": ResumeParserService.extract_experiences(text),
            "education": ResumeParserService.extract_education(text),
            "skills": ResumeParserService.extract_skills(text),
            "languages": ResumeParserService.extract_languages(text),
            "certifications": ResumeParserService.extract_certifications(text),
            "summary": ResumeParserService.extract_summary(text),
        }

        return resume_data

    @staticmethod
    def extract_personal_info(text: str) -> Dict[str, Optional[str]]:
        """Extrai informações pessoais"""
        info = {
            "name": None,
            "email": None,
            "phone": None,
            "location": None,
            "linkedin": None,
            "github": None,
        }

        # Email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, text)
        if email_match:
            info["email"] = email_match.group()

        # Telefone (formatos brasileiros)
        phone_patterns = [
            r'\+55\s*\(?\d{2}\)?\s*\d{4,5}-?\d{4}',
            r'\(?\d{2}\)?\s*\d{4,5}-?\d{4}',
            r'\d{2}\s*\d{4,5}-?\d{4}',
        ]

        for pattern in phone_patterns:
            phone_match = re.search(pattern, text)
            if phone_match:
                info["phone"] = phone_match.group().strip()
                break

        # LinkedIn
        linkedin_pattern = r'linkedin\.com/in/[\w-]+'
        linkedin_match = re.search(linkedin_pattern, text, re.IGNORECASE)
        if linkedin_match:
            info["linkedin"] = f"https://{linkedin_match.group()}"

        # GitHub
        github_pattern = r'github\.com/[\w-]+'
        github_match = re.search(github_pattern, text, re.IGNORECASE)
        if github_match:
            info["github"] = f"https://{github_match.group()}"

        # Nome (primeira linha não vazia geralmente é o nome)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if lines:
            # Nome geralmente está nas primeiras linhas
            for line in lines[:5]:
                # Nome não deve ter números ou caracteres especiais demais
                if len(line) > 5 and len(line) < 50:
                    if not re.search(r'\d', line) and not re.search(r'[!@#$%^&*()]', line):
                        info["name"] = line
                        break

        # Localização (procurar por padrões de cidade/estado)
        location_patterns = [
            r'([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç\s]+),\s*([A-Z]{2})',
            r'([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç\s]+)\s+-\s+([A-Z]{2})',
        ]

        for pattern in location_patterns:
            location_match = re.search(pattern, text)
            if location_match:
                info["location"] = location_match.group().strip()
                break

        return info

    @staticmethod
    def extract_experiences(text: str) -> list[Dict[str, Any]]:
        """
        Extrai experiências profissionais

        Procura por seções como "Experiência", "Experience", etc.
        """
        experiences = []

        # Encontrar seção de experiência
        experience_keywords = [
            'experiência profissional',
            'experiência',
            'histórico profissional',
            'experience',
            'work experience',
            'employment',
        ]

        # Procurar início da seção
        section_start = -1
        for keyword in experience_keywords:
            pattern = rf'\n\s*{re.escape(keyword)}\s*\n'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                section_start = match.end()
                break

        if section_start == -1:
            return experiences

        # Encontrar fim da seção (próxima seção)
        next_section_keywords = [
            'formação', 'educação', 'education', 'habilidades',
            'skills', 'idiomas', 'languages', 'certificações',
        ]

        section_end = len(text)
        for keyword in next_section_keywords:
            pattern = rf'\n\s*{re.escape(keyword)}\s*\n'
            match = re.search(pattern, text[section_start:], re.IGNORECASE)
            if match:
                section_end = section_start + match.start()
                break

        # Extrair texto da seção
        experience_text = text[section_start:section_end]

        # Padrões de datas
        date_patterns = [
            r'(\d{2}/\d{4})\s*-\s*(\d{2}/\d{4}|atual|presente|current)',
            r'(\d{4})\s*-\s*(\d{4}|atual|presente|current)',
            r'(\w+\s+\d{4})\s*-\s*(\w+\s+\d{4}|atual|presente|current)',
        ]

        # Dividir em blocos de experiência
        lines = experience_text.split('\n')

        current_exp = None

        for line in lines:
            line = line.strip()

            if not line:
                if current_exp and current_exp.get('company'):
                    experiences.append(current_exp)
                    current_exp = None
                continue

            # Procurar por datas
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

            # Se estamos em uma experiência atual
            if current_exp:
                # Se não tem cargo ainda, essa linha é o cargo
                if not current_exp["title"]:
                    current_exp["title"] = line
                # Se não tem empresa ainda, essa linha é a empresa
                elif not current_exp["company"]:
                    current_exp["company"] = line
                # Senão, é descrição
                else:
                    if line.startswith(('-', '•', '*')):
                        line = line[1:].strip()
                    current_exp["description"].append(line)

        # Adicionar última experiência
        if current_exp and current_exp.get('company'):
            experiences.append(current_exp)

        # Converter descrições de lista para string
        for exp in experiences:
            exp["description"] = "\n".join(exp["description"])

        return experiences

    @staticmethod
    def extract_education(text: str) -> list[Dict[str, Any]]:
        """Extrai formação acadêmica"""
        education = []

        # Encontrar seção de educação
        education_keywords = [
            'formação acadêmica',
            'formação',
            'educação',
            'education',
            'academic background',
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

        # Encontrar fim da seção
        next_section_keywords = [
            'experiência', 'experience', 'habilidades', 'skills',
            'idiomas', 'languages', 'certificações', 'projetos',
        ]

        section_end = len(text)
        for keyword in next_section_keywords:
            pattern = rf'\n\s*{re.escape(keyword)}\s*\n'
            match = re.search(pattern, text[section_start:], re.IGNORECASE)
            if match:
                section_end = section_start + match.start()
                break

        education_text = text[section_start:section_end]

        # Graus acadêmicos
        degree_patterns = [
            r'(bacharelado|graduação|ensino superior|bachelor)',
            r'(mestrado|mestre|master)',
            r'(doutorado|phd|ph\.d)',
            r'(especialização|pós-graduação|mba)',
            r'(técnico|tecnólogo)',
        ]

        lines = education_text.split('\n')

        for i, line in enumerate(lines):
            line = line.strip()

            if not line:
                continue

            # Procurar por grau acadêmico
            for pattern in degree_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    edu_entry = {
                        "degree": line,
                        "institution": None,
                        "year": None,
                        "description": []
                    }

                    # Próximas linhas são instituição e ano
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
        """Extrai skills técnicas e comportamentais"""
        skills = []

        # Encontrar seção de skills
        skills_keywords = [
            'habilidades',
            'competências',
            'skills',
            'conhecimentos',
            'tecnologias',
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

        # Próxima seção
        next_section_keywords = [
            'experiência', 'formação', 'idiomas', 'certificações', 'projetos',
        ]

        section_end = len(text)
        for keyword in next_section_keywords:
            pattern = rf'\n\s*{re.escape(keyword)}\s*\n'
            match = re.search(pattern, text[section_start:], re.IGNORECASE)
            if match:
                section_end = section_start + match.start()
                break

        skills_text = text[section_start:section_end]

        # Extrair skills
        lines = skills_text.split('\n')

        for line in lines:
            line = line.strip()

            if not line:
                continue

            # Remover marcadores
            line = re.sub(r'^[-•*]\s*', '', line)

            # Dividir por vírgulas ou pipes
            if ',' in line or '|' in line:
                separator = ',' if ',' in line else '|'
                parts = [p.strip() for p in line.split(separator)]
                skills.extend([p for p in parts if p])
            else:
                skills.append(line)

        return skills

    @staticmethod
    def extract_languages(text: str) -> list[Dict[str, str]]:
        """Extrai idiomas e níveis"""
        languages = []

        # Idiomas comuns
        language_names = [
            'português', 'inglês', 'espanhol', 'francês', 'alemão',
            'italiano', 'chinês', 'japonês', 'coreano', 'árabe',
            'portuguese', 'english', 'spanish', 'french', 'german',
            'italian', 'chinese', 'japanese', 'korean', 'arabic'
        ]

        # Níveis
        levels = [
            'nativo', 'fluente', 'avançado', 'intermediário', 'básico',
            'native', 'fluent', 'advanced', 'intermediate', 'basic',
        ]

        # Procurar por menções a idiomas
        for language in language_names:
            pattern = rf'{language}\s*[:-]?\s*({"|".join(levels)})?'
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for match in matches:
                lang_entry = {
                    "language": match.group().split(':')[0].strip(),
                    "level": match.group(1) if match.group(1) else "Não especificado"
                }
                languages.append(lang_entry)

        return languages

    @staticmethod
    def extract_certifications(text: str) -> list[str]:
        """Extrai certificações"""
        certifications = []

        # Encontrar seção de certificações
        cert_keywords = [
            'certificações',
            'certificados',
            'certifications',
            'cursos',
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

        # Próxima seção
        next_section_keywords = [
            'experiência', 'formação', 'habilidades', 'idiomas', 'projetos',
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

            # Remover marcadores
            line = re.sub(r'^[-•*]\s*', '', line)

            certifications.append(line)

        return certifications

    @staticmethod
    def extract_summary(text: str) -> Optional[str]:
        """Extrai resumo/objetivo profissional"""
        summary_keywords = [
            'resumo',
            'objetivo',
            'sobre',
            'perfil',
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
