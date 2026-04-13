"""
Servico de Chat para analise de curriculos contra oportunidades

Funcionalidades:
- Conversacao contextual com historico de mensagens
- Analise de curriculos contra descricao de vagas
- Ranking de candidatos por aderencia
- Busca semantica integrada ao chat
- Sugestoes de perguntas de follow-up
- Auditoria completa de interacoes
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from openai import AsyncOpenAI
from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text, desc

from app.db.models import (
    ChatConversation, ChatMessage, Candidate, Chunk, Embedding, AuditLog
)
from app.core.config import settings
from app.services.embedding_service import embedding_service
from app.services.keyword_extraction_service import KeywordExtractionService

logger = logging.getLogger(__name__)


@dataclass
class ChatResponse:
    """Resposta do chat"""
    message: str
    conversation_id: int
    message_id: int
    candidates_found: List[Dict[str, Any]] = field(default_factory=list)
    sources: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    tokens_used: int = 0
    confidence: float = 0.0


SYSTEM_PROMPT_CHAT = """Voce e um assistente de RH especializado em analise de curriculos e recrutamento.

Seu papel e ajudar recrutadores a:
1. Encontrar os melhores candidatos para vagas abertas
2. Analisar curriculos em detalhe
3. Comparar candidatos entre si
4. Identificar gaps e pontos fortes
5. Sugerir perguntas para entrevistas

REGRAS IMPORTANTES:
- Base suas respostas APENAS nos dados de curriculos fornecidos no contexto
- Nunca invente informacoes sobre candidatos
- Quando nao tiver dados suficientes, informe claramente
- Sempre cite o nome do candidato ao referenciar informacoes
- Use linguagem profissional e objetiva
- Estruture respostas longas com topicos ou tabelas
- Ao comparar candidatos, use criterios objetivos
- Considere tanto hard skills quanto soft skills
- Avalie certificacoes e habilitacoes relevantes para a vaga

FORMATO DE RESPOSTA:
- Para rankings: use tabela com nome, score, pontos fortes e gaps
- Para analises: use topicos claros com icones ou bullets
- Para comparacoes: use formato lado a lado
- Sempre termine com sugestoes de proximos passos quando relevante"""

SYSTEM_PROMPT_JOB_ANALYSIS = """Voce e um especialista em matching de candidatos com vagas.

Voce recebera a descricao de uma vaga e dados de curriculos. Sua tarefa e:

1. ANALISAR a vaga e identificar requisitos obrigatorios e desejaveis
2. AVALIAR cada candidato contra os requisitos
3. RANQUEAR candidatos por aderencia (0-100%)
4. DETALHAR pontos fortes e gaps de cada candidato
5. RECOMENDAR os melhores candidatos com justificativa

Para cada candidato, avalie:
- Experiencia relevante (anos, nivel, setor)
- Hard skills tecnicas
- Certificacoes e habilitacoes
- Formacao academica
- Disponibilidade (turno, viagem, mudanca)
- Soft skills identificaveis
- Fit cultural e senioridade

