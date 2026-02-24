from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import re
import httpx
from bs4 import BeautifulSoup

from app.db.models import ExternalEnrichment, Candidate, AuditLog
from app.schemas.candidate import LinkedInProfile, ExternalEnrichmentCreate


class LinkedInService:
    """
    Serviço para análise e enriquecimento de perfis do LinkedIn

    Nota: Para produção, considere usar APIs oficiais ou serviços de scraping
    profissionais que respeitam os termos de serviço do LinkedIn.
    """

    @staticmethod
    async def extract_profile_data(profile_url: str) -> Optional[Dict[str, Any]]:
        """
        Extrai dados de um perfil do LinkedIn

        IMPORTANTE: Esta é uma implementação de exemplo/demonstração.
        Em produção, você deve:
        1. Usar a API oficial do LinkedIn (LinkedIn API)
        2. Ou usar serviços terceirizados autorizados (PhantomBuster, Apify, etc.)
        3. Garantir conformidade com termos de serviço e LGPD
        """

        # Validar URL do LinkedIn
        linkedin_pattern = r'https?://(www\.)?linkedin\.com/in/[\w-]+'
        if not re.match(linkedin_pattern, profile_url):
            raise ValueError("URL do LinkedIn inválida")

        try:
            # Headers para simular um navegador (apenas para demonstração)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(profile_url, headers=headers, follow_redirects=True)

                if response.status_code != 200:
                    return None

                # Parsing básico do HTML (exemplo simplificado)
                soup = BeautifulSoup(response.text, 'html.parser')

                # Estrutura de dados extraídos
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

                # NOTA: O LinkedIn usa conteúdo dinâmico (JavaScript/React)
                # Para extração real, você precisaria usar:
                # - Selenium ou Playwright para renderizar JavaScript
                # - APIs oficiais do LinkedIn
                # - Serviços terceirizados especializados

                # Exemplo simplificado de extração (não funcional em produção):
                title_tag = soup.find('title')
                if title_tag:
                    # Extrair nome do título da página
                    title_text = title_tag.get_text()
                    if '|' in title_text:
                        profile_data["full_name"] = title_text.split('|')[0].strip()

                return profile_data

        except Exception as e:
            print(f"Erro ao extrair perfil do LinkedIn: {str(e)}")
            return None

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
            notes="Dados extraídos do perfil público do LinkedIn"
        )

        db.add(enrichment)
        db.commit()
        db.refresh(enrichment)

        # Registrar no audit log
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
        """Obtém dados do LinkedIn de um candidato"""
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
        """
        Atualiza informações do candidato com dados do LinkedIn
        Mescla informações quando possível
        """
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            return None

        updated_fields = []

        # Atualizar nome se estiver vazio
        if not candidate.full_name and linkedin_data.full_name:
            candidate.full_name = linkedin_data.full_name
            updated_fields.append("full_name")

        # Atualizar localização
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

            # Registrar no audit log
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
        """
        Permite entrada manual de dados do LinkedIn
        Útil quando a extração automática não está disponível
        """
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

        # Registrar no audit log
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
