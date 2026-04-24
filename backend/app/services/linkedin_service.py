"""
Servico aprimorado de integracao com LinkedIn

Funcionalidades:
- Extracao de dados de perfil publico
- Busca de profissionais por criterios (titulo, skills, localizacao)
- Enriquecimento de candidatos existentes
- Comparacao de perfil LinkedIn com curriculo
- Historico de buscas e resultados
- Conformidade LGPD com audit logging

IMPORTANTE: Em producao, use a API oficial do LinkedIn ou servicos autorizados.
Este modulo oferece a arquitetura e integracao - a fonte de dados deve ser
configurada conforme os termos de servico do LinkedIn.
"""
import re
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import desc
import httpx

from app.db.models import (
    ExternalEnrichment, Candidate, AuditLog, LinkedInSearch, Chunk
)
from app.schemas.candidate import LinkedInProfile, ExternalEnrichmentCreate
from app.core.config import settings

logger = logging.getLogger(__name__)


class LinkedInService:
    """
    Servico para integracao com LinkedIn

    Modulos:
    1. Extracao de perfil - Dados basicos de perfis publicos
    2. Busca de profissionais - Pesquisa por criterios
    3. Enriquecimento - Complementa dados de candidatos
    4. Matching - Compara perfil com vaga
    """

    # ================================================================
    # Profile Extraction
    # ================================================================

    @staticmethod
    async def extract_profile_data(profile_url: str) -> Optional[Dict[str, Any]]:
        """
        Extrai dados de um perfil do LinkedIn.

        Usa o provider configurado (Proxycurl, RapidAPI, ou scraping basico).

        Raises:
            ValueError: Quando a URL e invalida, a integracao esta desabilitada
                       ou o provider selecionado nao esta devidamente configurado.
        """
        linkedin_pattern = r'https?://(www\.)?linkedin\.com/in/[\w-]+'
        if not re.match(linkedin_pattern, profile_url):
            raise ValueError(
                "URL do LinkedIn invalida. Use o formato "
                "https://www.linkedin.com/in/usuario"
            )

        if not settings.linkedin_api_enabled:
            raise ValueError(
                "Integracao LinkedIn desabilitada. "
                "Habilite em Configuracoes > LinkedIn > 'Habilitar LinkedIn'."
            )

        provider = (settings.linkedin_api_provider or "none").lower()

        if provider == "proxycurl":
            if not settings.proxycurl_api_key:
                raise ValueError(
                    "Proxycurl selecionado mas API key nao configurada. "
                    "Adicione a chave em Configuracoes > LinkedIn > 'Proxycurl API Key'."
                )
            return await LinkedInService._extract_via_proxycurl(profile_url)

        if provider == "rapidapi":
            if not settings.rapidapi_key or not settings.rapidapi_host:
                raise ValueError(
                    "RapidAPI selecionado mas credenciais incompletas. "
                    "Configure 'RapidAPI Key' e 'RapidAPI Host' em Configuracoes > LinkedIn."
                )
            return await LinkedInService._extract_via_rapidapi(profile_url)

        if provider == "official":
            raise ValueError(
                "Extracao direta via API Oficial do LinkedIn ainda nao esta "
                "disponivel. Use provider 'proxycurl' ou 'rapidapi', ou utilize "
                "a aba 'Enriquecimento Manual' para inserir os dados."
            )

        # provider == "none" ou desconhecido
        raise ValueError(
            "Nenhum provider de LinkedIn configurado. "
            "Selecione 'proxycurl' ou 'rapidapi' em Configuracoes > LinkedIn > 'Provider da API' "
            "e informe as credenciais correspondentes."
        )

    @staticmethod
    async def _extract_via_proxycurl(profile_url: str) -> Optional[Dict[str, Any]]:
        """Extrai perfil completo via Proxycurl API"""
        try:
            base_url = settings.proxycurl_base_url.rstrip("/")
            async with httpx.AsyncClient(timeout=settings.linkedin_request_timeout) as client:
                response = await client.get(
                    f"{base_url}/api/v2/linkedin",
                    params={"url": profile_url},
                    headers={"Authorization": f"Bearer {settings.proxycurl_api_key}"},
                )

                if response.status_code == 404:
                    logger.warning(f"Proxycurl: perfil nao encontrado: {profile_url}")
                    raise ValueError(
                        "Perfil nao encontrado no LinkedIn. Verifique a URL."
                    )

                if response.status_code in (401, 403):
                    logger.error("Proxycurl: API key invalida ou sem creditos")
                    raise ValueError(
                        "Erro de autenticacao com Proxycurl. "
                        "Verifique sua API key e creditos em nubela.co/proxycurl"
                    )

                if response.status_code == 429:
                    logger.warning("Proxycurl: rate limit atingido")
                    raise ValueError(
                        "Limite de requisicoes atingido no Proxycurl. "
                        "Aguarde alguns minutos e tente novamente."
                    )

                if response.status_code != 200:
                    logger.error(f"Proxycurl erro {response.status_code}: {response.text[:200]}")
                    raise ValueError(
                        f"Proxycurl retornou status {response.status_code}. "
                        "Consulte os logs para detalhes."
                    )

                data = response.json()

                # Mapear resposta Proxycurl para formato interno
                experiences = []
                for exp in (data.get("experiences") or []):
                    experiences.append({
                        "company": exp.get("company"),
                        "title": exp.get("title"),
                        "start_date": exp.get("starts_at"),
                        "end_date": exp.get("ends_at"),
                        "description": exp.get("description"),
                        "location": exp.get("location"),
                    })

                education = []
                for edu in (data.get("education") or []):
                    education.append({
                        "school": edu.get("school"),
                        "degree": edu.get("degree_name"),
                        "field": edu.get("field_of_study"),
                        "start_date": edu.get("starts_at"),
                        "end_date": edu.get("ends_at"),
                    })

                skills = data.get("skills") or []
                certifications = [
                    c.get("name") for c in (data.get("certifications") or [])
                    if c.get("name")
                ]
                languages = [
                    lang.get("name") for lang in (data.get("languages") or [])
                    if lang.get("name")
                ]

                return {
                    "profile_url": profile_url,
                    "full_name": data.get("full_name"),
                    "headline": data.get("headline"),
                    "location": (
                        f"{data.get('city', '')}, {data.get('state', '')}, {data.get('country_full_name', '')}"
                    ).strip(", "),
                    "about": data.get("summary"),
                    "experiences": experiences,
                    "education": education,
                    "skills": skills,
                    "certifications": certifications,
                    "languages": languages,
                    "profile_pic_url": data.get("profile_pic_url"),
                    "follower_count": data.get("follower_count"),
                    "connections": data.get("connections"),
                    "extracted_at": datetime.now(timezone.utc).isoformat(),
                    "source": "proxycurl",
                }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Erro Proxycurl ao extrair perfil: {str(e)}")
            raise ValueError(
                "Falha ao consultar Proxycurl. "
                "Verifique conectividade, URL base e credenciais."
            )

    @staticmethod
    async def _extract_via_rapidapi(profile_url: str) -> Optional[Dict[str, Any]]:
        """Extrai perfil completo via RapidAPI (endpoint configuravel)"""
        host = (settings.rapidapi_host or "").strip()
        if not host:
            raise ValueError(
                "RapidAPI Host nao configurado. "
                "Defina em Configuracoes > LinkedIn > 'RapidAPI Host'."
            )

        endpoint_path = (settings.rapidapi_profile_endpoint or "/profile").strip()
        if not endpoint_path.startswith("/"):
            endpoint_path = "/" + endpoint_path
        url_param = settings.rapidapi_url_param or "url"

        try:
            async with httpx.AsyncClient(timeout=settings.linkedin_request_timeout) as client:
                response = await client.get(
                    f"https://{host}{endpoint_path}",
                    params={url_param: profile_url},
                    headers={
                        "X-RapidAPI-Key": settings.rapidapi_key,
                        "X-RapidAPI-Host": host,
                    },
                )

                if response.status_code == 404:
                    raise ValueError(
                        "Perfil nao encontrado no LinkedIn. Verifique a URL."
                    )

                if response.status_code in (401, 403):
                    raise ValueError(
                        "Erro de autenticacao com RapidAPI. "
                        "Verifique sua RapidAPI Key e o plano de assinatura."
                    )

                if response.status_code == 429:
                    raise ValueError(
                        "Limite de requisicoes atingido no RapidAPI. "
                        "Aguarde alguns minutos ou faca upgrade do plano."
                    )

                if response.status_code != 200:
                    logger.error(f"RapidAPI erro {response.status_code}: {response.text[:200]}")
                    raise ValueError(
                        f"RapidAPI retornou status {response.status_code}. "
                        "Consulte os logs para detalhes."
                    )

                data = response.json() or {}

                # RapidAPI nao tem schema unico; extraimos os campos mais comuns
                full_name = (
                    data.get("full_name")
                    or data.get("fullName")
                    or data.get("name")
                    or " ".join(filter(None, [data.get("first_name"), data.get("last_name")])).strip()
                    or None
                )

                return {
                    "profile_url": profile_url,
                    "full_name": full_name,
                    "headline": data.get("headline") or data.get("title"),
                    "location": data.get("location") or data.get("geo"),
                    "about": data.get("summary") or data.get("about"),
                    "experiences": data.get("experiences") or data.get("experience") or [],
                    "education": data.get("education") or data.get("educations") or [],
                    "skills": data.get("skills") or [],
                    "certifications": data.get("certifications") or [],
                    "languages": data.get("languages") or [],
                    "profile_pic_url": data.get("profile_pic_url") or data.get("profileImage"),
                    "extracted_at": datetime.now(timezone.utc).isoformat(),
                    "source": "rapidapi",
                }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Erro RapidAPI ao extrair perfil: {str(e)}")
            raise ValueError(
                "Falha ao consultar RapidAPI. Verifique host, endpoint e credenciais."
            )

    # ================================================================
    # Proxycurl Person Search
    # ================================================================

    @staticmethod
    async def search_via_proxycurl(criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Busca profissionais via Proxycurl Person Search API"""
        if not settings.proxycurl_api_key:
            return []

        try:
            params: Dict[str, Any] = {}
            if criteria.get("title"):
                params["current_role_title"] = criteria["title"]
            if criteria.get("location"):
                params["city"] = criteria["location"]
            if criteria.get("industry"):
                params["industry"] = criteria["industry"]
            if criteria.get("keywords"):
                params["keyword"] = " ".join(criteria["keywords"])

            if not params:
                return []

            if settings.linkedin_search_country:
                params["country"] = settings.linkedin_search_country
            params["page_size"] = min(
                criteria.get("limit", 10),
                settings.linkedin_search_results_limit
            )

            base_url = settings.proxycurl_base_url.rstrip("/")
            async with httpx.AsyncClient(timeout=settings.linkedin_request_timeout) as client:
                response = await client.get(
                    f"{base_url}/api/search/person/",
                    params=params,
                    headers={"Authorization": f"Bearer {settings.proxycurl_api_key}"},
                )

                if response.status_code != 200:
                    logger.warning(f"Proxycurl search erro {response.status_code}")
                    return []

                data = response.json()
                results = []

                for person in (data.get("results") or []):
                    results.append({
                        "name": person.get("name", "N/A"),
                        "linkedin_url": person.get("linkedin_profile_url"),
                        "headline": person.get("headline"),
                        "location": person.get("location"),
                        "score": 50,
                        "match_details": ["Resultado Proxycurl"],
                        "source": "proxycurl_search",
                    })

                return results

        except Exception as e:
            logger.error(f"Erro Proxycurl search: {str(e)}")
            return []

    # ================================================================
    # Config Status
    # ================================================================

    @staticmethod
    def get_config_status() -> Dict[str, Any]:
        """Retorna o status atual da configuracao LinkedIn"""
        provider = settings.linkedin_api_provider
        enabled = settings.linkedin_api_enabled

        status = {
            "enabled": enabled,
            "provider": provider,
            "provider_label": {
                "none": "Nenhum (apenas entrada manual)",
                "proxycurl": "Proxycurl API",
                "rapidapi": "RapidAPI",
                "official": "API Oficial LinkedIn",
            }.get(provider, provider),
            "credentials_configured": False,
            "ready": False,
            "message": "",
        }

        if not enabled:
            status["message"] = (
                "Integracao LinkedIn desabilitada. "
                "Ative em Configuracoes > LinkedIn."
            )
            return status

        if provider == "proxycurl":
            has_key = bool(settings.proxycurl_api_key)
            status["credentials_configured"] = has_key
            status["ready"] = has_key
            if has_key:
                status["message"] = "Proxycurl configurado e pronto para uso."
            else:
                status["message"] = (
                    "Proxycurl selecionado mas API key nao configurada. "
                    "Adicione a chave em Configuracoes > LinkedIn."
                )

        elif provider == "official":
            has_creds = bool(settings.linkedin_client_id and settings.linkedin_client_secret)
            status["credentials_configured"] = has_creds
            status["ready"] = has_creds
            if has_creds:
                status["message"] = "API Oficial LinkedIn configurada."
            else:
                status["message"] = (
                    "API Oficial selecionada mas credenciais incompletas. "
                    "Configure Client ID e Secret em Configuracoes > LinkedIn."
                )

        elif provider == "rapidapi":
            has_creds = bool(settings.rapidapi_key and settings.rapidapi_host)
            status["credentials_configured"] = has_creds
            status["ready"] = has_creds
            if has_creds:
                status["message"] = (
                    f"RapidAPI configurado ({settings.rapidapi_host}) e pronto para uso."
                )
            else:
                status["message"] = (
                    "RapidAPI selecionado mas credenciais incompletas. "
                    "Configure 'RapidAPI Key' e 'RapidAPI Host' em Configuracoes > LinkedIn."
                )

        else:
            status["message"] = (
                "Nenhum provider configurado. "
                "Apenas entrada manual e busca na base interna disponiveis."
            )

        return status

    # ================================================================
    # Professional Search
    # ================================================================

    @staticmethod
    def search_professionals(
        db: Session,
        user_id: int,
        criteria: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Busca profissionais com base em criterios

        Busca primeiro na base interna (candidatos + enrichments),
        e registra a busca para futura integracao com API do LinkedIn.

        Args:
            db: Sessao do banco
            user_id: ID do usuario
            criteria: Criterios de busca:
                - title: Cargo desejado
                - skills: Lista de skills
                - location: Cidade/Estado
                - experience_years: Anos minimos de experiencia
                - keywords: Palavras-chave gerais
                - industry: Setor/industria

        Returns:
            Resultados da busca interna + registro para busca externa
        """
        # Registrar a busca
        search_record = LinkedInSearch(
            user_id=user_id,
            search_criteria=criteria,
            status="processing",
        )
        db.add(search_record)
        db.commit()
        db.refresh(search_record)

        try:
            # Buscar na base interna primeiro
            internal_results = LinkedInService._search_internal_candidates(
                db, criteria
            )

            # Buscar em enrichments do LinkedIn existentes
            linkedin_results = LinkedInService._search_linkedin_enrichments(
                db, criteria
            )

            # Combinar resultados
            all_results = LinkedInService._merge_results(
                internal_results, linkedin_results
            )

            # Atualizar registro de busca
            search_record.results_count = len(all_results)
            search_record.results_json = {
                "internal_matches": len(internal_results),
                "linkedin_matches": len(linkedin_results),
                "total": len(all_results),
                "candidates": all_results[:settings.linkedin_search_results_limit],  # Limitar a 50
            }
            search_record.status = "completed"
            db.commit()

            # Audit log
            audit = AuditLog(
                user_id=user_id,
                action="linkedin_search",
                entity="linkedin_search",
                entity_id=search_record.id,
                metadata_json={
                    "criteria": criteria,
                    "results_count": len(all_results),
                }
            )
            db.add(audit)
            db.commit()

            return {
                "search_id": search_record.id,
                "criteria": criteria,
                "results": all_results[:settings.linkedin_search_results_limit],
                "total_found": len(all_results),
                "sources": {
                    "internal_database": len(internal_results),
                    "linkedin_enrichments": len(linkedin_results),
                },
                "note": (
                    "Resultados da base interna. "
                    "Para busca no LinkedIn, configure a API oficial "
                    "ou servico de integracao nas configuracoes."
                ),
            }

        except Exception as e:
            search_record.status = "failed"
            search_record.results_json = {"error": str(e)}
            db.commit()
            raise

    @staticmethod
    def _search_internal_candidates(
        db: Session, criteria: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Busca candidatos na base interna por criterios"""
        from sqlalchemy import or_, func

        query = db.query(Candidate)
        results = []

        # Filtrar por localizacao
        if criteria.get("location"):
            loc = criteria["location"]
            query = query.filter(
                or_(
                    func.lower(Candidate.city).contains(loc.lower()),
                    func.lower(Candidate.state).contains(loc.lower()),
                )
            )

        candidates = query.limit(settings.linkedin_internal_search_limit).all()

        for candidate in candidates:
            score = 0.0
            match_details = []

            # Verificar skills nos chunks
            if criteria.get("skills") or criteria.get("keywords") or criteria.get("title"):
                chunks = db.query(Chunk).filter(
                    Chunk.candidate_id == candidate.id
                ).all()

                all_content = " ".join(
                    c.content.lower() for c in chunks if c.content
                )

                # Match por skills
                if criteria.get("skills"):
                    matched_skills = []
                    for skill in criteria["skills"]:
                        if skill.lower() in all_content:
                            matched_skills.append(skill)
                            score += 10
                    if matched_skills:
                        match_details.append(f"Skills: {', '.join(matched_skills)}")

                # Match por titulo/cargo
                if criteria.get("title"):
                    title_lower = criteria["title"].lower()
                    if title_lower in all_content:
                        score += 20
                        match_details.append(f"Cargo: {criteria['title']}")

                # Match por keywords
                if criteria.get("keywords"):
                    for kw in criteria["keywords"]:
                        if kw.lower() in all_content:
                            score += 5
                            match_details.append(f"Keyword: {kw}")

                # Match por industria
                if criteria.get("industry"):
                    if criteria["industry"].lower() in all_content:
                        score += 15
                        match_details.append(f"Industria: {criteria['industry']}")

            # Verificar localizacao
            if criteria.get("location"):
                loc = criteria["location"].lower()
                if candidate.city and loc in candidate.city.lower():
                    score += 10
                    match_details.append(f"Cidade: {candidate.city}")
                elif candidate.state and loc in candidate.state.lower():
                    score += 5

            if score > 0:
                results.append({
                    "candidate_id": candidate.id,
                    "name": candidate.full_name,
                    "email": candidate.email,
                    "city": candidate.city,
                    "state": candidate.state,
                    "score": score,
                    "match_details": match_details,
                    "source": "internal_database",
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    @staticmethod
    def _search_linkedin_enrichments(
        db: Session, criteria: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Busca em dados do LinkedIn ja coletados"""
        enrichments = db.query(ExternalEnrichment).filter(
            ExternalEnrichment.source == "linkedin"
        ).all()

        results = []

        for enrichment in enrichments:
            if not enrichment.data_json:
                continue

            data = enrichment.data_json
            score = 0.0
            match_details = []

            # Concatenar todo texto do perfil
            profile_text = " ".join(filter(None, [
                data.get("headline", ""),
                data.get("about", ""),
                " ".join(data.get("skills", [])),
                data.get("location", ""),
            ])).lower()

            if criteria.get("skills"):
                for skill in criteria["skills"]:
                    if skill.lower() in profile_text:
                        score += 10
                        match_details.append(f"LinkedIn skill: {skill}")

            if criteria.get("title"):
                if criteria["title"].lower() in profile_text:
                    score += 20
                    match_details.append(f"LinkedIn titulo: {criteria['title']}")

            if criteria.get("keywords"):
                for kw in criteria["keywords"]:
                    if kw.lower() in profile_text:
                        score += 5

            if score > 0:
                candidate = db.query(Candidate).filter(
                    Candidate.id == enrichment.candidate_id
                ).first()

                results.append({
                    "candidate_id": enrichment.candidate_id,
                    "name": candidate.full_name if candidate else data.get("full_name", "N/A"),
                    "linkedin_url": enrichment.source_url,
                    "headline": data.get("headline"),
                    "score": score,
                    "match_details": match_details,
                    "source": "linkedin_enrichment",
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    @staticmethod
    def _merge_results(
        internal: List[Dict], linkedin: List[Dict]
    ) -> List[Dict]:
        """Combina e deduplica resultados"""
        seen_candidates = set()
        merged = []

        # Priorizar resultados internos
        for result in internal:
            cid = result.get("candidate_id")
            if cid not in seen_candidates:
                seen_candidates.add(cid)
                merged.append(result)

        # Adicionar LinkedIn que nao estao nos internos
        for result in linkedin:
            cid = result.get("candidate_id")
            if cid not in seen_candidates:
                seen_candidates.add(cid)
                merged.append(result)
            else:
                # Enriquecer resultado existente com dados do LinkedIn
                for m in merged:
                    if m.get("candidate_id") == cid:
                        m["linkedin_url"] = result.get("linkedin_url")
                        m["score"] += result.get("score", 0) * settings.linkedin_enrichment_score_weight
                        break

        merged.sort(key=lambda x: x.get("score", 0), reverse=True)
        return merged

    # ================================================================
    # Search History
    # ================================================================

    @staticmethod
    def get_search_history(
        db: Session, user_id: int, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Obtem historico de buscas do usuario"""
        searches = db.query(LinkedInSearch).filter(
            LinkedInSearch.user_id == user_id
        ).order_by(desc(LinkedInSearch.created_at)).limit(limit).all()

        return [
            {
                "id": s.id,
                "criteria": s.search_criteria,
                "results_count": s.results_count,
                "status": s.status,
                "created_at": s.created_at.isoformat(),
            }
            for s in searches
        ]

    @staticmethod
    def get_search_results(
        db: Session, search_id: int, user_id: int
    ) -> Optional[Dict[str, Any]]:
        """Obtem resultados de uma busca especifica"""
        search = db.query(LinkedInSearch).filter(
            LinkedInSearch.id == search_id,
            LinkedInSearch.user_id == user_id,
        ).first()

        if not search:
            return None

        return {
            "id": search.id,
            "criteria": search.search_criteria,
            "results_count": search.results_count,
            "results": search.results_json,
            "status": search.status,
            "created_at": search.created_at.isoformat(),
        }

    # ================================================================
    # Enrichment (mantendo compatibilidade)
    # ================================================================

    @staticmethod
    def create_enrichment_from_linkedin(
        db: Session,
        candidate_id: int,
        linkedin_data: LinkedInProfile,
        user_id: Optional[int] = None
    ) -> ExternalEnrichment:
        """Cria um registro de enriquecimento a partir de dados do LinkedIn"""
        enrichment = ExternalEnrichment(
            candidate_id=candidate_id,
            source="linkedin",
            source_url=linkedin_data.profile_url,
            data_json=linkedin_data.model_dump(),
            retention_policy="90_days",
            notes="Dados extraidos do perfil publico do LinkedIn"
        )

        db.add(enrichment)
        db.commit()
        db.refresh(enrichment)

        audit = AuditLog(
            user_id=user_id,
            action="create",
            entity="external_enrichment",
            entity_id=enrichment.id,
            metadata_json={
                "candidate_id": candidate_id,
                "source": "linkedin",
                "url": linkedin_data.profile_url
            }
        )
        db.add(audit)
        db.commit()

        return enrichment

    @staticmethod
    def get_candidate_linkedin_data(
        db: Session,
        candidate_id: int
    ) -> Optional[ExternalEnrichment]:
        """Obtem dados do LinkedIn de um candidato"""
        return db.query(ExternalEnrichment).filter(
            ExternalEnrichment.candidate_id == candidate_id,
            ExternalEnrichment.source == "linkedin"
        ).order_by(ExternalEnrichment.fetched_at.desc()).first()

    @staticmethod
    def update_candidate_from_linkedin(
        db: Session,
        candidate_id: int,
        linkedin_data: LinkedInProfile,
        user_id: Optional[int] = None
    ) -> Optional[Candidate]:
        """Atualiza informacoes do candidato com dados do LinkedIn"""
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            return None

        updated_fields = []

        if not candidate.full_name and linkedin_data.full_name:
            candidate.full_name = linkedin_data.full_name
            updated_fields.append("full_name")

        if linkedin_data.location:
            location_parts = linkedin_data.location.split(',')
            if len(location_parts) >= 2:
                if not candidate.city:
                    candidate.city = location_parts[0].strip()
                    updated_fields.append("city")
                if not candidate.state:
                    candidate.state = location_parts[1].strip()
                    updated_fields.append("state")

        if updated_fields:
            db.commit()
            db.refresh(candidate)

            audit = AuditLog(
                user_id=user_id,
                action="update_from_linkedin",
                entity="candidate",
                entity_id=candidate_id,
                metadata_json={
                    "updated_fields": updated_fields,
                    "source_url": linkedin_data.profile_url
                }
            )
            db.add(audit)
            db.commit()

        return candidate

    @staticmethod
    def manual_linkedin_input(
        db: Session,
        candidate_id: int,
        linkedin_data: Dict[str, Any],
        user_id: Optional[int] = None
    ) -> ExternalEnrichment:
        """Permite entrada manual de dados do LinkedIn"""
        enrichment = ExternalEnrichment(
            candidate_id=candidate_id,
            source="linkedin",
            source_url=linkedin_data.get("profile_url", ""),
            data_json=linkedin_data,
            retention_policy="90_days",
            notes="Dados inseridos manualmente"
        )

        db.add(enrichment)
        db.commit()
        db.refresh(enrichment)

        audit = AuditLog(
            user_id=user_id,
            action="manual_input",
            entity="external_enrichment",
            entity_id=enrichment.id,
            metadata_json={
                "candidate_id": candidate_id,
                "source": "linkedin",
                "method": "manual"
            }
        )
        db.add(audit)
        db.commit()

        return enrichment
