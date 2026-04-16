"""
Cliente LLM centralizado - abstrai OpenAI e Anthropic

Todos os servicos que precisam chamar um LLM devem usar este modulo
em vez de criar clientes diretamente.

Uso:
    from app.services.llm_client import llm_client

    response = await llm_client.chat_completion(
        messages=[{"role": "user", "content": "Ola"}],
        temperature=0.7,
        max_tokens=4096,
    )
    print(response.content)
    print(response.tokens_used)
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.config import settings, LLMProvider

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Resposta padronizada de qualquer provedor LLM"""
    content: str
    finish_reason: str
    tokens_used: int
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    raw: Any = None


class LLMClient:
    """
    Cliente LLM centralizado que abstrai OpenAI e Anthropic.

    Cria e gerencia os clientes de cada provedor conforme necessario.
    Todas as configuracoes vem de settings.
    """

    def __init__(self):
        self._openai_client = None
        self._anthropic_client = None

    def reset(self):
        """Reseta clientes (util apos mudanca de config)"""
        self._openai_client = None
        self._anthropic_client = None

    @property
    def provider(self) -> LLMProvider:
        return settings.llm_provider

    @property
    def model(self) -> str:
        return settings.chat_model

    # ================================================================
    # OpenAI Client
    # ================================================================

    @property
    def openai_client(self):
        """Lazy-load do cliente OpenAI (AsyncOpenAI)"""
        if self._openai_client is None:
            from openai import AsyncOpenAI

            if not settings.openai_api_key:
                raise ValueError(
                    "OpenAI API key nao configurada. "
                    "Defina OPENAI_API_KEY no .env ou nas configuracoes do sistema."
                )
            kwargs: Dict[str, Any] = {"api_key": settings.openai_api_key}
            if settings.openai_base_url:
                kwargs["base_url"] = settings.openai_base_url
            if settings.openai_organization:
                kwargs["organization"] = settings.openai_organization
            self._openai_client = AsyncOpenAI(**kwargs)
        return self._openai_client

    # ================================================================
    # Anthropic Client
    # ================================================================

    @property
    def anthropic_client(self):
        """Lazy-load do cliente Anthropic (AsyncAnthropic)"""
        if self._anthropic_client is None:
            try:
                from anthropic import AsyncAnthropic
            except ImportError:
                raise ImportError(
                    "Pacote 'anthropic' nao instalado. "
                    "Execute: pip install anthropic"
                )

            if not settings.anthropic_api_key:
                raise ValueError(
                    "Anthropic API key nao configurada. "
                    "Defina ANTHROPIC_API_KEY no .env ou nas configuracoes do sistema."
                )
            kwargs: Dict[str, Any] = {"api_key": settings.anthropic_api_key}
            if settings.anthropic_base_url:
                kwargs["base_url"] = settings.anthropic_base_url
            self._anthropic_client = AsyncAnthropic(**kwargs)
        return self._anthropic_client

    # ================================================================
    # Unified Chat Completion
    # ================================================================

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        provider: Optional[LLMProvider] = None,
    ) -> LLMResponse:
        """
        Executa chat completion usando o provedor configurado.

        Args:
            messages: Lista de mensagens no formato OpenAI
                      [{"role": "system"|"user"|"assistant", "content": "..."}]
            model: Modelo a usar (padrao: settings.chat_model)
            temperature: Temperatura (padrao: settings.llm_temperature)
            max_tokens: Max tokens (padrao: settings.llm_max_tokens)
            provider: Forcar provedor especifico (padrao: settings.llm_provider)

        Returns:
            LLMResponse com conteudo, tokens e metadados
        """
        _provider = provider or self.provider
        _model = model or self.model
        _temperature = temperature if temperature is not None else settings.llm_temperature
        _max_tokens = max_tokens or settings.llm_max_tokens

        if _provider == LLMProvider.ANTHROPIC:
            return await self._call_anthropic(messages, _model, _temperature, _max_tokens)
        else:
            return await self._call_openai(messages, _model, _temperature, _max_tokens)

    async def _call_openai(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        """Chama OpenAI Chat Completions API"""
        response = await self.openai_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        choice = response.choices[0]
        usage = response.usage

        return LLMResponse(
            content=choice.message.content or "",
            finish_reason=choice.finish_reason or "stop",
            tokens_used=usage.total_tokens if usage else 0,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            model=response.model,
            raw=response,
        )

    async def _call_anthropic(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        """Chama Anthropic Messages API"""
        # Separar system message das demais (Anthropic usa parametro separado)
        system_content = None
        user_messages = []

        for msg in messages:
            if msg["role"] == "system":
                # Anthropic aceita apenas um system prompt; concatenar se houver multiplos
                if system_content is None:
                    system_content = msg["content"]
                else:
                    system_content += "\n\n" + msg["content"]
            else:
                user_messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })

        # Garantir que ha pelo menos uma mensagem de usuario
        if not user_messages:
            user_messages = [{"role": "user", "content": ""}]

        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": user_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_content:
            kwargs["system"] = system_content

        response = await self.anthropic_client.messages.create(**kwargs)

        content = ""
        if response.content:
            content = response.content[0].text

        return LLMResponse(
            content=content,
            finish_reason=response.stop_reason or "end_turn",
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=response.model,
            raw=response,
        )

    # ================================================================
    # Helpers para embeddings (sempre OpenAI)
    # ================================================================

    async def generate_embedding(
        self,
        text: str,
        model: Optional[str] = None,
        dimensions: Optional[int] = None,
    ) -> List[float]:
        """
        Gera embedding via OpenAI API.
        Embeddings sempre usam OpenAI (Anthropic nao tem API de embeddings).
        """
        _model = model or settings.embedding_model
        kwargs: Dict[str, Any] = {
            "model": _model,
            "input": text,
        }
        if dimensions:
            kwargs["dimensions"] = dimensions

        response = await self.openai_client.embeddings.create(**kwargs)
        return response.data[0].embedding

    # ================================================================
    # Test de conexao
    # ================================================================

    async def test_connection(self, provider: Optional[LLMProvider] = None) -> Dict[str, Any]:
        """Testa conexao com o provedor LLM"""
        _provider = provider or self.provider

        try:
            if _provider == LLMProvider.ANTHROPIC:
                response = await self.chat_completion(
                    messages=[{"role": "user", "content": "Responda apenas: OK"}],
                    model=settings.chat_model,
                    temperature=0,
                    max_tokens=10,
                    provider=_provider,
                )
            else:
                response = await self.chat_completion(
                    messages=[{"role": "user", "content": "Responda apenas: OK"}],
                    model=settings.chat_model,
                    temperature=0,
                    max_tokens=10,
                    provider=_provider,
                )

            return {
                "status": "ok",
                "provider": _provider.value,
                "model": response.model,
                "tokens_used": response.tokens_used,
            }
        except Exception as e:
            return {
                "status": "error",
                "provider": _provider.value,
                "error": str(e),
            }


# Singleton global
llm_client = LLMClient()
