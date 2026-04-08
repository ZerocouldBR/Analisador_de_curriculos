"""
Servico avancado de extracao de palavras-chave para curriculos

Utiliza multiplas tecnicas:
- TF-IDF para termos relevantes
- N-grams para expressoes compostas
- Extracao de entidades nomeadas (empresas, tecnologias, certificacoes)
- Categorizacao por tipo (skill tecnica, soft skill, ferramenta, etc.)
- Suporte completo a producao, logistica e industria
"""
import re
from typing import Dict, List, Any, Set, Optional
from collections import Counter
import math


class KeywordExtractionService:
    """
    Servico para extracao avancada de palavras-chave de curriculos

    Gera indices semanticos para melhorar a localizacao pelo LLM
    Suporta perfis de TI, producao, logistica, qualidade e industria
    """

    # Categorias de palavras-chave para indexacao
    SKILL_CATEGORIES = {
        # ============================================
        # TECNOLOGIA DA INFORMACAO
        # ============================================
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

        # ============================================
        # PRODUCAO E MANUFATURA
        # ============================================
        "production_operations": [
            "operador de producao", "operador de maquinas", "operador de empilhadeira",
            "auxiliar de producao", "lider de producao", "supervisor de producao",
            "encarregado de producao", "gerente de producao", "coordenador de producao",
            "analista de producao", "tecnico de producao", "montador", "montagem",
            "linha de producao", "linha de montagem", "chao de fabrica",
            "operador cnc", "operador de torno", "operador de fresa",
            "operador de prensa", "operador de injecao", "soldador", "soldagem",
            "torneiro mecanico", "fresador", "retificador", "caldeireiro",
            "eletricista industrial", "mecanico industrial", "mecanico de manutencao",
            "instrumentista", "eletricista", "encanador industrial",
            "pintor industrial", "jateador", "polidor", "rebarbador",
            "alimentador de linha", "abastecedor", "embalador", "operador de ponte rolante",
            "setup de maquina", "preparador de maquinas", "ajustador mecanico",
            "ferramenteiro", "moleiro", "estampador"
        ],
        "production_management": [
            "pcp", "planejamento e controle de producao", "planejamento de producao",
            "controle de producao", "mrp", "mrp ii", "gestao de producao",
            "gestao industrial", "engenharia de producao", "engenharia industrial",
            "cronoanálise", "cronoanalise", "tempos e metodos", "tempos e movimentos",
            "balanceamento de linha", "capacidade produtiva", "eficiencia produtiva",
            "oee", "overall equipment effectiveness", "takt time", "lead time",
            "setup rapido", "smed", "troca rapida de ferramenta",
            "gestao de capacidade", "sequenciamento de producao",
            "programacao de producao", "ordem de producao", "ordem de servico"
        ],
        "production_systems": [
            "sap", "sap pp", "sap mm", "sap sd", "sap wm", "sap qm",
            "totvs", "totvs protheus", "protheus", "datasul", "microsiga",
            "oracle erp", "senior sistemas", "senior", "wms",
            "mes", "manufacturing execution system", "sistema mes",
            "scada", "supervisorio", "ihm", "clp", "plc",
            "automacao industrial", "automacao", "robotica industrial",
            "industria 4.0", "iot industrial", "iiot"
        ],

        # ============================================
        # LOGISTICA E SUPPLY CHAIN
        # ============================================
        "logistics_operations": [
            "logistica", "logistica reversa", "logistica integrada",
            "operador logistico", "auxiliar de logistica", "analista de logistica",
            "coordenador de logistica", "supervisor de logistica", "gerente de logistica",
            "almoxarife", "almoxarifado", "estoquista", "conferente",
            "separador", "picking", "packing", "cross docking", "crossdocking",
            "recebimento", "expedicao", "despacho", "distribuicao",
            "armazenagem", "armazem", "deposito", "centro de distribuicao", "cd",
            "inventario", "controle de estoque", "gestao de estoque",
            "movimentacao de materiais", "abastecimento", "empilhadeira",
            "paleteira", "transpaleteira", "carrinho hidraulico",
            "fifo", "lifo", "fefo", "kanban", "just in time", "jit",
            "operador de empilhadeira", "motorista de empilhadeira"
        ],
        "supply_chain": [
            "supply chain", "cadeia de suprimentos", "gestao de suprimentos",
            "compras", "procurement", "sourcing", "negociacao com fornecedores",
            "gestao de fornecedores", "homologacao de fornecedores",
            "planejamento de demanda", "forecast", "previsao de demanda",
            "gestao de materiais", "gestao de compras", "follow up",
            "importacao", "exportacao", "comercio exterior", "comex",
            "desembaraco aduaneiro", "drawback", "incoterms",
            "transporte", "frete", "roteirizacao", "gestao de frotas",
            "rastreamento", "tracking", "last mile", "primeira milha"
        ],

        # ============================================
        # QUALIDADE E MELHORIA CONTINUA
        # ============================================
        "quality_control": [
            "controle de qualidade", "qualidade", "inspetor de qualidade",
            "analista de qualidade", "tecnico de qualidade", "auditor de qualidade",
            "supervisor de qualidade", "coordenador de qualidade", "gerente de qualidade",
            "inspeccao", "metrologia", "calibracao", "rastreabilidade",
            "nao conformidade", "acao corretiva", "acao preventiva",
            "cep", "controle estatistico de processo", "carta de controle",
            "capabilidade", "cp", "cpk", "ppk", "msa",
            "analise de causa raiz", "ishikawa", "diagrama de pareto",
            "fmea", "ppap", "apqp", "8d", "masp", "pdca",
            "dispositivo poka-yoke", "poka yoke", "jidoka",
            "ensaios", "ensaio destrutivo", "ensaio nao destrutivo",
            "teste de qualidade", "amostragem", "plano de amostragem"
        ],
        "quality_certifications": [
            "iso 9001", "iso 14001", "iso 45001", "iso 22000", "iso 17025",
            "iso 16949", "iatf 16949", "iso 13485",
            "bpf", "boas praticas de fabricacao", "gmp",
            "haccp", "appcc", "fssc 22000",
            "ohsas 18001", "sa 8000", "iso 31000",
            "sistema de gestao integrado", "sgi", "sistema de gestao da qualidade", "sgq"
        ],
        "continuous_improvement": [
            "lean manufacturing", "lean", "lean production",
            "six sigma", "seis sigma", "green belt", "black belt",
            "yellow belt", "white belt", "master black belt",
            "kaizen", "melhoria continua", "5s", "cinco sensos",
            "tpm", "manutencao produtiva total",
            "value stream mapping", "vsm", "mapeamento de fluxo de valor",
            "gemba", "gemba walk", "gestao visual", "andon",
            "a3", "hoshin kanri", "heijunka",
            "teoria das restricoes", "toc", "gargalo",
            "dmaic", "dfss", "design for six sigma"
        ],

        # ============================================
        # SEGURANCA DO TRABALHO
        # ============================================
        "safety_norms": [
            "nr 01", "nr 04", "nr 05", "nr 06", "nr 07", "nr 09", "nr 10",
            "nr 11", "nr 12", "nr 13", "nr 15", "nr 17", "nr 18",
            "nr 20", "nr 23", "nr 25", "nr 26", "nr 33", "nr 35",
            "nr-01", "nr-04", "nr-05", "nr-06", "nr-07", "nr-09", "nr-10",
            "nr-11", "nr-12", "nr-13", "nr-15", "nr-17", "nr-18",
            "nr-20", "nr-23", "nr-25", "nr-26", "nr-33", "nr-35",
            "cipa", "sipat", "ppra", "pcmso", "ltcat", "pgr",
            "epi", "epc", "equipamento de protecao individual",
            "seguranca do trabalho", "tecnico de seguranca",
            "engenheiro de seguranca", "brigada de incendio", "brigadista",
            "primeiros socorros", "trabalho em altura", "espaco confinado",
            "permissao de trabalho", "pt", "analise preliminar de risco", "apr",
            "dialogo diario de seguranca", "dds"
        ],

        # ============================================
        # MANUTENCAO
        # ============================================
        "maintenance": [
            "manutencao preventiva", "manutencao corretiva", "manutencao preditiva",
            "manutencao industrial", "manutencao mecanica", "manutencao eletrica",
            "manutencao eletromecanica", "pcm", "planejamento de manutencao",
            "lubrificacao", "analise de vibracoes", "termografia",
            "analise de oleo", "ultrassom", "alinhamento",
            "balanceamento", "gestao de ativos", "confiabilidade",
            "mtbf", "mttr", "disponibilidade", "backlog",
            "ordem de manutencao", "plano de manutencao"
        ],

        # ============================================
        # HABILITACOES E LICENCAS
        # ============================================
        "licenses_permits": [
            "cnh a", "cnh b", "cnh c", "cnh d", "cnh e", "cnh ab", "cnh ad", "cnh ae",
            "carteira de habilitacao", "carteira de motorista",
            "mopp", "curso mopp", "movimentacao de produtos perigosos",
            "aso", "atestado de saude ocupacional",
            "crea", "cfq", "crq", "crf", "coren", "crbio",
            "registro profissional"
        ],

        # ============================================
        # COMPETENCIAS COMPORTAMENTAIS
        # ============================================
        "soft_skills": [
            "lideranca", "comunicacao", "trabalho em equipe", "proatividade", "criatividade",
            "resolucao de problemas", "pensamento critico", "adaptabilidade", "organizacao",
            "gestao de tempo", "negociacao", "apresentacao", "mentoria", "colaboracao",
            "empatia", "resiliencia", "iniciativa", "autonomia", "disciplina",
            "pontualidade", "comprometimento", "responsabilidade", "flexibilidade",
            "atencao a detalhes", "foco em resultados", "orientacao a resultados",
            "relacionamento interpessoal", "gestao de conflitos",
            "leadership", "communication", "teamwork", "problem solving",
            "critical thinking", "adaptability", "time management"
        ],

        # ============================================
        # METODOLOGIAS (TI + INDUSTRIA)
        # ============================================
        "methodologies": [
            "agile", "scrum", "kanban", "lean", "xp", "extreme programming",
            "devops", "devsecops", "ci/cd", "tdd", "bdd", "ddd",
            "solid", "clean code", "clean architecture",
            "microservices", "monolith", "serverless", "event-driven",
            "cqrs", "event sourcing",
            # Metodologias industriais
            "wce", "world class excellence", "wcm", "world class manufacturing",
            "tqm", "total quality management", "gestao da qualidade total",
            "sga", "sistema de gestao ambiental",
            "bsc", "balanced scorecard", "okr", "kpi",
            "gestao por processos", "bpm", "mapeamento de processos"
        ],

        # ============================================
        # CERTIFICACOES (TI + INDUSTRIA)
        # ============================================
        "certifications": [
            # TI
            "aws certified", "azure certified", "gcp certified", "pmp", "scrum master",
            "product owner", "cissp", "ceh", "comptia", "cisco", "ccna", "ccnp",
            "oracle certified", "microsoft certified", "kubernetes certified", "cka", "ckad",
            "terraform certified", "hashicorp certified", "linux+", "lpic",
            # Industria
            "auditor lider iso 9001", "auditor interno iso 9001",
            "auditor lider iso 14001", "auditor interno iso 14001",
            "green belt certificado", "black belt certificado",
            "lean practitioner", "lean master",
            "operador de empilhadeira certificado",
            "cqe", "cqa", "cmq", "cssgb", "cssbb",  # ASQ certs
            "cbet", "cres"  # Biomedical
        ],

        # ============================================
        # DOMINIOS DE CONHECIMENTO
        # ============================================
        "domains": [
            # TI
            "machine learning", "deep learning", "inteligencia artificial", "artificial intelligence",
            "data science", "ciencia de dados", "big data", "analytics", "business intelligence",
            "bi", "etl", "data engineering", "engenharia de dados", "nlp",
            "processamento de linguagem", "computer vision", "visao computacional",
            "iot", "internet das coisas", "blockchain", "web3", "fintech",
            "healthtech", "edtech", "e-commerce", "saas", "api", "rest",
            "graphql", "grpc", "websocket", "microservices", "microsservicos",
            # Industria
            "automotivo", "automovel", "metalurgia", "metalmecanico",
            "alimenticio", "farmaceutico", "quimico", "petroquimico",
            "papel e celulose", "textil", "plastico", "borracha",
            "eletroeletronico", "cosmetico", "construcao civil",
            "mineracao", "energia", "agronegocio", "agroindustria"
        ],

        # ============================================
        # FORMACAO ACADEMICA RELEVANTE
        # ============================================
        "education_areas": [
            "engenharia de producao", "engenharia mecanica", "engenharia eletrica",
            "engenharia quimica", "engenharia civil", "engenharia de alimentos",
            "engenharia de materiais", "engenharia ambiental",
            "administracao", "administracao de empresas", "gestao empresarial",
            "logistica", "gestao de logistica", "gestao da producao",
            "tecnico em mecanica", "tecnico em eletrica", "tecnico em eletronica",
            "tecnico em seguranca do trabalho", "tecnico em qualidade",
            "tecnico em logistica", "tecnico em administracao",
            "tecnologo em logistica", "tecnologo em producao",
            "tecnologo em gestao da qualidade",
            "ciencia da computacao", "sistemas de informacao",
            "engenharia da computacao", "engenharia de software",
            "analise e desenvolvimento de sistemas"
        ]
    }

    # Stopwords em portugues e ingles para filtrar
    STOPWORDS = {
        "a", "o", "e", "de", "da", "do", "em", "para", "com", "por", "que", "um", "uma",
        "os", "as", "no", "na", "se", "ou", "mais", "como", "mas", "foi", "aos", "das",
        "dos", "seu", "sua", "ser", "ter", "está", "são", "muito", "também", "já",
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of",
        "with", "by", "from", "as", "is", "was", "are", "were", "been", "be", "have",
        "has", "had", "do", "does", "did", "will", "would", "could", "should", "may",
        "might", "must", "shall", "can", "this", "that", "these", "those", "it", "its",
        "não", "sim", "pelo", "pela", "nos", "nas", "entre", "sobre", "até", "quando",
        "onde", "qual", "quem", "cada", "todo", "toda", "todos", "todas"
    }

    @classmethod
    def extract_keywords(cls, text: str, resume_data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Extrai palavras-chave estruturadas de um texto de curriculo

        Args:
            text: Texto completo do curriculo
            resume_data: Dados parseados do curriculo (opcional)

        Returns:
            Dict com palavras-chave categorizadas e indices
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
            # Producao e logistica
            "production_skills": [],
            "logistics_skills": [],
            "quality_skills": [],
            "safety_certifications": [],
            "maintenance_skills": [],
            "licenses": [],
            "erp_systems": [],
            "improvement_methods": [],
            "industry_sectors": [],
            # Analise
            "tfidf_terms": [],
            "ngrams": [],
            "search_index": "",
            "relevance_scores": {},
            "candidate_profile_type": "general"  # general, production, logistics, it, quality
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
                # Producao e logistica
                elif category in ["production_operations", "production_management"]:
                    result["production_skills"].extend(found)
                elif category in ["logistics_operations", "supply_chain"]:
                    result["logistics_skills"].extend(found)
                elif category in ["quality_control", "quality_certifications"]:
                    result["quality_skills"].extend(found)
                elif category == "safety_norms":
                    result["safety_certifications"].extend(found)
                elif category == "maintenance":
                    result["maintenance_skills"].extend(found)
                elif category == "licenses_permits":
                    result["licenses"].extend(found)
                elif category == "production_systems":
                    result["erp_systems"].extend(found)
                elif category == "continuous_improvement":
                    result["improvement_methods"].extend(found)

        # Extrair n-grams relevantes (2 e 3 palavras)
        ngrams = cls._extract_ngrams(normalized_text, [2, 3])
        result["ngrams"] = ngrams[:50]

        # Calcular TF-IDF dos termos
        tfidf_terms = cls._calculate_tfidf(normalized_text)
        result["tfidf_terms"] = tfidf_terms[:30]

        # Extrair empresas mencionadas (padroes comuns)
        companies = cls._extract_companies(text)
        result["companies"] = companies

        # Detectar setores industriais do texto
        result["industry_sectors"] = cls._detect_industry_sectors(normalized_text)

        # Processar dados parseados se disponiveis
        if resume_data:
            if resume_data.get("experiences"):
                for exp in resume_data["experiences"]:
                    if exp.get("title"):
                        result["experience_keywords"].append(exp["title"].lower())
                    if exp.get("company"):
                        result["companies"].append(exp["company"])

            if resume_data.get("education"):
                for edu in resume_data["education"]:
                    if edu.get("degree"):
                        result["education_keywords"].append(edu["degree"].lower())
                    if edu.get("institution"):
                        result["education_keywords"].append(edu["institution"].lower())

            if resume_data.get("skills"):
                for skill in resume_data["skills"]:
                    skill_lower = skill.lower().strip()
                    if skill_lower and skill_lower not in result["keywords"]:
                        result["keywords"].append(skill_lower)

            # Extrair dados especificos de producao/logistica do resume_data
            if resume_data.get("licenses"):
                result["licenses"].extend([l.lower() for l in resume_data["licenses"]])
            if resume_data.get("safety_certs"):
                result["safety_certifications"].extend(
                    [s.lower() for s in resume_data["safety_certs"]]
                )

        # Remover duplicatas
        for key in [
            "keywords", "technical_skills", "soft_skills", "tools_and_frameworks",
            "companies", "production_skills", "logistics_skills", "quality_skills",
            "safety_certifications", "maintenance_skills", "licenses", "erp_systems",
            "improvement_methods", "industry_sectors", "certifications", "domains"
        ]:
            result[key] = list(set(result[key]))

        # Determinar perfil do candidato
        result["candidate_profile_type"] = cls._determine_profile_type(result)

        # Calcular scores de relevancia
        result["relevance_scores"] = cls._calculate_relevance_scores(result, normalized_text)

        # Criar indice de busca otimizado para LLM
        result["search_index"] = cls._create_search_index(result)

        return result

    @classmethod
    def _determine_profile_type(cls, extracted: Dict) -> str:
        """Determina o tipo de perfil predominante do candidato"""
        scores = {
            "production": (
                len(extracted.get("production_skills", []))
                + len(extracted.get("maintenance_skills", []))
            ),
            "logistics": len(extracted.get("logistics_skills", [])),
            "quality": len(extracted.get("quality_skills", [])),
            "it": (
                len(extracted.get("technical_skills", []))
                + len(extracted.get("tools_and_frameworks", []))
            ),
            "safety": len(extracted.get("safety_certifications", [])),
        }

        if max(scores.values()) == 0:
            return "general"

        primary = max(scores, key=scores.get)

        # Se pontuacao muito baixa, manter como geral
        if scores[primary] < 2:
            return "general"

        return primary

    @classmethod
    def _detect_industry_sectors(cls, text: str) -> List[str]:
        """Detecta setores industriais mencionados no texto"""
        sectors = {
            "automotivo": ["automotivo", "automovel", "autopeças", "montadora", "veiculos"],
            "alimenticio": ["alimenticio", "alimentos", "bebidas", "frigorifico", "laticinio"],
            "farmaceutico": ["farmaceutico", "farmacia", "laboratorio", "medicamento"],
            "metalurgico": ["metalurgico", "metalurgia", "siderurgia", "fundição", "usinagem"],
            "quimico": ["quimico", "quimica", "petroquimico", "tintas", "solventes"],
            "textil": ["textil", "confeccao", "tecelagem", "malharia", "vestuario"],
            "plastico": ["plastico", "injecao plastica", "extrusão", "sopro", "termoformagem"],
            "eletroeletronico": ["eletroeletronico", "eletronico", "componentes", "pcb"],
            "construcao": ["construcao civil", "obra", "edificacao", "infraestrutura"],
            "agroindustria": ["agroindustria", "agronegocio", "usina", "grãos", "commodities"],
            "logistica_transporte": ["transportadora", "operador logistico", "armazem geral"],
            "papel_celulose": ["papel", "celulose", "embalagem", "cartonagem"],
            "energia": ["energia", "eletrica", "solar", "eolica", "termoeletrica"],
            "mineracao": ["mineracao", "mina", "extracao mineral", "beneficiamento"],
        }

        found = []
        for sector, keywords in sectors.items():
            for kw in keywords:
                if kw in text:
                    found.append(sector)
                    break

        return list(set(found))

    @classmethod
    def _normalize_text(cls, text: str) -> str:
        """Normaliza texto para extracao"""
        text = text.lower()
        text = re.sub(r'[^\w\sáéíóúàèìòùâêîôûãõç/\-.]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    @classmethod
    def _find_keywords_in_text(cls, text: str, keywords: List[str]) -> Set[str]:
        """Encontra palavras-chave no texto"""
        found = set()
        for keyword in keywords:
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

            counter = Counter(ngrams)

            for ngram, count in counter.most_common(25):
                if count >= 2:
                    all_ngrams.append({
                        "term": ngram,
                        "count": count,
                        "n": n
                    })

        all_ngrams.sort(key=lambda x: x["count"], reverse=True)
        return all_ngrams

    @classmethod
    def _calculate_tfidf(cls, text: str) -> List[Dict[str, Any]]:
        """Calcula TF-IDF simplificado para termos no documento"""
        words = [w for w in text.split() if w not in cls.STOPWORDS and len(w) > 2]
        word_count = Counter(words)

        tfidf_scores = []

        for word, count in word_count.items():
            tf = 1 + math.log(count) if count > 0 else 0

            idf = 1.0
            word_lower = word.lower()

            for category, keywords_list in cls.SKILL_CATEGORIES.items():
                if word_lower in [k.lower() for k in keywords_list]:
                    # Maior peso para termos de producao/logistica
                    if category in [
                        "production_operations", "production_management",
                        "logistics_operations", "supply_chain",
                        "quality_control", "safety_norms", "maintenance"
                    ]:
                        from app.core.config import settings as _s
                        idf = _s.keyword_idf_domain
                    else:
                        from app.core.config import settings as _s
                        idf = _s.keyword_idf_default
                    break

            if len(word) > 8:
                from app.core.config import settings as _s
                idf *= _s.keyword_idf_long_word_multiplier

            tfidf = tf * idf

            tfidf_scores.append({
                "term": word,
                "tf": round(tf, 3),
                "idf": round(idf, 3),
                "tfidf": round(tfidf, 3),
                "count": count
            })

        tfidf_scores.sort(key=lambda x: x["tfidf"], reverse=True)
        return tfidf_scores

    @classmethod
    def _extract_companies(cls, text: str) -> List[str]:
        """Extrai nomes de empresas do texto"""
        companies = []

        patterns = [
            r'(?:na|at|@|em)\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]*)*)',
            r'([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]*)*)\s+(?:Ltda|S\.A\.|Inc|Corp|LLC|Ltd|Eireli|ME|EPP)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if len(match) > 3:
                    companies.append(match.strip())

        return list(set(companies))[:20]

    @classmethod
    def _calculate_relevance_scores(cls, extracted: Dict, text: str) -> Dict[str, float]:
        """Calcula scores de relevancia para cada categoria"""
        scores = {}
        text_len = len(text) if text else 1

        for category, keywords in extracted["keywords_by_category"].items():
            if keywords:
                base_score = len(keywords) * 10
                coverage_bonus = 0
                for kw in keywords:
                    count = text.lower().count(kw.lower())
                    coverage_bonus += min(count * 2, 10)
                scores[category] = min(base_score + coverage_bonus, 100)

        total_keywords = len(extracted["keywords"])
        scores["overall"] = min(total_keywords * 5, 100)

        # Scores especificos de area
        prod_score = (
            len(extracted.get("production_skills", []))
            + len(extracted.get("maintenance_skills", []))
        ) * 15
        scores["production"] = min(prod_score, 100)

        log_score = len(extracted.get("logistics_skills", [])) * 15
        scores["logistics"] = min(log_score, 100)

        qual_score = (
            len(extracted.get("quality_skills", []))
            + len(extracted.get("improvement_methods", []))
        ) * 15
        scores["quality"] = min(qual_score, 100)

        safety_score = len(extracted.get("safety_certifications", [])) * 20
        scores["safety"] = min(safety_score, 100)

        return scores

    @classmethod
    def _create_search_index(cls, extracted: Dict) -> str:
        """
        Cria um indice de busca otimizado para consultas LLM

        Formato estruturado que facilita a localizacao semantica
        Inclui categorias de producao, logistica e qualidade
        """
        parts = []

        parts.append("=== INDICE DE PALAVRAS-CHAVE DO CURRICULO ===")
        parts.append(f"[TIPO DE PERFIL]: {extracted.get('candidate_profile_type', 'general')}")
        parts.append("")

        # Skills tecnicas (TI)
        if extracted["technical_skills"]:
            parts.append(f"[SKILLS TECNICAS TI]: {', '.join(extracted['technical_skills'])}")

        # Producao
        if extracted.get("production_skills"):
            parts.append(f"[PRODUCAO]: {', '.join(extracted['production_skills'])}")

        # Logistica
        if extracted.get("logistics_skills"):
            parts.append(f"[LOGISTICA]: {', '.join(extracted['logistics_skills'])}")

        # Qualidade
        if extracted.get("quality_skills"):
            parts.append(f"[QUALIDADE]: {', '.join(extracted['quality_skills'])}")

        # Seguranca
        if extracted.get("safety_certifications"):
            parts.append(f"[SEGURANCA/NRs]: {', '.join(extracted['safety_certifications'])}")

        # Manutencao
        if extracted.get("maintenance_skills"):
            parts.append(f"[MANUTENCAO]: {', '.join(extracted['maintenance_skills'])}")

        # Sistemas ERP
        if extracted.get("erp_systems"):
            parts.append(f"[SISTEMAS/ERP]: {', '.join(extracted['erp_systems'])}")

        # Melhoria continua
        if extracted.get("improvement_methods"):
            parts.append(f"[MELHORIA CONTINUA]: {', '.join(extracted['improvement_methods'])}")

        # Habilitacoes
        if extracted.get("licenses"):
            parts.append(f"[HABILITACOES]: {', '.join(extracted['licenses'])}")

        # Setores industriais
        if extracted.get("industry_sectors"):
            parts.append(f"[SETORES]: {', '.join(extracted['industry_sectors'])}")

        # Soft skills
        if extracted["soft_skills"]:
            parts.append(f"[SOFT SKILLS]: {', '.join(extracted['soft_skills'])}")

        # Ferramentas
        if extracted["tools_and_frameworks"]:
            parts.append(f"[FERRAMENTAS]: {', '.join(extracted['tools_and_frameworks'])}")

        # Certificacoes
        if extracted["certifications"]:
            parts.append(f"[CERTIFICACOES]: {', '.join(extracted['certifications'])}")

        # Dominios
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

        # Scores de relevancia
        if extracted.get("relevance_scores"):
            scores = extracted["relevance_scores"]
            score_parts = []
            for area in ["production", "logistics", "quality", "safety", "overall"]:
                if scores.get(area, 0) > 0:
                    score_parts.append(f"{area}={scores[area]:.0f}")
            if score_parts:
                parts.append(f"[SCORES]: {', '.join(score_parts)}")

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
        """
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

            # Producao/logistica
            "chunk_production_skills": chunk_keywords.get("production_skills", []),
            "chunk_logistics_skills": chunk_keywords.get("logistics_skills", []),
            "chunk_quality_skills": chunk_keywords.get("quality_skills", []),
            "chunk_safety_certs": chunk_keywords.get("safety_certifications", []),
            "chunk_profile_type": chunk_keywords.get("candidate_profile_type", "general"),

            # Referencia as keywords do documento
            "document_keywords_overlap": list(
                set(chunk_keywords["keywords"]) & set(keywords.get("keywords", []))
            ),

            # Scores de relevancia
            "relevance_scores": chunk_keywords["relevance_scores"],

            # Indice de busca otimizado do chunk
            "search_hints": cls._create_search_hints(section, chunk_keywords),

            # Estatisticas
            "content_length": len(content),
            "keyword_density": len(chunk_keywords["keywords"]) / max(len(content.split()), 1),
        }

        return metadata

    @classmethod
    def _create_search_hints(cls, section: str, keywords: Dict) -> List[str]:
        """Cria hints de busca para o chunk"""
        hints = []

        section_hints = {
            "full_text": ["curriculo completo", "documento inteiro", "resumo geral"],
            "personal_info": ["dados pessoais", "contato", "localizacao", "email", "telefone"],
            "experiences": [
                "experiencia profissional", "trabalho anterior", "cargo", "empresa",
                "producao", "logistica", "operador", "fabrica"
            ],
            "education": ["formacao academica", "graduacao", "universidade", "curso", "tecnico"],
            "skills": [
                "habilidades", "competencias", "conhecimentos tecnicos",
                "producao", "logistica", "qualidade", "seguranca"
            ],
            "languages": ["idiomas", "linguas", "nivel de fluencia"],
            "certifications": [
                "certificacoes", "cursos", "qualificacoes",
                "nr", "iso", "lean", "six sigma", "cnh"
            ],
            "keyword_index": [
                "indice", "palavras-chave", "resumo de skills",
                "perfil tecnico", "perfil operacional"
            ],
        }

        hints.extend(section_hints.get(section, []))

        if keywords.get("technical_skills"):
            hints.extend(keywords["technical_skills"][:5])
        if keywords.get("production_skills"):
            hints.extend(keywords["production_skills"][:5])
        if keywords.get("logistics_skills"):
            hints.extend(keywords["logistics_skills"][:5])
        if keywords.get("domains"):
            hints.extend(keywords["domains"][:3])
        if keywords.get("industry_sectors"):
            hints.extend(keywords["industry_sectors"][:3])

        return hints


# Instancia global
keyword_extraction_service = KeywordExtractionService()
