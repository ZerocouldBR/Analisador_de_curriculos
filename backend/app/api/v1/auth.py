from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.auth import (
    UserCreate,
    UserLogin,
    UserResponse,
    Token,
    LoginResponse,
    PasswordChange,
    RoleCreate,
    RoleResponse,
    RoleUpdate
)
from app.services.auth_service import AuthService
from app.core.security import decode_access_token, decode_refresh_token, create_access_token, create_refresh_token
from app.core.dependencies import (
    get_current_user,
    get_current_superuser,
    require_permission
)
from app.db.models import User, Role


class RefreshTokenRequest(BaseModel):
    refresh_token: str


router = APIRouter(prefix="/auth", tags=["authentication"])


def _build_user_response(user: User) -> UserResponse:
    """Constroi UserResponse incluindo dados da empresa"""
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        status=user.status,
        is_superuser=user.is_superuser,
        company_id=user.company_id,
        company_name=user.company.name if user.company else None,
        roles=[role.name for role in user.roles],
        created_at=user.created_at,
        last_login=user.last_login,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_data: UserCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Registra um novo usuario (e opcionalmente uma empresa de RH)

    **Campos obrigatorios:**
    - **email**: Email unico do usuario
    - **name**: Nome completo
    - **password**: Senha (minimo 8 caracteres, maiuscula, minuscula, numero e especial)

    **Campos opcionais para empresa:**
    - **company_name**: Nome da empresa de RH (cria nova empresa e vincula)
    - **company_cnpj**: CNPJ da empresa
    - **company_phone**: Telefone da empresa
    - **company_id**: ID de empresa existente para vincular

    Se `company_name` for informado, o usuario recebe role 'admin' da empresa.
    Caso contrario, recebe role 'viewer' por padrao.
    """
    from app.core.rate_limit import check_rate_limit
    check_rate_limit(request, key_prefix="register", max_requests=5, window_seconds=300)

    try:
        user = AuthService.create_user(db, user_data)

        return _build_user_response(user)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", response_model=LoginResponse)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Faz login e retorna tokens de acesso + dados do usuario

    Aceita form data (OAuth2) com campos:
    - **username**: Email do usuario
    - **password**: Senha

    Retorna:
    - **access_token**: Token JWT de acesso (valido por 15 minutos)
    - **refresh_token**: Token de refresh (valido por 7 dias)
    - **user**: Dados do usuario autenticado
    """
    from app.core.rate_limit import check_rate_limit
    check_rate_limit(request, key_prefix="login", max_requests=10, window_seconds=60)

    try:
        credentials = UserLogin(email=form_data.username, password=form_data.password)
        user = AuthService.authenticate_user(db, credentials)

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email ou senha incorretos",
                headers={"WWW-Authenticate": "Bearer"},
            )

        tokens = AuthService.create_tokens(user)

        return LoginResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_type=tokens["token_type"],
            user=_build_user_response(user),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Obtém informações do usuário autenticado

    Requer autenticação via Bearer token.
    """
    return _build_user_response(current_user)


@router.post("/change-password")
def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Altera a senha do usuário autenticado

    - **old_password**: Senha atual
    - **new_password**: Nova senha (mínimo 8 caracteres)
    """
    try:
        AuthService.update_password(
            db,
            current_user,
            password_data.old_password,
            password_data.new_password
        )

        return {"message": "Senha alterada com sucesso"}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/refresh", response_model=LoginResponse)
def refresh_token(
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Renova o access token usando um refresh token valido

    - **refresh_token**: Token de refresh obtido no login

    Retorna novos tokens e dados do usuario.
    """
    token_data = decode_refresh_token(payload.refresh_token)

    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = AuthService.get_user_by_id(db, token_data.user_id)

    if user is None or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario nao encontrado ou inativo",
        )

    tokens = AuthService.create_tokens(user)

    return LoginResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"],
        user=_build_user_response(user),
    )


# Endpoints de gerenciamento de roles (apenas superuser)

@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(
    role_data: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    Cria um novo role (apenas superuser)

    - **name**: Nome único do role
    - **description**: Descrição do role
    - **permissions**: Dict com permissões {permission: true/false}
    """
    # Verificar se role já existe
    existing_role = db.query(Role).filter(Role.name == role_data.name).first()
    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role já existe"
        )

    role = Role(
        name=role_data.name,
        description=role_data.description,
        permissions=role_data.permissions
    )

    db.add(role)
    db.commit()
    db.refresh(role)

    return role


@router.get("/roles", response_model=list[RoleResponse])
def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lista todos os roles disponíveis

    Requer autenticação.
    """
    roles = db.query(Role).all()
    return roles


@router.put("/roles/{role_id}", response_model=RoleResponse)
def update_role(
    role_id: int,
    role_update: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    Atualiza um role (apenas superuser)
    """
    role = db.query(Role).filter(Role.id == role_id).first()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role não encontrado"
        )

    update_data = role_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(role, field, value)

    db.commit()
    db.refresh(role)

    return role


@router.post("/users/{user_id}/roles/{role_name}")
def assign_role_to_user(
    user_id: int,
    role_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    Atribui um role a um usuário (apenas superuser)
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )

    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role não encontrado"
        )

    # Verificar se já possui o role
    if role in user.roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário já possui este role"
        )

    user.roles.append(role)
    db.commit()

    return {"message": f"Role '{role_name}' atribuído ao usuário {user.email}"}


@router.delete("/users/{user_id}/roles/{role_name}")
def remove_role_from_user(
    user_id: int,
    role_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    Remove um role de um usuário (apenas superuser)
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )

    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role não encontrado"
        )

    # Verificar se possui o role
    if role not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário não possui este role"
        )

    user.roles.remove(role)
    db.commit()

    return {"message": f"Role '{role_name}' removido do usuário {user.email}"}
