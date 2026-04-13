"""
API de Chat para analise de curriculos

Endpoints:
- Criar/listar/arquivar conversas
- Enviar mensagens e receber analises
- Analisar oportunidades contra base de curriculos
- Obter historico de mensagens
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from app.db.database import get_db
from app.db.models import User, ChatConversation, ChatMessage
from app.core.config import settings
from app.core.dependencies import get_current_user, require_permission
from app.services.chat_service import chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


# ================================================================
# Schemas
# ================================================================

class ConversationCreate(BaseModel):
    title: str = Field(default="Nova Conversa", max_length=200)
    job_description: Optional[str] = Field(None, description="Descricao da vaga (opcional)")
    job_title: Optional[str] = Field(None, max_length=200)
    domain: str = Field(default="general", description="production, logistics, quality, general")


class ConversationResponse(BaseModel):
    id: int
    title: str
    job_title: Optional[str]
    domain: str
    status: str
    created_at: str
    updated_at: str
    message_count: int = 0

    class Config:
        from_attributes = True


class MessageSend(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000, description="Mensagem do usuario")
    candidate_ids: Optional[List[int]] = Field(None, description="IDs de candidatos para focar")


class JobAnalysisRequest(BaseModel):
    job_description: str = Field(..., min_length=10, description="Descricao completa da vaga")
    job_title: str = Field(default="", max_length=200, description="Titulo da vaga")
    limit: int = Field(default=10, ge=1, le=50, description="Numero maximo de candidatos")


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    tokens_used: int
    created_at: str
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class ChatResponseModel(BaseModel):
    message: str
    conversation_id: int
    message_id: int
    candidates_found: List[Dict[str, Any]] = []
    sources: List[Dict[str, Any]] = []
    suggestions: List[str] = []
    tokens_used: int = 0
    confidence: float = 0.0


# ================================================================
# Conversation Endpoints
# ================================================================

@router.post("/conversations", response_model=ConversationResponse)
def create_conversation(
    data: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cria uma nova conversa de chat

    Pode opcionalmente incluir uma descricao de vaga para analise direcionada.
    """
    conversation = chat_service.create_conversation(
        db=db,
        user_id=current_user.id,
        title=data.title,
        job_description=data.job_description,
        job_title=data.job_title,
        domain=data.domain,
    )

    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        job_title=conversation.job_title,
        domain=conversation.domain,
        status=conversation.status,
        created_at=conversation.created_at.isoformat(),
        updated_at=conversation.updated_at.isoformat(),
        message_count=0,
    )


@router.get("/conversations", response_model=List[ConversationResponse])
def list_conversations(
    status_filter: str = "active",
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista conversas do usuario atual"""
    conversations = chat_service.get_conversations(
        db, current_user.id, status_filter, limit
    )

    results = []
    for conv in conversations:
        msg_count = db.query(ChatMessage).filter(
            ChatMessage.conversation_id == conv.id
        ).count()

        results.append(ConversationResponse(
            id=conv.id,
            title=conv.title,
            job_title=conv.job_title,
            domain=conv.domain,
            status=conv.status,
            created_at=conv.created_at.isoformat(),
            updated_at=conv.updated_at.isoformat(),
            message_count=msg_count,
        ))

    return results


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Obtem detalhes de uma conversa"""
    conv = chat_service.get_conversation(db, conversation_id, current_user.id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversa nao encontrada"
        )

    msg_count = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conv.id
    ).count()

    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        job_title=conv.job_title,
        domain=conv.domain,
        status=conv.status,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
        message_count=msg_count,
    )


@router.delete("/conversations/{conversation_id}")
def archive_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Arquiva uma conversa"""
    success = chat_service.archive_conversation(
        db, conversation_id, current_user.id
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversa nao encontrada"
        )
    return {"status": "archived", "conversation_id": conversation_id}


# ================================================================
# Message Endpoints
# ================================================================

@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
def get_messages(
    conversation_id: int,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Obtem mensagens de uma conversa"""
    conv = chat_service.get_conversation(db, conversation_id, current_user.id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversa nao encontrada"
        )

    messages = chat_service.get_messages(db, conversation_id, limit)

    return [
        MessageResponse(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            tokens_used=msg.tokens_used or 0,
            created_at=msg.created_at.isoformat(),
            metadata=msg.metadata_json,
        )
        for msg in messages
    ]


