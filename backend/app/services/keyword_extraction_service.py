"""
Serviço avançado de extração de palavras-chave para currículos

Utiliza múltiplas técnicas:
- TF-IDF para termos relevantes
- N-grams para expressões compostas
- Extração de entidades nomeadas (empresas, tecnologias, certificações)
- Categorização por tipo (skill técnica, soft skill, ferramenta, etc.)
"""
import re
from typing import Dict, List, Any, Set, Optional
from collections import Counter
import math


class KeywordExtractionService:
    """
    Serviço para extração avançada de palavras-chave de currículos

    Gera índices semânticos para melhorar a localização pelo LLM
    """

    # Categorias de palavras-chave para indexação
    SKILL_CATEGORIES = {
        "programming_languages": [
            "python", "java", "javascript", "typescript", "c++", "c#", "ruby", "go", "golang",
            "rust", "php", "swift", "kotlin", "scala", "r", "perl", "lua", "dart", "elixir",
            "clojure", "haskell", "erlang", "f#", "objective-c", "assembly", "sql", "plsql",
            "t-sql", "bash", "shell", "powershell", "vba", "matlab", "cobol", "fortran"
        ],
        "frameworks": [
            "django", "flask", "fastapi", "spring", "spring boot", "react", "angular", "vue",
            "next.js", "nuxt", "express", "nestjs", "rails", "laravel", "symfony", "asp.net",
            ".net core", "node.js", "tensorflow", "pytorch", "keras", "scikit-learn", "pandas",
            "numpy", "spark", "hadoop", "airflow", "celery", "redux", "mobx", "svelte",
            "gatsby", "electron", "react native", "flutter", "ionic", "xamarin"
        ],
        "databases": [
            "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "oracle", "sql server",
            "sqlite", "cassandra", "dynamodb", "couchdb", "neo4j", "influxdb", "timescaledb",
            "mariadb", "firebase", "supabase", "cockroachdb", "yugabyte", "clickhouse"
        ],
        "cloud_platforms": [
            "aws", "azure", "gcp", "google cloud", "heroku", "digitalocean", "linode",
            "vercel", "netlify", "cloudflare", "oracle cloud", "ibm cloud", "alibaba cloud"
        ],
        "devops_tools": [
            "docker", "kubernetes", "terraform", "ansible", "jenkins", "gitlab ci", "github actions",
            "circleci", "travis ci", "argo", "helm", "prometheus", "grafana", "datadog",
            "new relic", "splunk", "elk stack", "logstash", "kibana", "vagrant", "puppet",
            "chef", "saltstack", "packer"
        ],
        "soft_skills": [
            "liderança", "comunicação", "trabalho em equipe", "proatividade", "criatividade",
            "resolução de problemas", "pensamento crítico", "adaptabilidade", "organização",
            "gestão de tempo", "negociação", "apresentação", "mentoria", "colaboração",
            "empatia", "resiliência", "iniciativa", "autonomia", "leadership", "communication",
            "teamwork", "problem solving", "critical thinking", "adaptability"
        ],
        "methodologies": [
            "agile", "scrum", "kanban", "lean", "xp", "extreme programming", "devops", "devsecops",
            "ci/cd", "tdd", "bdd", "ddd", "solid", "clean code", "clean architecture",
            "microservices", "monolith", "serverless", "event-driven", "cqrs", "event sourcing"
        ],
        "certifications": [
            "aws certified", "azure certified", "gcp certified", "pmp", "scrum master",
            "product owner", "cissp", "ceh", "comptia", "cisco", "ccna", "ccnp",
            "oracle certified", "microsoft certified", "kubernetes certified", "cka", "ckad",
            "terraform certified", "hashicorp certified", "linux+", "lpic"
        ],
        "domains": [
            "machine learning", "deep learning", "inteligência artificial", "artificial intelligence",
            "data science", "ciência de dados", "big data", "analytics", "business intelligence",
            "bi", "etl", "data engineering", "engenharia de dados", "nlp", "processamento de linguagem",
            "computer vision", "visão computacional", "iot", "internet das coisas", "blockchain",
            "web3", "fintech", "healthtech", "edtech", "e-commerce", "saas", "api", "rest",
            "graphql", "grpc", "websocket", "microservices", "microsserviços"
        ]
    }

    # Stopwords em português e inglês para filtrar
    STOPWORDS = {
        "a", "o", "e", "de", "da", "do", "em", "para", "com", "por", "que", "um", "uma",
        "os", "as", "no", "na", "se", "ou", "mais", "como", "mas", "foi", "aos", "das",
        "dos", "seu", "sua", "ser", "ter", "está", "são", "muito", "também", "já",
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of",
        "with", "by", "from", "as", "is", "was", "are", "were", "been", "be", "have",
        "has", "had", "do", "does", "did", "will", "would", "could", "should", "may",
        "might", "must", "shall", "can", "this", "that", "these", "those", "it", "its"
    }

    @classmethod
    def extract_keywords(cls, text: str, resume_data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Extrai palavras-chave estruturadas de um texto de currículo

        Args:
            text: Texto completo do currículo
            resume_data: Dados parseados do currículo (opcional)

        Returns:
            Dict com palavras-chave categorizadas e índices
        """
        result = {
            "keywords": [],
            "keywords_by_category": {},
            "technical_skills": [],
            "soft_skills": [],
            "tools_and_frameworks": [],
            "certifications": [],
            "domains": [],
            "companies": [],
            "education_keywords": [],
            "experience_keywords": [],
            "tfidf_terms": [],
            "ngrams": [],
            "search_index": "",
            "relevance_scores": {}
        }

        # Normalizar texto
        normalized_text = cls._normalize_text(text)

        # Extrair por categoria
        for category, keywords_list in cls.SKILL_CATEGORIES.items():
            found = cls._find_keywords_in_text(normalized_text, keywords_list)
            if found:
                result["keywords_by_category"][category] = list(found)
                result["keywords"].extend(found)

                # Distribuir nas categorias principais
                if category in ["programming_languages", "frameworks", "databases"]:
                    result["technical_skills"].extend(found)
                elif category == "soft_skills":
                    result["soft_skills"].extend(found)
                elif category in ["devops_tools", "cloud_platforms"]:
                    result["tools_and_frameworks"].extend(found)
                elif category == "certifications":
                    result["certifications"].extend(found)
                elif category == "domains":
                    result["domains"].extend(found)

        # Extrair n-grams relevantes (2 e 3 palavras)
        ngrams = cls._extract_ngrams(normalized_text, [2, 3])
        result["ngrams"] = ngrams[:50]  # Top 50 n-grams

        # Calcular TF-IDF dos termos
        tfidf_terms = cls._calculate_tfidf(normalized_text)
        result["tfidf_terms"] = tfidf_terms[:30]  # Top 30 termos TF-IDF

        # Extrair empresas mencionadas (padrões comuns)
        companies = cls._extract_companies(text)
        result["companies"] = companies

        # Processar dados parseados se disponíveis
        if resume_data:
            # Keywords de experiência
            if resume_data.get("experiences"):
                for exp in resume_data["experiences"]:
                    if exp.get("title"):
                        result["experience_keywords"].append(exp["title"].lower())
                    if exp.get("company"):
                        result["companies"].append(exp["company"])

            # Keywords de educação
            if resume_data.get("education"):
                for edu in resume_data["education"]:
                    if edu.get("degree"):
                        result["education_keywords"].append(edu["degree"].lower())
                    if edu.get("institution"):
                        result["education_keywords"].append(edu["institution"].lower())

            # Skills explícitas
            if resume_data.get("skills"):
                for skill in resume_data["skills"]:
                    skill_lower = skill.lower().strip()
                    if skill_lower and skill_lower not in result["keywords"]:
                        result["keywords"].append(skill_lower)

        # Remover duplicatas
        result["keywords"] = list(set(result["keywords"]))
        result["technical_skills"] = list(set(result["technical_skills"]))
        result["soft_skills"] = list(set(result["soft_skills"]))
        result["tools_and_frameworks"] = list(set(result["tools_and_frameworks"]))
        result["companies"] = list(set(result["companies"]))

        # Calcular scores de relevância
        result["relevance_scores"] = cls._calculate_relevance_scores(result, normalized_text)

        # Criar índice de busca otimizado para LLM
        result["search_index"] = cls._create_search_index(result)

        return result

    @classmethod
    def _normalize_text(cls, text: str) -> str:
        """Normaliza texto para extração"""
        # Converter para minúsculas
        text = text.lower()
        # Remover caracteres especiais mantendo espaços
        text = re.sub(r'[^\w\sáéíóúàèìòùâêîôûãõç]', ' ', text)
        # Remover múltiplos espaços
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    @classmethod
    def _find_keywords_in_text(cls, text: str, keywords: List[str]) -> Set[str]:
        """Encontra palavras-chave no texto"""
        found = set()
        for keyword in keywords:
            # Busca por palavra completa
            pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
            if re.search(pattern, text, re.IGNORECASE):
                found.add(keyword.lower())
        return found

    @classmethod
    def _extract_ngrams(cls, text: str, ns: List[int] = [2, 3]) -> List[Dict[str, Any]]:
        """Extrai n-grams mais frequentes"""
        words = [w for w in text.split() if w not in cls.STOPWORDS and len(w) > 2]

        all_ngrams = []

        for n in ns:
            ngrams = []
            for i in range(len(words) - n + 1):
                ngram = ' '.join(words[i:i+n])
                ngrams.append(ngram)

            # Contar frequências
            counter = Counter(ngrams)

            for ngram, count in counter.most_common(25):
                if count >= 2:  # Apenas n-grams que aparecem 2+ vezes
                    all_ngrams.append({
                        "term": ngram,
                        "count": count,
                        "n": n
                    })

        # Ordenar por contagem
        all_ngrams.sort(key=lambda x: x["count"], reverse=True)
        return all_ngrams

    @classmethod
    def _calculate_tfidf(cls, text: str) -> List[Dict[str, Any]]:
        """
        Calcula TF-IDF simplificado para termos no documento

        Como temos apenas um documento, usamos log-normalization no TF
        e IDF fixo baseado em raridade do termo
        """
        words = [w for w in text.split() if w not in cls.STOPWORDS and len(w) > 2]
        word_count = Counter(words)
        total_words = len(words)

        tfidf_scores = []

        for word, count in word_count.items():
            # TF: Log normalization
            tf = 1 + math.log(count) if count > 0 else 0

            # IDF aproximado baseado na raridade do termo
            # Termos técnicos têm IDF maior
            idf = 1.0
            word_lower = word.lower()

            # Aumentar IDF para termos técnicos
            for category, keywords_list in cls.SKILL_CATEGORIES.items():
                if word_lower in [k.lower() for k in keywords_list]:
                    idf = 2.5
                    break

            # Termos longos tendem a ser mais específicos
            if len(word) > 8:
                idf *= 1.2

            tfidf = tf * idf

            tfidf_scores.append({
                "term": word,
                "tf": round(tf, 3),
                "idf": round(idf, 3),
                "tfidf": round(tfidf, 3),
                "count": count
            })

        # Ordenar por TF-IDF
        tfidf_scores.sort(key=lambda x: x["tfidf"], reverse=True)
        return tfidf_scores

    @classmethod
    def _extract_companies(cls, text: str) -> List[str]:
        """Extrai nomes de empresas do texto"""
        companies = []

        # Padrões comuns de empresas
        patterns = [
            r'(?:na|at|@|em)\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]*)*)',
            r'([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]*)*)\s+(?:Ltda|S\.A\.|Inc|Corp|LLC|Ltd)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if len(match) > 3:
                    companies.append(match.strip())

        return list(set(companies))[:20]  # Limitar a 20 empresas

    @classmethod
    def _calculate_relevance_scores(cls, extracted: Dict, text: str) -> Dict[str, float]:
        """Calcula scores de relevância para cada categoria"""
        scores = {}
        text_len = len(text) if text else 1

        # Score baseado na quantidade e cobertura de cada categoria
        for category, keywords in extracted["keywords_by_category"].items():
            if keywords:
                # Base score: quantidade de keywords
                base_score = len(keywords) * 10

                # Bonus por cobertura no texto
                coverage_bonus = 0
                for kw in keywords:
                    count = text.lower().count(kw.lower())
                    coverage_bonus += min(count * 2, 10)  # Max 10 pontos por keyword

                scores[category] = min(base_score + coverage_bonus, 100)

        # Score geral
        total_keywords = len(extracted["keywords"])
        scores["overall"] = min(total_keywords * 5, 100)

        return scores

    @classmethod
    def _create_search_index(cls, extracted: Dict) -> str:
        """
        Cria um índice de busca otimizado para consultas LLM

        Formato estruturado que facilita a localização semântica
        """
        parts = []

        # Header com resumo
        parts.append("=== INDICE DE PALAVRAS-CHAVE DO CURRICULO ===")
        parts.append("")

        # Skills técnicas
        if extracted["technical_skills"]:
            parts.append(f"[SKILLS TECNICAS]: {', '.join(extracted['technical_skills'])}")

        # Soft skills
        if extracted["soft_skills"]:
            parts.append(f"[SOFT SKILLS]: {', '.join(extracted['soft_skills'])}")

        # Ferramentas
        if extracted["tools_and_frameworks"]:
            parts.append(f"[FERRAMENTAS]: {', '.join(extracted['tools_and_frameworks'])}")

        # Certificações
        if extracted["certifications"]:
            parts.append(f"[CERTIFICACOES]: {', '.join(extracted['certifications'])}")

        # Domínios
        if extracted["domains"]:
            parts.append(f"[DOMINIOS]: {', '.join(extracted['domains'])}")

        # Empresas
        if extracted["companies"]:
            parts.append(f"[EMPRESAS]: {', '.join(extracted['companies'][:10])}")

        # Categorias detalhadas
        parts.append("")
        parts.append("=== DETALHAMENTO POR CATEGORIA ===")

        for category, keywords in extracted["keywords_by_category"].items():
            if keywords:
                category_name = category.replace("_", " ").upper()
                parts.append(f"[{category_name}]: {', '.join(keywords)}")

        # N-grams relevantes
        if extracted["ngrams"]:
            top_ngrams = [ng["term"] for ng in extracted["ngrams"][:10]]
            parts.append(f"[EXPRESSOES FREQUENTES]: {', '.join(top_ngrams)}")

        # TF-IDF terms
        if extracted["tfidf_terms"]:
            top_terms = [t["term"] for t in extracted["tfidf_terms"][:10]]
            parts.append(f"[TERMOS RELEVANTES]: {', '.join(top_terms)}")

        parts.append("")
        parts.append("=== FIM DO INDICE ===")

        return "\n".join(parts)

    @classmethod
    def create_chunk_metadata(
        cls,
        section: str,
        content: str,
        keywords: Dict[str, Any],
        chunk_index: int,
        total_chunks: int
    ) -> Dict[str, Any]:
        """
        Cria metadados enriquecidos para um chunk

        Args:
            section: Tipo de seção do chunk
            content: Conteúdo do chunk
            keywords: Keywords extraídas do documento completo
            chunk_index: Índice do chunk no documento
            total_chunks: Total de chunks no documento

        Returns:
            Dict com metadados estruturados
        """
        # Extrair keywords específicas deste chunk
        chunk_keywords = cls.extract_keywords(content)

        metadata = {
            "section": section,
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
            "chunk_position": f"{chunk_index + 1}/{total_chunks}",

            # Keywords do chunk
            "chunk_keywords": chunk_keywords["keywords"][:20],
            "chunk_technical_skills": chunk_keywords["technical_skills"],
            "chunk_soft_skills": chunk_keywords["soft_skills"],

            # Referência às keywords do documento
            "document_keywords_overlap": list(
                set(chunk_keywords["keywords"]) & set(keywords.get("keywords", []))
            ),

            # Scores de relevância
            "relevance_scores": chunk_keywords["relevance_scores"],

            # Índice de busca otimizado do chunk
            "search_hints": cls._create_search_hints(section, chunk_keywords),

            # Estatísticas
            "content_length": len(content),
            "keyword_density": len(chunk_keywords["keywords"]) / max(len(content.split()), 1),
        }

        return metadata

    @classmethod
    def _create_search_hints(cls, section: str, keywords: Dict) -> List[str]:
        """Cria hints de busca para o chunk"""
        hints = []

        # Hint baseado na seção
        section_hints = {
            "full_text": ["curriculo completo", "documento inteiro", "resumo geral"],
            "personal_info": ["dados pessoais", "contato", "localizacao", "email", "telefone"],
            "experiences": ["experiencia profissional", "trabalho anterior", "cargo", "empresa"],
            "education": ["formacao academica", "graduacao", "universidade", "curso"],
            "skills": ["habilidades", "competencias", "conhecimentos tecnicos"],
            "languages": ["idiomas", "linguas", "nivel de fluencia"],
            "certifications": ["certificacoes", "cursos", "qualificacoes"],
        }

        hints.extend(section_hints.get(section, []))

        # Adicionar keywords principais como hints
        if keywords.get("technical_skills"):
            hints.extend(keywords["technical_skills"][:5])

        if keywords.get("domains"):
            hints.extend(keywords["domains"][:3])

        return hints


# Instância global
keyword_extraction_service = KeywordExtractionService()
