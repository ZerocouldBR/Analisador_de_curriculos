"""
API de integracao com LinkedIn

Endpoints:
- Extracao de perfil publico
- Busca de profissionais por criterios
- Enriquecimento de candidatos
- Historico de buscas
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.db.database import get_db
from app.schemas.candidate import (
    LinkedInProfile,
    ExternalEnrichmentResponse,
    CandidateResponse
)
from app.services.linkedin_service import LinkedInService
from app.services.candidate_service import CandidateService
from app.core.dependencies import require_permission, get_current_user
from app.core.config import settings
from app.db.models import User

router = APIRouter(prefix="/linkedin", tags=["linkedin"])


# ================================================================
# Schemas
# ================================================================

class ProfessionalSearchRequest(BaseModel):
    """Criterios de busca de profissionais"""
    title: Optional[str] = Field(None, description="Cargo desejado (ex: Operador CNC)")
    skills: Optional[List[str]] = Field(None, description="Lista de skills requeridas")
    location: Optional[str] = Field(None, description="Cidade ou estado")
    experience_years: Optional[int] = Field(None, ge=0, description="Anos minimos de experiencia")
    keywords: Optional[List[str]] = Field(None, description="Palavras-chave gerais")
    industry: Optional[str] = Field(None, description="Setor/industria")


class SearchResultResponse(BaseModel):
    search_id: int
    criteria: Dict[str, Any]
    results: List[Dict[str, Any]]
    total_found: int
    sources: Dict[str, int]
    note: str


# ================================================================
# Profile Extraction
# ================================================================

@router.post("/extract", response_model=Dict[str, Any])
async def extract_linkedin_profile(
    profile_url: str = Body(..., embed=True, description="URL do perfil do LinkedIn"),
    current_user: User = Depends(require_permission("linkedin.enrich"))
):
    """
    Extrai dados de um perfil publico do LinkedIn

    **Requer permissao:** linkedin.enrich
    """
    try:
        profile_data = await LinkedInService.extract_profile_data(profile_url)

        if not profile_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nao foi possivel extrair dados do perfil. Verifique a URL."
            )

        return profile_data

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar perfil: {str(e)}"
        )


# ================================================================
# Professional Search
# ================================================================

@router.post("/search", response_model=SearchResultResponse)
def search_professionals(
    criteria: ProfessionalSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("linkedin.enrich")),
):
    """
    Busca profissionais por criterios

    Busca na base interna de candidatos e em dados do LinkedIn ja coletados.
    Retorna candidatos ranqueados por aderencia aos criterios.

    **Criterios disponiveis:**
    - `title`: Cargo desejado
    - `skills`: Lista de habilidades
    - `location`: Cidade ou estado
    - `experience_years`: Anos de experiencia
    - `keywords`: Palavras-chave
    - `industry`: Setor

    **Requer permissao:** linkedin.enrich
    """
    try:
        criteria_dict = criteria.model_dump(exclude_none=True)

        if not criteria_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Informe ao menos um criterio de busca"
            )

        result = LinkedInService.search_professionals(
            db=db,
            user_id=current_user.id,
            criteria=criteria_dict,
        )

        return SearchResultResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na busca: {str(e)}"
        )


@router.get("/search/history")
def get_search_history(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtem historico de buscas de profissionais

    **Requer:** Autenticacao
    """
    return LinkedInService.get_search_history(db, current_user.id, limit)


