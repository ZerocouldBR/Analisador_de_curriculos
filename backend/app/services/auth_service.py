import re
import uuid
import logging

from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timezone

from app.db.models import User, Role, Company, AuditLog
from app.schemas.auth import UserCreate, UserLogin
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token
)

logger = logging.getLogger(__name__)


class AuthService:
    @staticmethod
    def create_user(db: Session, user_data: UserCreate, role_names: list[str] = None) -> User:
        """
        Cria um novo usuario

        Se company_name for informado, cria uma nova empresa e associa o usuario como admin.
        Se company_id for informado, associa o usuario a empresa existente.

        Args:
            db: Sessao do banco de dados
            user_data: Dados do usuario (inclui campos de empresa opcionais)
            role_names: Lista de nomes de roles para atribuir ao usuario

        Returns:
            Usuario criado
        """
        # Verificar se email ja existe (mensagem generica para evitar enumeracao)
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise ValueError("Nao foi possivel criar a conta. Verifique os dados e tente novamente.")

        company_id = None

        # Criar nova empresa se company_name foi informado
        if hasattr(user_data, 'company_name') and user_data.company_name:
            company = AuthService._create_company_for_registration(
                db,
                name=user_data.company_name,
                cnpj=getattr(user_data, 'company_cnpj', None),
                phone=getattr(user_data, 'company_phone', None),
                email=user_data.email,
            )
            company_id = company.id
            # Se criou empresa, default role e admin
            if not role_names:
                role_names = ["admin"]
            logger.info(f"Empresa '{user_data.company_name}' criada no registro (id={company.id})")

        # Vincular a empresa existente se company_id informado
        elif hasattr(user_data, 'company_id') and user_data.company_id:
            company = db.query(Company).filter(
                Company.id == user_data.company_id,
                Company.is_active == True,
            ).first()
            if not company:
                raise ValueError(f"Empresa {user_data.company_id} nao encontrada ou inativa")
            company_id = company.id

        # Criar usuario
        db_user = User(
            email=user_data.email,
            name=user_data.name,
            password_hash=get_password_hash(user_data.password),
            status="active",
            company_id=company_id,
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
            # Role padrao: viewer
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
            metadata_json={
                "email": user_data.email,
                "name": user_data.name,
                "company_id": company_id,
            }
        )
        db.add(audit)
        db.commit()

        return db_user

    @staticmethod
    def _create_company_for_registration(
        db: Session,
        name: str,
        cnpj: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Company:
        """Cria empresa durante o registro de usuario"""
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower().strip()).strip('-') or "empresa"

        # Slug unico
        existing = db.query(Company).filter(Company.slug == slug).first()
        if existing:
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"

        # CNPJ unico
        if cnpj:
            existing_cnpj = db.query(Company).filter(Company.cnpj == cnpj).first()
            if existing_cnpj:
                raise ValueError(f"CNPJ '{cnpj}' ja cadastrado")

        company = Company(
            name=name,
            slug=slug,
            cnpj=cnpj,
            phone=phone,
            email=email,
            plan="free",
        )
        db.add(company)
        db.flush()

        return company

    @staticmethod
    def authenticate_user(db: Session, credentials: UserLogin) -> Optional[User]:
        """
        Autentica um usuario

        Prevencao contra timing attacks: sempre executa verify_password
        mesmo que usuario nao exista, para evitar enumeration.

        Args:
            db: Sessao do banco de dados
            credentials: Credenciais de login

        Returns:
            Usuario autenticado ou None se credenciais invalidas
        """
        user = db.query(User).filter(User.email == credentials.email).first()

        # Dummy hash para manter tempo constante quando usuario nao existe
        _dummy_hash = "$2b$12$LJ3m4ys3Lz0rNqV956Fx7etXMWxGMuaL2b0HOrdFVMpMYP7QmFi2C"
        stored_hash = user.password_hash if user else _dummy_hash

        password_valid = verify_password(credentials.password, stored_hash)

        if not user or not password_valid:
            return None

        if user.status != "active":
            raise ValueError("Conta inativa ou suspensa")

        # Atualizar último login
        user.last_login = datetime.now(timezone.utc)
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
            raise ValueError("Senha atual incorreta")

        # Nao permitir reusar a mesma senha
        if old_password == new_password:
            raise ValueError("A nova senha deve ser diferente da senha atual")

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