REGRAS:
- Base suas avaliacoes APENAS nos dados fornecidos
- Seja objetivo e justo na avaliacao
- Destaque riscos e pontos de atencao
- Sugira perguntas para entrevista focadas nos gaps identificados"""


class ChatService:
    """
    Servico de chat conversacional para analise de curriculos.
    Todas as configuracoes vem de settings.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.openai_api_key
        self.chat_model = settings.chat_model
        self._client: Optional[AsyncOpenAI] = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            if not self.api_key:
                raise ValueError("OpenAI API key nao configurada")
            kwargs = {"api_key": self.api_key}
            if settings.openai_base_url:
                kwargs["base_url"] = settings.openai_base_url
            if settings.openai_organization:
                kwargs["organization"] = settings.openai_organization
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    # ================================================================
    # Conversation Management
    # ================================================================

    def create_conversation(
        self,
        db: Session,
        user_id: int,
        title: str = "Nova Conversa",
        job_description: Optional[str] = None,
        job_title: Optional[str] = None,
        domain: str = "general",
    ) -> ChatConversation:
        """Cria uma nova conversa"""
        conversation = ChatConversation(
            user_id=user_id,
            title=title,
            job_description=job_description,
            job_title=job_title,
            domain=domain,
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        # Audit log
        audit = AuditLog(
            user_id=user_id,
            action="create_conversation",
            entity="chat_conversation",
            entity_id=conversation.id,
            metadata_json={"title": title, "domain": domain}
        )
        db.add(audit)
        db.commit()

        return conversation

    def get_conversations(
        self,
        db: Session,
        user_id: int,
        status: str = "active",
        limit: int = 50,
    ) -> List[ChatConversation]:
        """Lista conversas do usuario"""
        return db.query(ChatConversation).filter(
            ChatConversation.user_id == user_id,
            ChatConversation.status == status,
        ).order_by(desc(ChatConversation.updated_at)).limit(limit).all()

    def get_conversation(
        self, db: Session, conversation_id: int, user_id: int
    ) -> Optional[ChatConversation]:
        """Obtem uma conversa com verificacao de propriedade"""
        return db.query(ChatConversation).filter(
            ChatConversation.id == conversation_id,
            ChatConversation.user_id == user_id,
        ).first()

    def get_messages(
        self, db: Session, conversation_id: int, limit: int = 100
    ) -> List[ChatMessage]:
        """Obtem mensagens de uma conversa"""
        return db.query(ChatMessage).filter(
            ChatMessage.conversation_id == conversation_id
        ).order_by(ChatMessage.created_at).limit(limit).all()

    def archive_conversation(
        self, db: Session, conversation_id: int, user_id: int
    ) -> bool:
        """Arquiva uma conversa"""
        conv = self.get_conversation(db, conversation_id, user_id)
        if not conv:
            return False
        conv.status = "archived"
        db.commit()
        return True

    # ================================================================
    # Chat Processing
    # ================================================================

    async def send_message(
        self,
        db: Session,
        conversation_id: int,
        user_id: int,
        message: str,
        candidate_ids: Optional[List[int]] = None,
        company_id: Optional[int] = None,
    ) -> ChatResponse:
        """
        Envia mensagem no chat e obtem resposta do LLM

        Args:
            db: Sessao do banco
            conversation_id: ID da conversa
            user_id: ID do usuario
            message: Mensagem do usuario
            candidate_ids: IDs de candidatos especificos para focar
            company_id: ID da empresa para filtrar candidatos (multi-tenant)

        Returns:
            ChatResponse com resposta e metadados
        """
        # Validar conversa
        conversation = self.get_conversation(db, conversation_id, user_id)
        if not conversation:
            raise ValueError("Conversa nao encontrada ou sem permissao")

        # Salvar mensagem do usuario
        user_msg = ChatMessage(
            conversation_id=conversation_id,
            role="user",
            content=message,
        )
        db.add(user_msg)
        db.commit()
        db.refresh(user_msg)

        try:
            # Buscar chunks relevantes (filtrado por empresa)
            relevant_chunks = await self._search_relevant_chunks(
                db, message, candidate_ids, company_id
            )

            # Construir contexto de curriculos
            resume_context = self._build_resume_context(relevant_chunks)

            # Obter historico da conversa
            history = self._get_conversation_history(db, conversation_id)

            # Selecionar system prompt
            system_prompt = self._select_system_prompt(conversation)

            # Adicionar contexto da vaga se existir
            job_context = ""
            if conversation.job_description:
                job_context = f"\n\nVAGA EM ANALISE:\nTitulo: {conversation.job_title or 'N/A'}\nDescricao: {conversation.job_description}\n"

            # Construir mensagens para o LLM
            messages = [
                {"role": "system", "content": system_prompt + job_context},
            ]

            # Adicionar historico
            for hist_msg in history:
                messages.append({
                    "role": hist_msg.role,
                    "content": hist_msg.content
                })

            # Adicionar mensagem atual com contexto
            user_content = message
            if resume_context:
                user_content = f"CONTEXTO DOS CURRICULOS:\n{resume_context}\n\nPERGUNTA DO RECRUTADOR: {message}"

            messages.append({"role": "user", "content": user_content})

            # Chamar LLM
            response = await self.client.chat.completions.create(
                model=self.chat_model,
                messages=messages,
                temperature=settings.chat_temperature,
                max_tokens=settings.chat_max_tokens,
            )

            assistant_content = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if response.usage else 0

            # Extrair candidatos mencionados e fontes
            candidates_found = self._extract_candidates_from_chunks(relevant_chunks)
            sources = self._extract_sources(relevant_chunks)
            suggestions = self._generate_suggestions(message, conversation)

            # Salvar resposta do assistente
            assistant_msg = ChatMessage(
                conversation_id=conversation_id,
                role="assistant",
                content=assistant_content,
                tokens_used=tokens_used,
                metadata_json={
                    "candidates_found": [c["id"] for c in candidates_found],
                    "chunks_used": len(relevant_chunks),
                    "model": self.chat_model,
                    "confidence": self._calculate_confidence(relevant_chunks),
                }
            )
            db.add(assistant_msg)

            # Atualizar titulo da conversa se for a primeira mensagem
            msg_count = db.query(ChatMessage).filter(
                ChatMessage.conversation_id == conversation_id
            ).count()
            if msg_count <= 2:
                conversation.title = message[:80] + ("..." if len(message) > 80 else "")

            conversation.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(assistant_msg)

            return ChatResponse(
                message=assistant_content,
                conversation_id=conversation_id,
                message_id=assistant_msg.id,
                candidates_found=candidates_found,
                sources=sources,
                suggestions=suggestions,
                tokens_used=tokens_used,
                confidence=self._calculate_confidence(relevant_chunks),
            )

        except Exception as e:
            logger.error(f"Erro no chat: {e}", exc_info=True)

            # Salvar mensagem de erro
            error_msg = ChatMessage(
                conversation_id=conversation_id,
                role="assistant",
                content=f"Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente.",
                metadata_json={"error": str(e)}
            )
            db.add(error_msg)
            db.commit()
            db.refresh(error_msg)

            return ChatResponse(
                message=error_msg.content,
                conversation_id=conversation_id,
                message_id=error_msg.id,
                confidence=0.0,
            )

    async def analyze_job_opportunity(
        self,
        db: Session,
        conversation_id: int,
        user_id: int,
        job_description: str,
        job_title: str = "",
        limit: int = 10,
    ) -> ChatResponse:
        """
        Analisa uma oportunidade contra todos os curriculos da base

        Fluxo:
        1. Extrai requisitos da vaga
        2. Busca candidatos semanticamente similares
        3. Ranqueia por aderencia
        4. Retorna analise detalhada
        """
        conversation = self.get_conversation(db, conversation_id, user_id)
        if not conversation:
            raise ValueError("Conversa nao encontrada")

        # Atualizar conversa com dados da vaga
        conversation.job_description = job_description
        conversation.job_title = job_title
        db.commit()

        # Construir mensagem de analise
        analysis_message = (
            f"Analise a seguinte oportunidade e encontre os {limit} melhores candidatos "
            f"na base de curriculos:\n\n"
            f"TITULO DA VAGA: {job_title}\n\n"
            f"DESCRICAO DA VAGA:\n{job_description}\n\n"
            f"Por favor:\n"
            f"1. Identifique os requisitos obrigatorios e desejaveis\n"
            f"2. Ranqueie os candidatos por aderencia (0-100%)\n"
            f"3. Para cada candidato, liste pontos fortes e gaps\n"
            f"4. De uma recomendacao final\n"
            f"5. Sugira perguntas de entrevista focadas nos gaps"
        )

        return await self.send_message(
            db=db,
            conversation_id=conversation_id,
            user_id=user_id,
            message=analysis_message,
        )

    # ================================================================
    # Private Methods
    # ================================================================

    async def _search_relevant_chunks(
        self,
        db: Session,
        query: str,
        candidate_ids: Optional[List[int]] = None,
        company_id: Optional[int] = None,
    ) -> List[Tuple[Chunk, float]]:
        """Busca chunks relevantes para a query, filtrado por empresa"""
        try:
            query_embedding = await embedding_service.generate_embedding(query)
        except Exception as e:
            logger.warning(f"Falha ao gerar embedding: {e}")
            return []

        # Construir filtros
        extra_filters = ""
        params = {
            "query_vector": str(query_embedding),
            "threshold": settings.vector_search_pre_filter_threshold,
            "limit": settings.chat_max_chunks_per_query,
        }

        if candidate_ids:
            extra_filters += " AND c.candidate_id = ANY(:candidate_ids)"
            params["candidate_ids"] = candidate_ids

        # Filtrar por empresa (multi-tenant)
        if company_id:
            extra_filters += " AND cand.company_id = :company_id"
            params["company_id"] = company_id

        company_join = "JOIN candidates cand ON cand.id = c.candidate_id" if company_id else ""

        sql = sql_text(f"""
            SELECT
                c.id as chunk_id,
                c.candidate_id,
                c.section,
                c.content,
                1 - (e.vector <=> :query_vector::vector) as similarity
            FROM chunks c
            JOIN embeddings e ON e.chunk_id = c.id
            {company_join}
            WHERE 1 - (e.vector <=> :query_vector::vector) >= :threshold
            {extra_filters}
            ORDER BY e.vector <=> :query_vector::vector
            LIMIT :limit
        """)

        result = db.execute(sql, params)
        chunks_with_scores = []

        for row in result:
            chunk = db.query(Chunk).filter(Chunk.id == row.chunk_id).first()
            if chunk:
                chunks_with_scores.append((chunk, row.similarity))

        return chunks_with_scores

    def _build_resume_context(
        self, chunks: List[Tuple[Chunk, float]]
    ) -> str:
        """Constroi contexto de curriculos para o LLM"""
        if not chunks:
            return ""

        context_parts = []
        total_chars = 0
        seen_candidates = set()

        for chunk, score in chunks:
            if total_chars >= settings.chat_max_context_chars:
                break

            candidate_header = ""
            if chunk.candidate and chunk.candidate_id not in seen_candidates:
                c = chunk.candidate
                candidate_header = f"\n[CANDIDATO: {c.full_name or 'N/A'}"
                if c.email:
                    candidate_header += f" | {c.email}"
                if c.city:
                    candidate_header += f" | {c.city}"
                if c.state:
                    candidate_header += f"-{c.state}"
                candidate_header += f"]\n"
                seen_candidates.add(chunk.candidate_id)

            section_header = f"[Secao: {chunk.section} | Relevancia: {score:.0%}]"

            content = chunk.content
            remaining = settings.chat_max_context_chars - total_chars
            if len(content) > remaining:
                content = content[:remaining] + "..."

            block = f"{candidate_header}{section_header}\n{content}\n---"
            context_parts.append(block)
            total_chars += len(block)

        return "\n".join(context_parts)

    def _get_conversation_history(
        self, db: Session, conversation_id: int
    ) -> List[ChatMessage]:
        """Obtem historico recente da conversa"""
        messages = db.query(ChatMessage).filter(
            ChatMessage.conversation_id == conversation_id,
            ChatMessage.role.in_(["user", "assistant"]),
        ).order_by(desc(ChatMessage.created_at)).limit(
            settings.chat_max_context_messages
        ).all()

        # Reverter para ordem cronologica
        return list(reversed(messages))

    def _select_system_prompt(self, conversation: ChatConversation) -> str:
        """Seleciona prompt baseado no tipo de conversa"""
        if conversation.job_description:
            return SYSTEM_PROMPT_JOB_ANALYSIS
        return SYSTEM_PROMPT_CHAT

    def _extract_candidates_from_chunks(
        self, chunks: List[Tuple[Chunk, float]]
    ) -> List[Dict[str, Any]]:
        """Extrai lista de candidatos dos chunks"""
        candidates = {}
        for chunk, score in chunks:
            if chunk.candidate and chunk.candidate_id not in candidates:
                c = chunk.candidate
                candidates[chunk.candidate_id] = {
                    "id": c.id,
                    "name": c.full_name,
                    "email": c.email,
                    "city": c.city,
                    "state": c.state,
                    "relevance": round(score, 3),
                }

        return sorted(
            candidates.values(),
            key=lambda x: x["relevance"],
            reverse=True,
        )

    def _extract_sources(
        self, chunks: List[Tuple[Chunk, float]]
    ) -> List[Dict[str, Any]]:
        """Extrai fontes dos chunks"""
        return [
            {
                "chunk_id": chunk.id,
                "candidate_id": chunk.candidate_id,
                "candidate_name": chunk.candidate.full_name if chunk.candidate else "N/A",
                "section": chunk.section,
                "relevance": round(score, 3),
            }
            for chunk, score in chunks
        ]

    def _calculate_confidence(
        self, chunks: List[Tuple[Chunk, float]]
    ) -> float:
        """Calcula score de confianca"""
        if not chunks:
            return 0.0
        scores = [score for _, score in chunks]
        avg = sum(scores) / len(scores)
        coverage = min(len(chunks) / settings.confidence_coverage_divisor, 1.0)
        return round(avg * settings.confidence_score_weight + coverage * settings.confidence_coverage_weight, 3)

    def _generate_suggestions(
        self, message: str, conversation: ChatConversation
    ) -> List[str]:
        """Gera sugestoes de perguntas de follow-up"""
        suggestions = []

        msg_lower = message.lower()

        if conversation.job_description:
            if "ranking" not in msg_lower and "ranqu" not in msg_lower:
                suggestions.append("Faca um ranking dos 5 melhores candidatos para esta vaga")
            if "gap" not in msg_lower and "falta" not in msg_lower:
                suggestions.append("Quais gaps os candidatos tem para esta vaga?")
            if "entrevista" not in msg_lower:
                suggestions.append("Sugira perguntas de entrevista para os candidatos selecionados")
            if "compara" not in msg_lower:
                suggestions.append("Compare os 3 melhores candidatos lado a lado")
        else:
            if "experiencia" not in msg_lower:
                suggestions.append("Quais candidatos tem mais experiencia em producao?")
            if "certificac" not in msg_lower:
                suggestions.append("Quais candidatos possuem certificacoes NR relevantes?")
            if "dispon" not in msg_lower:
                suggestions.append("Quais candidatos estao disponiveis para turno noturno?")

        return suggestions[:3]


# Instancia global
chat_service = ChatService()
