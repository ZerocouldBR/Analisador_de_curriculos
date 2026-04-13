from datetime import datetime, timedelta, timezone
from typing import Optional, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.core.config import settings


# Configuração de hash de senha
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenData(BaseModel):
    """Dados armazenados no token JWT"""
    user_id: int
    email: str
    roles: list[str] = []


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha está correta"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Gera hash da senha"""
    return pwd_context.hash(password)


def _utcnow() -> datetime:
    """Returns current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


def create_access_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Cria um token JWT de acesso

    Args:
        data: Dados a serem codificados no token
        expires_delta: Tempo de expiração customizado

    Returns:
        Token JWT codificado
    """
    to_encode = data.copy()
    now = _utcnow()

    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode.update({"exp": expire, "iat": now, "type": "access"})

    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[TokenData]:
    """
    Decodifica e valida um token JWT de acesso

    Args:
        token: Token JWT a ser decodificado

    Returns:
        TokenData se válido, None caso contrário
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])

        # Rejeitar refresh tokens usados como access tokens
        token_type = payload.get("type", "access")
        if token_type != "access":
            return None

        user_id: int = payload.get("user_id")
        email: str = payload.get("email")
        roles: list[str] = payload.get("roles", [])

        if user_id is None or email is None:
            return None

        return TokenData(user_id=user_id, email=email, roles=roles)

    except JWTError:
        return None


def decode_refresh_token(token: str) -> Optional[TokenData]:
    """
    Decodifica e valida um token JWT de refresh

    Args:
        token: Token JWT de refresh

    Returns:
        TokenData se valido, None caso contrario
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])

        # Deve ser um refresh token
        token_type = payload.get("type")
        if token_type != "refresh":
            return None

        user_id: int = payload.get("user_id")
        email: str = payload.get("email")
        roles: list[str] = payload.get("roles", [])

        if user_id is None or email is None:
            return None

        return TokenData(user_id=user_id, email=email, roles=roles)

    except JWTError:
        return None


def create_refresh_token(data: dict[str, Any]) -> str:
    """
    Cria um token de refresh

    Args:
        data: Dados a serem codificados no token

    Returns:
        Token JWT de refresh
    """
    to_encode = data.copy()
    now = _utcnow()
    expire = now + timedelta(days=settings.refresh_token_expire_days)
    to_encode.update({"exp": expire, "iat": now, "type": "refresh"})

    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt
