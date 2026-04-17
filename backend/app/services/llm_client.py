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
        cache_system_prompt: bool = False,
        thinking_budget: Optional[int] = None,
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
            cache_system_prompt: Habilita prompt caching (Anthropic) do system prompt.
                Reduz custo/latencia quando o mesmo system prompt e reutilizado
                em multiplas chamadas dentro de ~5 minutos. No-op para OpenAI.
            thinking_budget: Se fornecido, habilita extended thinking do Claude
                com esse budget de tokens (ex: 5000). No-op para OpenAI.

        Returns:
            LLMResponse com conteudo, tokens e metadados
        """
        _provider = provider or self.provider
        _model = model or self.model
        _temperature = temperature if temperature is not None else settings.llm_temperature
        _max_tokens = max_tokens if max_tokens is not None else settings.llm_max_tokens

        if _provider == LLMProvider.ANTHROPIC:
            return await self._call_anthropic(
                messages, _model, _temperature, _max_tokens,
                cache_system_prompt=cache_system_prompt,
                thinking_budget=thinking_budget,
            )
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
        cache_system_prompt: bool = False,
        thinking_budget: Optional[int] = None,
    ) -> LLMResponse:
        """Chama Anthropic Messages API com suporte opcional a prompt caching
        e extended thinking."""
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

        # Anthropic exige que a primeira mensagem seja 'user' e que as mensagens
        # alternem entre 'user' e 'assistant'. Consolidar mensagens consecutivas
        # do mesmo role e garantir que comeca com 'user'.
        if user_messages and user_messages[0]["role"] != "user":
            user_messages.insert(0, {"role": "user", "content": "..."})

        consolidated = []
        for msg in user_messages:
            if consolidated and consolidated[-1]["role"] == msg["role"]:
                consolidated[-1]["content"] += "\n\n" + msg["content"]
            else:
                consolidated.append(dict(msg))
        user_messages = consolidated

        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": user_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_content:
            # Prompt caching: a API da Anthropic aceita "system" como lista de
            # blocos quando um deles precisa ser marcado para cache.
            # Reutilizar o system prompt em chamadas subsequentes (ate ~5 min)
            # economiza ate ~90% do custo de input tokens no bloco cacheado.
            if cache_system_prompt and len(system_content) >= 1024:
                kwargs["system"] = [
                    {
                        "type": "text",
                        "text": system_content,
                        "cache_control": {"type": "ephemeral"},
                    }
                ]
            else:
                kwargs["system"] = system_content

        # Extended thinking (Claude): quando habilitado, temperatura deve ser 1.0
        if thinking_budget and thinking_budget > 0:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}
            kwargs["temperature"] = 1.0  # requisito da API
            # max_tokens precisa ser > thinking_budget
            if max_tokens <= thinking_budget:
                kwargs["max_tokens"] = thinking_budget + 1024

        response = await self.anthropic_client.messages.create(**kwargs)

        # Extrair o texto da resposta, pulando blocos "thinking" quando presentes
        content = ""
        if response.content:
            for block in response.content:
                block_type = getattr(block, "type", None)
                if block_type == "text":
                    content = block.text
                    break

        # Normalizar stop_reason para formato compativel com OpenAI
        raw_reason = response.stop_reason or "end_turn"
        finish_reason_map = {
            "end_turn": "stop",
            "max_tokens": "length",
            "stop_sequence": "stop",
        }
        finish_reason = finish_reason_map.get(raw_reason, raw_reason)

        # Contabilizar tokens cacheados quando o caching esta ativo.
        # A API Anthropic expoe cache_creation_input_tokens e
        # cache_read_input_tokens alem de input_tokens regulares.
        usage = response.usage
        cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        total_input = (usage.input_tokens or 0) + cache_creation + cache_read

        return LLMResponse(
            content=content,
            finish_reason=finish_reason,
            tokens_used=total_input + usage.output_tokens,
            input_tokens=total_input,
            output_tokens=usage.output_tokens,
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
            response = await self.chat_completion(
                messages=[{"role": "user", "content": "Responda apenas: OK"}],
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