@router.post("/conversations/{conversation_id}/messages", response_model=ChatResponseModel)
async def send_message(
    conversation_id: int,
    data: MessageSend,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Envia uma mensagem e recebe resposta do assistente

    O assistente busca automaticamente curriculos relevantes na base vetorial
    e responde baseado nos dados encontrados.

    Opcionalmente, passe `candidate_ids` para focar em candidatos especificos.
    """
    conv = chat_service.get_conversation(db, conversation_id, current_user.id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversa nao encontrada"
        )

    try:
        # Multi-tenant: filtrar candidatos por empresa
        company_id = current_user.company_id if settings.multi_tenant_enabled and not current_user.is_superuser else None

        response = await chat_service.send_message(
            db=db,
            conversation_id=conversation_id,
            user_id=current_user.id,
            message=data.message,
            candidate_ids=data.candidate_ids,
            company_id=company_id,
        )

        return ChatResponseModel(
            message=response.message,
            conversation_id=response.conversation_id,
            message_id=response.message_id,
            candidates_found=response.candidates_found,
            sources=response.sources,
            suggestions=response.suggestions,
            tokens_used=response.tokens_used,
            confidence=response.confidence,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar mensagem: {str(e)}"
        )


# ================================================================
# Job Analysis Endpoint
# ================================================================

@router.post("/conversations/{conversation_id}/analyze-job", response_model=ChatResponseModel)
async def analyze_job_opportunity(
    conversation_id: int,
    data: JobAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("search.advanced")),
):
    """
    Analisa uma oportunidade de emprego contra a base de curriculos

    Busca e ranqueia os melhores candidatos para a vaga descrita,
    com analise detalhada de aderencia, pontos fortes e gaps.

    **Requer permissao:** search.advanced
    """
    conv = chat_service.get_conversation(db, conversation_id, current_user.id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversa nao encontrada"
        )

    try:
        response = await chat_service.analyze_job_opportunity(
            db=db,
            conversation_id=conversation_id,
            user_id=current_user.id,
            job_description=data.job_description,
            job_title=data.job_title,
            limit=data.limit,
        )

        return ChatResponseModel(
            message=response.message,
            conversation_id=response.conversation_id,
            message_id=response.message_id,
            candidates_found=response.candidates_found,
            sources=response.sources,
            suggestions=response.suggestions,
            tokens_used=response.tokens_used,
            confidence=response.confidence,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na analise: {str(e)}"
        )


# ================================================================
# Quick Analysis (without conversation)
# ================================================================

@router.post("/quick-analyze", response_model=ChatResponseModel)
async def quick_analyze(
    data: JobAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("search.advanced")),
):
    """
    Analise rapida de vaga sem criar conversa persistente

    Cria uma conversa temporaria, faz a analise e retorna o resultado.
    A conversa fica disponivel para follow-up.

    **Requer permissao:** search.advanced
    """
    try:
        # Criar conversa automaticamente
        conversation = chat_service.create_conversation(
            db=db,
            user_id=current_user.id,
            title=f"Analise: {data.job_title or 'Vaga'}",
            job_description=data.job_description,
            job_title=data.job_title,
        )

        response = await chat_service.analyze_job_opportunity(
            db=db,
            conversation_id=conversation.id,
            user_id=current_user.id,
            job_description=data.job_description,
            job_title=data.job_title,
            limit=data.limit,
        )

        return ChatResponseModel(
            message=response.message,
            conversation_id=response.conversation_id,
            message_id=response.message_id,
            candidates_found=response.candidates_found,
            sources=response.sources,
            suggestions=response.suggestions,
            tokens_used=response.tokens_used,
            confidence=response.confidence,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na analise rapida: {str(e)}"
        )
