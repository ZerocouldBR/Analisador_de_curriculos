"""
Servico de matching inteligente de vagas

Analisa curriculos e busca candidatos que se enquadram
no perfil da empresa, com foco em producao e logistica.

Funcionalidades:
- Definicao de perfis de vagas com requisitos ponderados
- Scoring multi-criterio (skills, experiencia, certificacoes, disponibilidade)
- Ranking de candidatos por aderencia
- Sugestoes de vagas para candidatos
- Analise de gaps (o que falta para o candidato)
"""
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import re
import math
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import text, func

from app.db.models import Candidate, Chunk, Embedding
from app.core.config import settings
from app.services.keyword_extraction_service import KeywordExtractionService


class JobCategory(str, Enum):
    """Categorias de vagas"""
    PRODUCTION_OPERATOR = "production_operator"
    PRODUCTION_LEADER = "production_leader"
    PRODUCTION_SUPERVISOR = "production_supervisor"
    LOGISTICS_OPERATOR = "logistics_operator"
    LOGISTICS_ANALYST = "logistics_analyst"
    WAREHOUSE_OPERATOR = "warehouse_operator"
    FORKLIFT_OPERATOR = "forklift_operator"
    QUALITY_INSPECTOR = "quality_inspector"
    QUALITY_ANALYST = "quality_analyst"
    MAINTENANCE_TECHNICIAN = "maintenance_technician"
    MAINTENANCE_MECHANIC = "maintenance_mechanic"
    SAFETY_TECHNICIAN = "safety_technician"
    CNC_OPERATOR = "cnc_operator"
    WELDER = "welder"
    ELECTRICIAN = "electrician"
    PCP_ANALYST = "pcp_analyst"
    SUPPLY_CHAIN = "supply_chain"
    DRIVER = "driver"
    GENERAL = "general"


@dataclass
class JobRequirement:
    """Requisito de uma vaga"""
    name: str
    weight: float  # 0.0 a 1.0 (importancia)
    required: bool  # obrigatorio ou desejavel
    keywords: List[str]  # termos para busca
    category: str  # categoria do requisito


@dataclass
class JobProfile:
    """Perfil completo de uma vaga"""
    title: str
    category: JobCategory
    description: str
    requirements: List[JobRequirement]
    preferred_shifts: List[str] = field(default_factory=list)
    requires_cnh: Optional[str] = None  # Categoria CNH se necessario
    requires_travel: bool = False
    min_experience_years: int = 0
    industry_sector: Optional[str] = None


