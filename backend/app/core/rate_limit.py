"""
Rate limiter simples para endpoints criticos (login, registro, refresh)

Usa Redis se disponivel, fallback para dict em memoria.
Protege contra brute force e credential stuffing.
"""
import logging
import time
from typing import Optional
from fastapi import HTTPException, Request, status

from app.core.config import settings

logger = logging.getLogger(__name__)

# Cache em memoria (fallback se Redis indisponivel)
_memory_store: dict[str, list[float]] = {}


def _get_client_ip(request: Request) -> str:
    """Extrai IP do cliente (respeita X-Forwarded-For)"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _cleanup_old_entries(key: str, window: int):
    """Remove entradas expiradas do cache em memoria"""
    now = time.time()
    if key in _memory_store:
        _memory_store[key] = [t for t in _memory_store[key] if now - t < window]


def check_rate_limit(
    request: Request,
    key_prefix: str = "auth",
    max_requests: int = 10,
    window_seconds: int = 60,
):
    """
    Verifica rate limit para o request atual

    Args:
        request: Request FastAPI
        key_prefix: Prefixo da chave (ex: 'login', 'register')
        max_requests: Maximo de requests na janela
        window_seconds: Tamanho da janela em segundos

    Raises:
        HTTPException 429 se limite excedido
    """
    client_ip = _get_client_ip(request)
    key = f"rate:{key_prefix}:{client_ip}"

    try:
        import redis
        r = redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=1)

        # Incrementar contador com TTL
        current = r.incr(key)
        if current == 1:
            r.expire(key, window_seconds)

        ttl = r.ttl(key)
        r.close()

        if current > max_requests:
            logger.warning(
                f"Rate limit excedido: {key_prefix} ip={client_ip} "
                f"({current}/{max_requests} em {window_seconds}s)"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Muitas tentativas. Aguarde {ttl} segundos.",
                headers={"Retry-After": str(ttl)},
            )

    except (ImportError, Exception) as e:
        if isinstance(e, HTTPException):
            raise

        # Fallback: rate limit em memoria
        now = time.time()
        _cleanup_old_entries(key, window_seconds)

        if key not in _memory_store:
            _memory_store[key] = []

        if len(_memory_store[key]) >= max_requests:
            oldest = _memory_store[key][0]
            wait = int(window_seconds - (now - oldest)) + 1
            logger.warning(f"Rate limit (memory) excedido: {key_prefix} ip={client_ip}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Muitas tentativas. Aguarde {max(wait, 1)} segundos.",
                headers={"Retry-After": str(max(wait, 1))},
            )

        _memory_store[key].append(now)
