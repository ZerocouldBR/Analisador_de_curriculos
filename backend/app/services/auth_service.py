from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.db.models import User, Role, AuditLog
from app.schemas.auth import UserCreate, UserLogin
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token
)


class AuthService:
    @staticmethod
    def create_user(db: Session, user_data: UserCreate, role_names: list[str] = None) -> User:
        """
        Cria um novo usuário

        Args:
            db: Sessão do banco de dados
            user_data: Dados do usuário
            role_names: Lista de nomes de roles para atribuir ao usuário

        Returns:
            Usuário criado
        """
        # Verificar se email já existe
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise ValueError("Email já cadastrado")

        # Criar usuário
        db_user = User(
            email=user_data.email,
            name=user_data.name,
            password_hash=get_password_hash(user_data.password),
            status="active"
        )

        db.add(db_user)
        db.flush()

        # Atribuir roles
        if role_names:
            for role_name in role_names:
                role = db.query(Role).filter(Role.name == role_name).first()
                if role:
                    db_user.roles.append(role)
        else:
            # Role padrão: viewer
            default_role = db.query(Role).filter(Role.name == "viewer").first()
            if default_role:
                db_user.roles.append(default_role)

        db.commit()
        db.refresh(db_user)

        # Audit log
        audit = AuditLog(
            user_id=None,
            action="create_user",
            entity="user",
            entity_id=db_user.id,
            metadata_json={"email": user_data.email, "name": user_data.name}
        )
        db.add(audit)
        db.commit()

        return db_user

    @staticmethod
    def authenticate_user(db: Session, credentials: UserLogin) -> Optional[User]:
        """
        Autentica um usuário

        Args:
            db: Sessão do banco de dados
            credentials: Credenciais de login

        Returns:
            Usuário autenticado ou None se credenciais inválidas
        """
        user = db.query(User).filter(User.email == credentials.email).first()

        if not user:
            return None

        if not verify_password(credentials.password, user.password_hash):
            return None

        if user.status != "active":
            raise ValueError("Usuário inativo ou suspenso")

        # Atualizar último login
        user.last_login = datetime.utcnow()
        db.commit()

        # Audit log
        audit = AuditLog(
            user_id=user.id,
            action="login",
            entity="user",
            entity_id=user.id,
            metadata_json={"email": user.email}
        )
        db.add(audit)
        db.commit()

        return user

    @staticmethod
    def create_tokens(user: User) -> dict:
        """
        Cria tokens de acesso e refresh para um usuário

        Args:
            user: Usuário autenticado

        Returns:
            Dict com access_token e refresh_token
        """
        role_names = [role.name for role in user.roles]

        token_data = {
            "user_id": user.id,
            "email": user.email,
            "roles": role_names,
            "is_superuser": user.is_superuser
        }

        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        """Obtém um usuário por ID"""
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        """Obtém um usuário por email"""
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def update_password(
        db: Session,
        user: User,
        old_password: str,
        new_password: str
    ) -> bool:
        """
        Atualiza a senha de um usuário

        Args:
            db: Sessão do banco de dados
            user: Usuário
            old_password: Senha antiga
            new_password: Senha nova

        Returns:
            True se senha atualizada com sucesso
        """
        # Verificar senha antiga
        if not verify_password(old_password, user.password_hash):
            raise ValueError("Senha antiga incorreta")

        # Atualizar senha
        user.password_hash = get_password_hash(new_password)
        db.commit()

        # Audit log
        audit = AuditLog(
            user_id=user.id,
            action="password_change",
            entity="user",
            entity_id=user.id,
            metadata_json={"email": user.email}
        )
        db.add(audit)
        db.commit()

        return True

    @staticmethod
    def has_permission(user: User, permission: str) -> bool:
        """
        Verifica se um usuário tem uma permissão específica

        Args:
            user: Usuário
            permission: Nome da permissão (ex: "candidates.delete")

        Returns:
            True se tem permissão
        """
        # Superuser tem todas as permissões
        if user.is_superuser:
            return True

        # Verificar permissões nos roles
        for role in user.roles:
            if role.permissions.get(permission, False):
                return True

        return False

    @staticmethod
    def has_role(user: User, role_name: str) -> bool:
        """
        Verifica se um usuário tem um role específico

        Args:
            user: Usuário
            role_name: Nome do role

        Returns:
            True se tem o role
        """
        return any(role.name == role_name for role in user.roles)
