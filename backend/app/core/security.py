from datetime import datetime, timedelta
from typing import Optional, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.core.config import settings


# Configuração de hash de senha
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Configurações JWT
SECRET_KEY = getattr(settings, 'secret_key', "your-secret-key-change-this-in-production")
ALGORITHM = getattr(settings, 'algorithm', "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = getattr(settings, 'access_token_expire_minutes', 30)


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

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "iat": datetime.utcnow()})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[TokenData]:
    """
    Decodifica e valida um token JWT

    Args:
        token: Token JWT a ser decodificado

    Returns:
        TokenData se válido, None caso contrário
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

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
    Cria um token de refresh (válido por 7 dias)

    Args:
        data: Dados a serem codificados no token

    Returns:
        Token JWT de refresh
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=7)
    to_encode.update({"exp": expire, "iat": datetime.utcnow(), "type": "refresh"})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