@router.get("/search/{search_id}")
def get_search_results(
    search_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtem resultados de uma busca especifica

    **Requer:** Autenticacao
    """
    result = LinkedInService.get_search_results(db, search_id, current_user.id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Busca nao encontrada"
        )

    return result


# ================================================================
# Enrichment Endpoints
# ================================================================

@router.post("/candidates/{candidate_id}/enrich", response_model=ExternalEnrichmentResponse)
def enrich_candidate_with_linkedin(
    candidate_id: int,
    linkedin_data: LinkedInProfile,
    update_candidate: bool = Body(
        default=True,
        description="Se True, atualiza informacoes do candidato com dados do LinkedIn"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("linkedin.enrich"))
):
    """
    Enriquece um candidato com dados do LinkedIn

    **Requer permissao:** linkedin.enrich
    """
    candidate = CandidateService.get_candidate(db, candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidato {candidate_id} nao encontrado"
        )

    enrichment = LinkedInService.create_enrichment_from_linkedin(
        db, candidate_id, linkedin_data, user_id=current_user.id
    )

    if update_candidate:
        LinkedInService.update_candidate_from_linkedin(
            db, candidate_id, linkedin_data, user_id=current_user.id
        )

    return enrichment


@router.post("/candidates/{candidate_id}/manual", response_model=ExternalEnrichmentResponse)
def add_manual_linkedin_data(
    candidate_id: int,
    linkedin_data: Dict[str, Any] = Body(..., description="Dados do LinkedIn inseridos manualmente"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("linkedin.enrich"))
):
    """
    Adiciona dados do LinkedIn manualmente

    **Requer permissao:** linkedin.enrich
    """
    candidate = CandidateService.get_candidate(db, candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidato {candidate_id} nao encontrado"
        )

    if "profile_url" not in linkedin_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O campo 'profile_url' e obrigatorio"
        )

    enrichment = LinkedInService.manual_linkedin_input(
        db, candidate_id, linkedin_data, user_id=current_user.id
    )

    return enrichment


@router.get("/candidates/{candidate_id}/linkedin", response_model=ExternalEnrichmentResponse)
def get_candidate_linkedin_data(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("candidates.read"))
):
    """
    Obtem os dados do LinkedIn de um candidato

    **Requer permissao:** candidates.read
    """
    candidate = CandidateService.get_candidate(db, candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidato {candidate_id} nao encontrado"
        )

    linkedin_data = LinkedInService.get_candidate_linkedin_data(db, candidate_id)

    if not linkedin_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nenhum dado do LinkedIn encontrado para o candidato {candidate_id}"
        )

    return linkedin_data


@router.put("/candidates/{candidate_id}/sync-from-linkedin", response_model=CandidateResponse)
def sync_candidate_from_linkedin(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("linkedin.enrich"))
):
    """
    Sincroniza informacoes do candidato com dados do LinkedIn

    **Requer permissao:** linkedin.enrich
    """
    candidate = CandidateService.get_candidate(db, candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidato {candidate_id} nao encontrado"
        )

    linkedin_enrichment = LinkedInService.get_candidate_linkedin_data(db, candidate_id)
    if not linkedin_enrichment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nenhum dado do LinkedIn encontrado para sincronizar"
        )

    linkedin_profile = LinkedInProfile(**linkedin_enrichment.data_json)

    updated_candidate = LinkedInService.update_candidate_from_linkedin(
        db, candidate_id, linkedin_profile, user_id=current_user.id
    )

    return updated_candidate


# ================================================================
# Configuration Status
# ================================================================

@router.get("/config-status")
def get_linkedin_config_status(
    current_user: User = Depends(get_current_user),
):
    """
    Retorna o status atual da configuracao da API LinkedIn

    Verifica:
    - Se a integracao esta habilitada
    - Qual provider esta configurado (proxycurl, official, rapidapi, none)
    - Se as credenciais estao preenchidas
    - Se a integracao esta pronta para uso

    **Requer:** Autenticacao
    """
    return LinkedInService.get_config_status()


# ================================================================
# LinkedIn Integration Guide
# ================================================================

@router.get("/guide")
def get_linkedin_integration_guide(
    current_user: User = Depends(get_current_user),
):
    """
    Guia completo de integracao com LinkedIn

    Retorna instrucoes passo-a-passo para:
    - Configurar a API oficial do LinkedIn
    - Usar servicos alternativos (Proxycurl, RapidAPI, PhantomBuster)
    - Buscar curriculos de pessoas-chave pelo LinkedIn
    - Melhores praticas e conformidade
    """
    return {
        "title": "Guia Completo - Integracao LinkedIn para Busca de Curriculos",
        "app_version": settings.app_version,

        "overview": (
            "Este guia explica como configurar a integracao com o LinkedIn "
            "para buscar e importar curriculos de pessoas-chave. "
            "Existem 4 metodos, do mais recomendado ao mais simples."
        ),

        "methods": [
            {
                "name": "Metodo 1: API Oficial do LinkedIn (Recomendado para empresas)",
                "difficulty": "Alta",
                "cost": "Gratuito (basico) / Pago (premium)",
                "reliability": "Alta",
                "steps": [
                    {
                        "step": 1,
                        "title": "Criar LinkedIn Developer App",
                        "instructions": [
                            "Acesse https://www.linkedin.com/developers/apps",
                            "Clique em 'Create app'",
                            "Preencha: App name, LinkedIn Page (da empresa), Logo",
                            "Aceite os termos de uso",
                            "Anote o Client ID e Client Secret gerados",
                        ],
                    },
                    {
                        "step": 2,
                        "title": "Configurar OAuth 2.0",
                        "instructions": [
                            "Na aba 'Auth' da sua app, adicione o Redirect URL:",
                            "  https://seu-dominio.com/api/v1/linkedin/callback",
                            "  ou http://localhost:8000/api/v1/linkedin/callback (dev)",
                            "Solicite os scopes: r_liteprofile, r_emailaddress",
                            "Para People Search: solicite r_basicprofile, r_organization_social",
                        ],
                    },
                    {
                        "step": 3,
                        "title": "Solicitar acesso a Marketing/Recruiter API",
                        "instructions": [
                            "Na aba 'Products', solicite acesso a:",
                            "  - 'Share on LinkedIn' (basico)",
                            "  - 'Sign In with LinkedIn using OpenID Connect'",
                            "  - 'LinkedIn Marketing (para empresa)' - requer aprovacao",
                            "  - 'LinkedIn Recruiter System Connect' - requer LinkedIn Recruiter",
                            "NOTA: Para busca de perfis, voce precisa do Recruiter System Connect",
                            "      ou usar um servico alternativo (veja Metodo 2)",
                        ],
                    },
                    {
                        "step": 4,
                        "title": "Configurar no sistema",
                        "instructions": [
                            "Edite o arquivo .env do backend:",
                            "  LINKEDIN_API_ENABLED=true",
                            "  LINKEDIN_CLIENT_ID=seu_client_id_aqui",
                            "  LINKEDIN_CLIENT_SECRET=seu_client_secret_aqui",
                            "  LINKEDIN_REDIRECT_URI=https://seu-dominio.com/api/v1/linkedin/callback",
                            "Reinicie o servidor",
                        ],
                    },
                ],
            },
            {
                "name": "Metodo 2: Proxycurl API (Recomendado - mais simples)",
                "difficulty": "Baixa",
                "cost": "Pago (a partir de $0.01/perfil)",
                "reliability": "Alta",
                "steps": [
                    {
                        "step": 1,
                        "title": "Criar conta no Proxycurl",
                        "instructions": [
                            "Acesse https://nubela.co/proxycurl",
                            "Crie uma conta (tem creditos gratuitos para teste)",
                            "Obtenha sua API key no dashboard",
                        ],
                    },
                    {
                        "step": 2,
                        "title": "Testar a API",
                        "instructions": [
                            "Teste com curl:",
                            '  curl -H "Authorization: Bearer SUA_API_KEY" \\',
                            '    "https://nubela.co/proxycurl/api/v2/linkedin?url=https://linkedin.com/in/perfil"',
                            "A resposta contem: nome, headline, experiencias, educacao, skills",
                        ],
                    },
                    {
                        "step": 3,
                        "title": "Buscar pessoas-chave",
                        "instructions": [
                            "Use a Person Search API do Proxycurl:",
                            '  curl -H "Authorization: Bearer SUA_API_KEY" \\',
                            '    "https://nubela.co/proxycurl/api/search/person/" \\',
                            '    -d \'{"current_company_name": "Empresa Alvo", "current_role_title": "Gerente de Producao"}\'',
                            "",
                            "Filtros disponiveis:",
                            "  - current_company_name: Empresa atual",
                            "  - current_role_title: Cargo atual",
                            "  - region: Regiao (ex: Brazil)",
                            "  - city: Cidade",
                            "  - education_school_name: Universidade",
                            "  - skills: Habilidades",
                        ],
                    },
                    {
                        "step": 4,
                        "title": "Importar para o sistema",
                        "instructions": [
                            "Use o endpoint PUT /api/v1/linkedin/candidates/{id}/enrich",
                            "Envie os dados do Proxycurl no formato LinkedInProfile",
                            "O sistema automaticamente enriquece o candidato",
                        ],
                    },
                ],
            },
            {
                "name": "Metodo 3: RapidAPI LinkedIn Endpoints",
                "difficulty": "Media",
                "cost": "Freemium (50-500 requests/mes gratis)",
                "reliability": "Media",
                "steps": [
                    {
                        "step": 1,
                        "title": "Criar conta no RapidAPI",
                        "instructions": [
                            "Acesse https://rapidapi.com",
                            "Crie uma conta gratuita",
                            "Busque por 'LinkedIn' no marketplace",
                            "APIs recomendadas:",
                            "  - 'LinkedIn Profile Data' by rockapis",
                            "  - 'Fresh LinkedIn Profile Data' by mgujjargamingm",
                            "  - 'LinkedIn Data Scraper' by bfrancois",
                            "Inscreva-se no plano gratuito para testar",
                        ],
                    },
                    {
                        "step": 2,
                        "title": "Buscar perfis de pessoas-chave",
                        "instructions": [
                            "Exemplo com a API 'LinkedIn Profile Data':",
                            '  curl --request GET \\',
                            '    --url "https://linkedin-profile-data.p.rapidapi.com/profile?url=https://linkedin.com/in/perfil" \\',
                            '    --header "X-RapidAPI-Key: SUA_RAPID_API_KEY" \\',
                            '    --header "X-RapidAPI-Host: linkedin-profile-data.p.rapidapi.com"',
                        ],
                    },
                    {
                        "step": 3,
                        "title": "Buscar por empresa/cargo",
                        "instructions": [
                            "Exemplo de busca por pessoas em uma empresa:",
                            '  curl --request GET \\',
                            '    --url "https://linkedin-profile-data.p.rapidapi.com/search-people?company=NomeEmpresa&title=Gerente" \\',
                            '    --header "X-RapidAPI-Key: SUA_RAPID_API_KEY"',
                        ],
                    },
                ],
            },
            {
                "name": "Metodo 4: Entrada Manual (Sem API)",
                "difficulty": "Baixa",
                "cost": "Gratuito",
                "reliability": "Alta",
                "steps": [
                    {
                        "step": 1,
                        "title": "Buscar perfil no LinkedIn manualmente",
                        "instructions": [
                            "Acesse https://linkedin.com",
                            "Use a busca avancada do LinkedIn:",
                            "  - Buscar por: cargo, empresa, localizacao, conexoes",
                            "  - Filtrar por: People, Current company, Location",
                            "  - Para busca avancada: use LinkedIn Recruiter ou Sales Navigator",
                        ],
                    },
                    {
                        "step": 2,
                        "title": "Copiar dados do perfil",
                        "instructions": [
                            "No perfil da pessoa, copie:",
                            "  - URL do perfil (ex: https://linkedin.com/in/nome-pessoa)",
                            "  - Nome completo",
                            "  - Headline/titulo",
                            "  - Localizacao",
                            "  - Experiencias profissionais",
                            "  - Formacao",
                            "  - Skills/habilidades",
                        ],
                    },
                    {
                        "step": 3,
                        "title": "Inserir no sistema",
                        "instructions": [
                            "Use o endpoint POST /api/v1/linkedin/candidates/{id}/manual",
                            "Exemplo de payload:",
                            '  {',
                            '    "profile_url": "https://linkedin.com/in/nome-pessoa",',
                            '    "full_name": "Nome Completo",',
                            '    "headline": "Gerente de Producao | Lean Manufacturing",',
                            '    "location": "Porto Alegre, RS",',
                            '    "experiences": [',
                            '      {',
                            '        "company": "Empresa ABC",',
                            '        "title": "Gerente de Producao",',
                            '        "start_date": "2020-01",',
                            '        "end_date": "atual"',
                            '      }',
                            '    ],',
                            '    "skills": ["Lean Manufacturing", "Six Sigma", "SAP"],',
                            '    "education": [{"school": "UFRGS", "degree": "Eng. Producao"}]',
                            '  }',
                        ],
                    },
                ],
            },
        ],

        "searching_key_people": {
            "title": "Como buscar curriculos de pessoas-chave pelo LinkedIn",
            "strategies": [
                {
                    "name": "Busca por empresa + cargo",
                    "description": "Encontrar gerentes, diretores, especialistas em empresas especificas",
                    "linkedin_search_url": (
                        "https://www.linkedin.com/search/results/people/"
                        "?currentCompany=[EMPRESA]&title=[CARGO]&geoUrn=[REGIAO]"
                    ),
                    "example": (
                        "Para encontrar 'Gerentes de Producao' na 'Empresa XYZ' em 'RS':\n"
                        "1. Acesse LinkedIn > Busca > People\n"
                        "2. Filtro 'Current company': Empresa XYZ\n"
                        "3. Filtro 'Title': Gerente de Producao\n"
                        "4. Filtro 'Location': Rio Grande do Sul"
                    ),
                },
                {
                    "name": "Busca por habilidades especificas",
                    "description": "Encontrar profissionais com skills raras ou especificas",
                    "example": (
                        "Para encontrar profissionais com 'Six Sigma Black Belt':\n"
                        "1. Busca: 'Six Sigma Black Belt'\n"
                        "2. Filtro 'People'\n"
                        "3. Filtro 'Location': sua regiao\n"
                        "4. Filtro 'Industry': Manufacturing"
                    ),
                },
                {
                    "name": "Busca por certificacoes",
                    "description": "Encontrar profissionais com certificacoes especificas (NR, ISO, etc)",
                    "example": (
                        "Para encontrar auditores ISO 9001:\n"
                        "1. Busca: 'Auditor interno ISO 9001' ou 'ISO 9001 Lead Auditor'\n"
                        "2. Filtro por regiao\n"
                        "3. Verificar certificacoes no perfil"
                    ),
                },
                {
                    "name": "Boolean Search (busca avancada)",
                    "description": "Usar operadores booleanos para buscas complexas",
                    "example": (
                        'Operadores:\n'
                        '  AND: "Lean Manufacturing" AND "Six Sigma"\n'
                        '  OR: "Gerente" OR "Supervisor" OR "Coordenador"\n'
                        '  NOT: "Producao" NOT "Vendas"\n'
                        '  "": Busca exata: "Engenheiro de Producao"\n'
                        '  (): Agrupamento: (Gerente OR Supervisor) AND "Lean"\n'
                        '\n'
                        'Exemplo completo:\n'
                        '  ("Gerente de Producao" OR "Supervisor de Producao") '
                        'AND ("Lean" OR "Six Sigma") AND "Porto Alegre"'
                    ),
                },
            ],
        },

        "compliance": {
            "title": "Conformidade e melhores praticas",
            "rules": [
                "Respeite os Termos de Servico do LinkedIn",
                "LGPD: Obtenha consentimento antes de armazenar dados pessoais",
                "Nao faca scraping em massa - use APIs oficiais ou autorizadas",
                "Mantenha registro (audit log) de todos os dados coletados",
                "Configure politica de retencao (default: 90 dias)",
                "O sistema ja registra automaticamente no audit_log e external_enrichments",
                "Permita que candidatos solicitem exclusao de seus dados (LGPD Art. 18)",
            ],
        },

        "current_config": {
            "linkedin_api_enabled": settings.linkedin_api_enabled,
            "client_id_configured": bool(settings.linkedin_client_id),
            "client_secret_configured": bool(settings.linkedin_client_secret),
            "redirect_uri": settings.linkedin_redirect_uri,
            "request_timeout": settings.linkedin_request_timeout,
            "search_results_limit": settings.linkedin_search_results_limit,
        },

        "api_endpoints": [
            {
                "method": "POST",
                "path": "/api/v1/linkedin/extract",
                "description": "Extrair dados de perfil publico por URL",
            },
            {
                "method": "POST",
                "path": "/api/v1/linkedin/search",
                "description": "Buscar profissionais por criterios (base interna + LinkedIn)",
            },
            {
                "method": "POST",
                "path": "/api/v1/linkedin/candidates/{id}/enrich",
                "description": "Enriquecer candidato com dados do LinkedIn",
            },
            {
                "method": "POST",
                "path": "/api/v1/linkedin/candidates/{id}/manual",
                "description": "Inserir dados do LinkedIn manualmente",
            },
            {
                "method": "GET",
                "path": "/api/v1/linkedin/candidates/{id}/linkedin",
                "description": "Obter dados do LinkedIn de um candidato",
            },
            {
                "method": "GET",
                "path": "/api/v1/linkedin/search/history",
                "description": "Historico de buscas",
            },
        ],
    }
