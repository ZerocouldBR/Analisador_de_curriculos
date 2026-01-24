from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional

from app.db.database import get_db
from app.db.models import User
from app.core.security import decode_access_token
from app.services.auth_service import AuthService


security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency para obter o usuário autenticado atual

    Raises:
        HTTPException: Se token inválido ou usuário não encontrado
    """
    token = credentials.credentials

    # Decodificar token
    token_data = decode_access_token(token)

    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Buscar usuário
    user = AuthService.get_user_by_id(db, token_data.user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo ou suspenso"
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency para garantir que o usuário está ativo

    Raises:
        HTTPException: Se usuário inativo
    """
    if current_user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo"
        )
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency para garantir que o usuário é superuser

    Raises:
        HTTPException: Se não for superuser
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: privilégios de superuser necessários"
        )
    return current_user


def require_permission(permission: str):
    """
    Dependency factory para verificar permissões específicas

    Args:
        permission: Nome da permissão (ex: "candidates.delete")

    Returns:
        Dependency function
    """
    async def permission_checker(
        current_user: User = Depends(get_current_user)
    ) -> User:
        if not AuthService.has_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissão negada: {permission}"
            )
        return current_user

    return permission_checker


def require_role(role_name: str):
    """
    Dependency factory para verificar roles específicos

    Args:
        role_name: Nome do role (ex: "admin", "recruiter")

    Returns:
        Dependency function
    """
    async def role_checker(
        current_user: User = Depends(get_current_user)
    ) -> User:
        if not (current_user.is_superuser or AuthService.has_role(current_user, role_name)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado: role '{role_name}' necessário"
            )
        return current_user

    return role_checker


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Dependency para obter usuário se autenticado, None caso contrário

    Útil para endpoints que podem ser acessados com ou sem autenticação
    """
    if credentials is None:
        return None

    token = credentials.credentials
    token_data = decode_access_token(token)

    if token_data is None:
        return None

    user = AuthService.get_user_by_id(db, token_data.user_id)

    if user and user.status == "active":
        return user

    return None