@dataclass
class CandidateMatch:
    """Resultado de matching de um candidato"""
    candidate_id: int
    candidate_name: str
    total_score: float  # 0.0 a 100.0
    requirement_scores: Dict[str, float]
    matched_keywords: List[str]
    missing_requirements: List[str]
    strengths: List[str]
    gaps: List[str]
    profile_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class JobMatchingService:
    """
    Servico para matching inteligente entre vagas e candidatos

    Especializado em perfis de producao e logistica
    """

    # Perfis pre-definidos para vagas comuns
    PRESET_PROFILES: Dict[str, JobProfile] = {}

    @classmethod
    def _init_presets(cls):
        """Inicializa perfis pre-definidos de vagas"""
        if cls.PRESET_PROFILES:
            return

        cls.PRESET_PROFILES = {
            # ============================================
            # PRODUCAO
            # ============================================
            "operador_producao": JobProfile(
                title="Operador de Producao",
                category=JobCategory.PRODUCTION_OPERATOR,
                description="Operador para linha de producao industrial",
                requirements=[
                    JobRequirement(
                        name="Experiencia em producao",
                        weight=0.3, required=True,
                        keywords=[
                            "operador de producao", "linha de producao", "linha de montagem",
                            "auxiliar de producao", "montagem", "montador",
                            "chao de fabrica", "producao industrial"
                        ],
                        category="production_operations"
                    ),
                    JobRequirement(
                        name="Escolaridade minima",
                        weight=0.1, required=True,
                        keywords=[
                            "ensino medio", "ensino médio", "segundo grau",
                            "ensino fundamental"
                        ],
                        category="education"
                    ),
                    JobRequirement(
                        name="Disponibilidade de turno",
                        weight=0.15, required=True,
                        keywords=[
                            "turno", "escala", "disponibilidade",
                            "1o turno", "2o turno", "3o turno"
                        ],
                        category="availability"
                    ),
                    JobRequirement(
                        name="5S e Qualidade",
                        weight=0.1, required=False,
                        keywords=[
                            "5s", "qualidade", "controle de qualidade",
                            "boas praticas", "procedimento"
                        ],
                        category="quality_control"
                    ),
                    JobRequirement(
                        name="Seguranca do Trabalho",
                        weight=0.15, required=False,
                        keywords=[
                            "nr", "epi", "seguranca", "cipa",
                            "nr-12", "nr-06"
                        ],
                        category="safety_norms"
                    ),
                    JobRequirement(
                        name="Trabalho em Equipe",
                        weight=0.1, required=False,
                        keywords=[
                            "trabalho em equipe", "equipe", "colaboracao",
                            "proatividade", "comprometimento"
                        ],
                        category="soft_skills"
                    ),
                    JobRequirement(
                        name="Lean/Melhoria Continua",
                        weight=0.1, required=False,
                        keywords=[
                            "lean", "kaizen", "5s", "melhoria continua",
                            "tpm", "kanban"
                        ],
                        category="continuous_improvement"
                    ),
                ],
                preferred_shifts=["1o turno", "2o turno", "3o turno"],
            ),

            "lider_producao": JobProfile(
                title="Lider de Producao",
                category=JobCategory.PRODUCTION_LEADER,
                description="Lider de equipe em ambiente de producao industrial",
                requirements=[
                    JobRequirement(
                        name="Experiencia em producao",
                        weight=0.25, required=True,
                        keywords=[
                            "lider de producao", "encarregado", "supervisor",
                            "coordenador", "gestao de equipe", "producao",
                            "chao de fabrica"
                        ],
                        category="production_management"
                    ),
                    JobRequirement(
                        name="Lideranca e Gestao",
                        weight=0.2, required=True,
                        keywords=[
                            "lideranca", "gestao de pessoas", "gestao de equipe",
                            "coordenacao", "supervisao", "treinamento",
                            "desenvolvimento de equipe"
                        ],
                        category="soft_skills"
                    ),
                    JobRequirement(
                        name="Lean/Melhoria Continua",
                        weight=0.15, required=True,
                        keywords=[
                            "lean", "kaizen", "5s", "melhoria continua",
                            "tpm", "pdca", "oee", "indicadores"
                        ],
                        category="continuous_improvement"
                    ),
                    JobRequirement(
                        name="ERP/Sistemas",
                        weight=0.1, required=False,
                        keywords=[
                            "sap", "totvs", "protheus", "erp",
                            "sistema de producao", "excel avancado"
                        ],
                        category="production_systems"
                    ),
                    JobRequirement(
                        name="Qualidade",
                        weight=0.15, required=False,
                        keywords=[
                            "qualidade", "iso 9001", "controle de qualidade",
                            "nao conformidade", "cep", "fmea"
                        ],
                        category="quality_control"
                    ),
                    JobRequirement(
                        name="Seguranca",
                        weight=0.15, required=True,
                        keywords=[
                            "seguranca do trabalho", "nr", "dds",
                            "cipa", "epi", "apr"
                        ],
                        category="safety_norms"
                    ),
                ],
                min_experience_years=2,
            ),

            "operador_empilhadeira": JobProfile(
                title="Operador de Empilhadeira",
                category=JobCategory.FORKLIFT_OPERATOR,
                description="Operador de empilhadeira para movimentacao de materiais",
                requirements=[
                    JobRequirement(
                        name="Habilitacao Empilhadeira",
                        weight=0.35, required=True,
                        keywords=[
                            "empilhadeira", "empilhadeirista",
                            "operador de empilhadeira", "curso de empilhadeira",
                            "nr-11", "nr 11"
                        ],
                        category="licenses_permits"
                    ),
                    JobRequirement(
                        name="Experiencia Logistica",
                        weight=0.2, required=True,
                        keywords=[
                            "logistica", "almoxarifado", "armazem", "deposito",
                            "movimentacao", "estoque", "expedicao"
                        ],
                        category="logistics_operations"
                    ),
                    JobRequirement(
                        name="CNH",
                        weight=0.1, required=False,
                        keywords=["cnh", "carteira de habilitacao", "habilitacao"],
                        category="licenses_permits"
                    ),
                    JobRequirement(
                        name="Seguranca",
                        weight=0.2, required=True,
                        keywords=[
                            "nr-11", "seguranca", "epi", "nr-12",
                            "movimentacao segura"
                        ],
                        category="safety_norms"
                    ),
                    JobRequirement(
                        name="Organizacao/5S",
                        weight=0.15, required=False,
                        keywords=[
                            "5s", "organizacao", "limpeza",
                            "fifo", "gestao visual"
                        ],
                        category="continuous_improvement"
                    ),
                ],
                requires_cnh="B",
            ),

            # ============================================
            # LOGISTICA
            # ============================================
            "auxiliar_logistica": JobProfile(
                title="Auxiliar de Logistica",
                category=JobCategory.LOGISTICS_OPERATOR,
                description="Auxiliar para operacoes logisticas e movimentacao",
                requirements=[
                    JobRequirement(
                        name="Experiencia Logistica",
                        weight=0.3, required=True,
                        keywords=[
                            "logistica", "auxiliar de logistica", "almoxarifado",
                            "estoque", "conferente", "separador", "recebimento",
                            "expedicao", "picking", "packing"
                        ],
                        category="logistics_operations"
                    ),
                    JobRequirement(
                        name="Controle de Estoque",
                        weight=0.2, required=True,
                        keywords=[
                            "controle de estoque", "inventario", "contagem",
                            "entrada", "saida", "fifo", "gestao de estoque"
                        ],
                        category="logistics_operations"
                    ),
                    JobRequirement(
                        name="Sistemas WMS/ERP",
                        weight=0.15, required=False,
                        keywords=[
                            "wms", "sap", "totvs", "sistema", "erp",
                            "excel", "informatica"
                        ],
                        category="production_systems"
                    ),
                    JobRequirement(
                        name="Organizacao",
                        weight=0.15, required=False,
                        keywords=[
                            "organizacao", "5s", "fifo", "enderecamento",
                            "rastreabilidade"
                        ],
                        category="continuous_improvement"
                    ),
                    JobRequirement(
                        name="Seguranca",
                        weight=0.1, required=False,
                        keywords=["nr-11", "seguranca", "epi", "movimentacao"],
                        category="safety_norms"
                    ),
                    JobRequirement(
                        name="Disponibilidade",
                        weight=0.1, required=True,
                        keywords=["turno", "disponibilidade", "escala"],
                        category="availability"
                    ),
                ],
            ),

            "analista_logistica": JobProfile(
                title="Analista de Logistica",
                category=JobCategory.LOGISTICS_ANALYST,
                description="Analista para planejamento e controle logistico",
                requirements=[
                    JobRequirement(
                        name="Experiencia Logistica",
                        weight=0.25, required=True,
                        keywords=[
                            "logistica", "analista de logistica", "supply chain",
                            "cadeia de suprimentos", "planejamento logistico",
                            "distribuicao", "transporte"
                        ],
                        category="supply_chain"
                    ),
                    JobRequirement(
                        name="Formacao Superior",
                        weight=0.15, required=True,
                        keywords=[
                            "logistica", "administracao", "engenharia",
                            "superior", "graduacao", "tecnologo"
                        ],
                        category="education"
                    ),
                    JobRequirement(
                        name="ERP/Sistemas",
                        weight=0.2, required=True,
                        keywords=[
                            "sap", "totvs", "wms", "tms", "erp",
                            "excel avancado", "bi", "power bi"
                        ],
                        category="production_systems"
                    ),
                    JobRequirement(
                        name="Indicadores/KPIs",
                        weight=0.15, required=False,
                        keywords=[
                            "kpi", "indicadores", "otl", "otif",
                            "nivel de servico", "custo logistico",
                            "dashboard", "relatorio"
                        ],
                        category="methodologies"
                    ),
                    JobRequirement(
                        name="Melhoria Continua",
                        weight=0.1, required=False,
                        keywords=[
                            "lean", "kaizen", "melhoria continua",
                            "pdca", "projetos de melhoria"
                        ],
                        category="continuous_improvement"
                    ),
                    JobRequirement(
                        name="Comunicacao",
                        weight=0.15, required=False,
                        keywords=[
                            "comunicacao", "negociacao", "relacionamento",
                            "fornecedores", "transportadoras"
                        ],
                        category="soft_skills"
                    ),
                ],
                min_experience_years=2,
            ),

            # ============================================
            # QUALIDADE
            # ============================================
            "inspetor_qualidade": JobProfile(
                title="Inspetor de Qualidade",
                category=JobCategory.QUALITY_INSPECTOR,
                description="Inspetor de qualidade para industria",
                requirements=[
                    JobRequirement(
                        name="Experiencia em Qualidade",
                        weight=0.3, required=True,
                        keywords=[
                            "inspetor de qualidade", "inspeccao", "controle de qualidade",
                            "qualidade", "auditoria", "amostragem",
                            "nao conformidade"
                        ],
                        category="quality_control"
                    ),
                    JobRequirement(
                        name="Metrologia",
                        weight=0.2, required=True,
                        keywords=[
                            "metrologia", "paquimetro", "micrometro",
                            "relogio comparador", "medicao", "calibracao",
                            "instrumentos de medicao"
                        ],
                        category="quality_control"
                    ),
                    JobRequirement(
                        name="Normas ISO",
                        weight=0.15, required=False,
                        keywords=[
                            "iso 9001", "iso", "sistema de gestao",
                            "auditoria interna", "procedimento", "instrucao de trabalho"
                        ],
                        category="quality_certifications"
                    ),
                    JobRequirement(
                        name="CEP/Estatistica",
                        weight=0.15, required=False,
                        keywords=[
                            "cep", "controle estatistico", "carta de controle",
                            "cp", "cpk", "capabilidade", "msa"
                        ],
                        category="quality_control"
                    ),
                    JobRequirement(
                        name="Leitura de Desenho",
                        weight=0.1, required=False,
                        keywords=[
                            "desenho tecnico", "leitura de desenho",
                            "interpretacao de desenho", "gd&t"
                        ],
                        category="quality_control"
                    ),
                    JobRequirement(
                        name="FMEA/APQP",
                        weight=0.1, required=False,
                        keywords=[
                            "fmea", "apqp", "ppap", "8d", "masp",
                            "acao corretiva"
                        ],
                        category="quality_control"
                    ),
                ],
            ),

            # ============================================
            # MANUTENCAO
            # ============================================
            "mecanico_manutencao": JobProfile(
                title="Mecanico de Manutencao",
                category=JobCategory.MAINTENANCE_MECHANIC,
                description="Mecanico para manutencao industrial",
                requirements=[
                    JobRequirement(
                        name="Experiencia em Manutencao",
                        weight=0.3, required=True,
                        keywords=[
                            "manutencao mecanica", "manutencao industrial",
                            "manutencao preventiva", "manutencao corretiva",
                            "mecanico industrial", "mecanico de manutencao"
                        ],
                        category="maintenance"
                    ),
                    JobRequirement(
                        name="Formacao Tecnica",
                        weight=0.15, required=True,
                        keywords=[
                            "tecnico em mecanica", "mecanica industrial",
                            "senai", "eletmecanica", "mecatronica"
                        ],
                        category="education"
                    ),
                    JobRequirement(
                        name="Equipamentos",
                        weight=0.2, required=False,
                        keywords=[
                            "pneumatica", "hidraulica", "rolamentos",
                            "alinhamento", "lubrificacao", "soldagem"
                        ],
                        category="maintenance"
                    ),
                    JobRequirement(
                        name="Seguranca",
                        weight=0.15, required=True,
                        keywords=[
                            "nr-12", "nr-10", "bloqueio", "tagueamento",
                            "loto", "seguranca", "epi"
                        ],
                        category="safety_norms"
                    ),
                    JobRequirement(
                        name="Sistemas",
                        weight=0.1, required=False,
                        keywords=[
                            "sap pm", "pcm", "ordem de servico",
                            "planejamento de manutencao"
                        ],
                        category="production_systems"
                    ),
                    JobRequirement(
                        name="Melhoria Continua",
                        weight=0.1, required=False,
                        keywords=[
                            "tpm", "kaizen", "5s",
                            "analise de falha", "rcm", "confiabilidade"
                        ],
                        category="continuous_improvement"
                    ),
                ],
                min_experience_years=1,
            ),

            # ============================================
            # PCP
            # ============================================
            "analista_pcp": JobProfile(
                title="Analista de PCP",
                category=JobCategory.PCP_ANALYST,
                description="Analista de Planejamento e Controle de Producao",
                requirements=[
                    JobRequirement(
                        name="Experiencia em PCP",
                        weight=0.3, required=True,
                        keywords=[
                            "pcp", "planejamento de producao",
                            "controle de producao", "programacao de producao",
                            "sequenciamento", "mrp"
                        ],
                        category="production_management"
                    ),
                    JobRequirement(
                        name="ERP/SAP",
                        weight=0.2, required=True,
                        keywords=[
                            "sap", "sap pp", "totvs", "erp",
                            "mrp", "mrp ii", "sistema de producao"
                        ],
                        category="production_systems"
                    ),
                    JobRequirement(
                        name="Excel/BI",
                        weight=0.15, required=True,
                        keywords=[
                            "excel avancado", "power bi", "dashboard",
                            "indicadores", "kpi", "oee"
                        ],
                        category="production_systems"
                    ),
                    JobRequirement(
                        name="Formacao",
                        weight=0.1, required=True,
                        keywords=[
                            "engenharia de producao", "administracao",
                            "logistica", "superior"
                        ],
                        category="education"
                    ),
                    JobRequirement(
                        name="Lean/Melhoria",
                        weight=0.15, required=False,
                        keywords=[
                            "lean", "kaizen", "smed", "takt time",
                            "balanceamento de linha"
                        ],
                        category="continuous_improvement"
                    ),
                    JobRequirement(
                        name="Gestao de Capacidade",
                        weight=0.1, required=False,
                        keywords=[
                            "capacidade produtiva", "lead time",
                            "gestao de capacidade", "forecast", "demanda"
                        ],
                        category="production_management"
                    ),
                ],
                min_experience_years=2,
            ),
        }

    @classmethod
    def get_preset_profiles(cls) -> Dict[str, JobProfile]:
        """Retorna perfis pre-definidos disponiveis"""
        cls._init_presets()
        return cls.PRESET_PROFILES

    @classmethod
    def get_profile(cls, profile_key: str) -> Optional[JobProfile]:
        """Retorna um perfil pre-definido pelo nome"""
        cls._init_presets()
        return cls.PRESET_PROFILES.get(profile_key)

    @classmethod
    def create_custom_profile(
        cls,
        title: str,
        category: str,
        description: str,
        requirements: List[Dict[str, Any]],
        **kwargs
    ) -> JobProfile:
        """
        Cria um perfil de vaga customizado

        Args:
            title: Titulo da vaga
            category: Categoria (usar JobCategory)
            description: Descricao da vaga
            requirements: Lista de requisitos com formato:
                [{"name": str, "weight": float, "required": bool,
                  "keywords": list, "category": str}]
        """
        reqs = []
        for req in requirements:
            reqs.append(JobRequirement(
                name=req["name"],
                weight=req.get("weight", 0.1),
                required=req.get("required", False),
                keywords=req.get("keywords", []),
                category=req.get("category", "general")
            ))

        try:
            cat = JobCategory(category)
        except ValueError:
            cat = JobCategory.GENERAL

        return JobProfile(
            title=title,
            category=cat,
            description=description,
            requirements=reqs,
            preferred_shifts=kwargs.get("preferred_shifts", []),
            requires_cnh=kwargs.get("requires_cnh"),
            requires_travel=kwargs.get("requires_travel", False),
            min_experience_years=kwargs.get("min_experience_years", 0),
            industry_sector=kwargs.get("industry_sector"),
        )

    @classmethod
    def match_candidates(
        cls,
        db: Session,
        job_profile: JobProfile,
        limit: int = 20,
        min_score: float = 30.0
    ) -> List[CandidateMatch]:
        """
        Busca e ranqueia candidatos para uma vaga

        Args:
            db: Sessao do banco
            job_profile: Perfil da vaga
            limit: Numero maximo de resultados
            min_score: Score minimo para inclusao (0-100)

        Returns:
            Lista de CandidateMatch ordenada por score
        """
        # Buscar todos os candidatos com chunks
        candidates = db.query(Candidate).join(
            Chunk, Chunk.candidate_id == Candidate.id
        ).distinct().all()

        matches = []

        for candidate in candidates:
            # Obter chunks do candidato
            chunks = db.query(Chunk).filter(
                Chunk.candidate_id == candidate.id
            ).all()

            if not chunks:
                continue

            # Obter texto completo e keywords
            full_text = ""
            candidate_keywords = {}

            for chunk in chunks:
                if chunk.section == "full_text":
                    full_text = chunk.content
                if chunk.section == "keyword_index" and chunk.meta_json:
                    candidate_keywords = chunk.meta_json

            if not full_text:
                full_text = " ".join(c.content for c in chunks)

            # Se nao tem keywords indexadas, extrair
            if not candidate_keywords:
                candidate_keywords = KeywordExtractionService.extract_keywords(full_text)

            # Calcular match
            match = cls._score_candidate(
                candidate, full_text, candidate_keywords, job_profile
            )

            if match.total_score >= min_score:
                matches.append(match)

        # Ordenar por score
        matches.sort(key=lambda m: m.total_score, reverse=True)

        return matches[:limit]

    @classmethod
    def _score_candidate(
        cls,
        candidate: Candidate,
        full_text: str,
        keywords: Dict[str, Any],
        profile: JobProfile
    ) -> CandidateMatch:
        """Calcula score detalhado de um candidato para uma vaga"""
        text_lower = full_text.lower()
        requirement_scores = {}
        matched_keywords = []
        missing_requirements = []
        strengths = []
        gaps = []
        total_weighted_score = 0.0
        total_weight = 0.0

        for req in profile.requirements:
            # Calcular score para este requisito
            score = cls._score_requirement(text_lower, keywords, req)
            requirement_scores[req.name] = score

            # Acumular score ponderado
            total_weighted_score += score * req.weight
            total_weight += req.weight

            # Coletar keywords encontradas
            for kw in req.keywords:
                if kw.lower() in text_lower:
                    matched_keywords.append(kw)

            # Classificar requisitos
            if score >= settings.job_matching_strength_threshold:
                strengths.append(f"{req.name} ({score:.0f}%)")
            elif score < settings.job_matching_gap_threshold:
                if req.required:
                    missing_requirements.append(f"[OBRIGATORIO] {req.name}")
                    gaps.append(
                        f"Necessita: {req.name} "
                        f"(buscar: {', '.join(req.keywords[:3])})"
                    )
                else:
                    gaps.append(f"Desejavel: {req.name}")

        # Calcular score total normalizado
        total_score = (total_weighted_score / total_weight * 100) if total_weight > 0 else 0

        # Bonus por CNH se requerida
        if profile.requires_cnh:
            cnh_pattern = rf'CNH\s*[:\-]?\s*(?:categoria\s*)?.*{profile.requires_cnh}'
            if re.search(cnh_pattern, full_text, re.IGNORECASE):
                total_score = min(total_score + settings.job_matching_cnh_bonus, 100)
                strengths.append(f"Possui CNH {profile.requires_cnh}")
            elif profile.requires_cnh:
                gaps.append(f"Necessita CNH categoria {profile.requires_cnh}")

        # Bonus por experiencia
        if profile.min_experience_years > 0:
            exp_years = cls._estimate_experience_years(full_text)
            if exp_years >= profile.min_experience_years:
                total_score = min(total_score + settings.job_matching_experience_bonus, 100)
                strengths.append(f"~{exp_years} anos de experiencia")
            else:
                gaps.append(
                    f"Experiencia minima: {profile.min_experience_years} anos "
                    f"(estimado: {exp_years})"
                )

        # Penalizacao por requisitos obrigatorios faltantes
        penalty = len(missing_requirements) * 10
        total_score = max(total_score - penalty, 0)

        # Determinar tipo de perfil
        profile_type = keywords.get("candidate_profile_type", "general")

        return CandidateMatch(
            candidate_id=candidate.id,
            candidate_name=candidate.full_name or "N/A",
            total_score=round(total_score, 1),
            requirement_scores={k: round(v, 1) for k, v in requirement_scores.items()},
            matched_keywords=list(set(matched_keywords)),
            missing_requirements=missing_requirements,
            strengths=strengths,
            gaps=gaps,
            profile_type=profile_type,
            metadata={
                "job_title": profile.title,
                "job_category": profile.category.value,
                "candidate_email": candidate.email,
                "candidate_city": candidate.city,
                "candidate_state": candidate.state,
            }
        )

    @classmethod
    def _score_requirement(
        cls,
        text_lower: str,
        keywords: Dict[str, Any],
        requirement: JobRequirement
    ) -> float:
        """Calcula score de um requisito especifico (0-100)"""
        if not requirement.keywords:
            return 50.0  # Neutral se sem keywords

        # Contar matches diretos no texto
        direct_matches = 0
        for kw in requirement.keywords:
            if kw.lower() in text_lower:
                direct_matches += 1

        direct_ratio = direct_matches / len(requirement.keywords)

        # Verificar match em keywords indexadas
        indexed_matches = 0
        all_candidate_kw = []

        # Coletar todas as keywords do candidato
        for key in [
            "keywords", "technical_skills", "production_skills",
            "logistics_skills", "quality_skills", "safety_certifications",
            "maintenance_skills", "licenses", "erp_systems",
            "improvement_methods", "soft_skills"
        ]:
            if isinstance(keywords.get(key), list):
                all_candidate_kw.extend([k.lower() if isinstance(k, str) else str(k).lower()
                                         for k in keywords[key]])

        for kw in requirement.keywords:
            if kw.lower() in all_candidate_kw:
                indexed_matches += 1

        indexed_ratio = indexed_matches / len(requirement.keywords)

        # Score combinado (texto direto tem mais peso)
        score = (direct_ratio * settings.job_matching_direct_text_weight + indexed_ratio * settings.job_matching_indexed_weight) * 100

        # Bonus se muitas ocorrencias (experiencia mais profunda)
        for kw in requirement.keywords[:5]:
            count = text_lower.count(kw.lower())
            if count > settings.job_matching_keyword_repeat_threshold:
                score = min(score + settings.job_matching_keyword_bonus, 100)

        return score

    @classmethod
    def _estimate_experience_years(cls, text: str) -> int:
        """Estima anos de experiencia a partir do texto"""
        # Procurar por padroes de datas
        date_ranges = re.findall(
            r'(\d{2}/\d{4})\s*[-–a]\s*(\d{2}/\d{4}|atual|presente)',
            text, re.IGNORECASE
        )

        if not date_ranges:
            # Tentar padrao com apenas ano
            year_ranges = re.findall(
                r'(\d{4})\s*[-–a]\s*(\d{4}|atual|presente)',
                text, re.IGNORECASE
            )
            date_ranges = year_ranges

        total_months = 0
        from datetime import datetime
        current_year = datetime.now().year

        for start_str, end_str in date_ranges:
            try:
                # Extrair ano de inicio
                start_year_match = re.search(r'(\d{4})', start_str)
                if start_year_match:
                    start_year = int(start_year_match.group(1))
                else:
                    continue

                # Extrair ano de fim
                if end_str.lower() in ['atual', 'presente', 'current']:
                    end_year = current_year
                else:
                    end_year_match = re.search(r'(\d{4})', end_str)
                    if end_year_match:
                        end_year = int(end_year_match.group(1))
                    else:
                        continue

                if 1980 <= start_year <= current_year and start_year <= end_year:
                    total_months += (end_year - start_year) * 12

            except (ValueError, AttributeError):
                continue

        return total_months // 12

    @classmethod
    def suggest_jobs_for_candidate(
        cls,
        db: Session,
        candidate_id: int
    ) -> List[Dict[str, Any]]:
        """
        Sugere vagas para um candidato baseado em seu perfil

        Args:
            db: Sessao do banco
            candidate_id: ID do candidato

        Returns:
            Lista de vagas sugeridas com scores
        """
        cls._init_presets()

        # Obter dados do candidato
        chunks = db.query(Chunk).filter(
            Chunk.candidate_id == candidate_id
        ).all()

        if not chunks:
            return []

        full_text = ""
        candidate_keywords = {}

        for chunk in chunks:
            if chunk.section == "full_text":
                full_text = chunk.content
            if chunk.section == "keyword_index" and chunk.meta_json:
                candidate_keywords = chunk.meta_json

        if not full_text:
            full_text = " ".join(c.content for c in chunks)

        if not candidate_keywords:
            candidate_keywords = KeywordExtractionService.extract_keywords(full_text)

        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            return []

        # Avaliar cada perfil pre-definido
        suggestions = []
        for profile_key, profile in cls.PRESET_PROFILES.items():
            match = cls._score_candidate(candidate, full_text, candidate_keywords, profile)

            if match.total_score >= settings.job_matching_suggestion_threshold:
                suggestions.append({
                    "profile_key": profile_key,
                    "job_title": profile.title,
                    "category": profile.category.value,
                    "match_score": match.total_score,
                    "strengths": match.strengths,
                    "gaps": match.gaps,
                    "matched_keywords": match.matched_keywords[:10],
                })

        # Ordenar por score
        suggestions.sort(key=lambda s: s["match_score"], reverse=True)

        return suggestions[:10]


# Instancia global
job_matching_service = JobMatchingService()
