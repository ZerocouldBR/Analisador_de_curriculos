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
from bs4 import BeautifulSoup

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
        Extrai dados de um perfil do LinkedIn

        IMPORTANTE: Implementacao de demonstracao.
        Em producao, use:
        1. LinkedIn API oficial (requer parceria)
        2. Servicos como PhantomBuster, Apify, Proxycurl
        3. RapidAPI LinkedIn endpoints
        """
        linkedin_pattern = r'https?://(www\.)?linkedin\.com/in/[\w-]+'
        if not re.match(linkedin_pattern, profile_url):
            raise ValueError("URL do LinkedIn invalida")

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    profile_url, headers=headers, follow_redirects=True
                )

                if response.status_code != 200:
                    return None

                soup = BeautifulSoup(response.text, 'html.parser')

                profile_data = {
                    "profile_url": profile_url,
                    "full_name": None,
                    "headline": None,
                    "location": None,
                    "about": None,
                    "experiences": [],
                    "education": [],
                    "skills": [],
                    "certifications": [],
                    "languages": [],
                    "extracted_at": datetime.now(timezone.utc).isoformat()
                }

                title_tag = soup.find('title')
                if title_tag:
                    title_text = title_tag.get_text()
                    if '|' in title_text:
                        profile_data["full_name"] = title_text.split('|')[0].strip()
                    elif '-' in title_text:
                        profile_data["full_name"] = title_text.split('-')[0].strip()

                # Meta tags podem conter informacoes uteis
                meta_desc = soup.find('meta', {'name': 'description'})
                if meta_desc and meta_desc.get('content'):
                    profile_data["headline"] = meta_desc['content'][:200]

                return profile_data

        except Exception as e:
            logger.error(f"Erro ao extrair perfil do LinkedIn: {str(e)}")
            return None

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
                "candidates": all_results[:50],  # Limitar a 50
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
                "results": all_results[:50],
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

        candidates = query.limit(200).all()

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
                        m["score"] += result.get("score", 0) * 0.3
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
