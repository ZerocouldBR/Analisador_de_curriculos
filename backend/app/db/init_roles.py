"""
Script para inicializar roles padrão no banco de dados
"""

from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db.models import Role, User
from app.core.security import get_password_hash


def create_default_roles(db: Session):
    """
    Cria os roles padrão do sistema

    Roles:
    - admin: Acesso completo ao sistema
    - recruiter: Pode gerenciar candidatos e currículos
    - viewer: Apenas visualização
    """

    roles_data = [
        {
            "name": "admin",
            "description": "Administrador com acesso completo ao sistema",
            "permissions": {
                "candidates.create": True,
                "candidates.read": True,
                "candidates.update": True,
                "candidates.delete": True,
                "documents.create": True,
                "documents.read": True,
                "documents.update": True,
                "documents.delete": True,
                "settings.read": True,
                "settings.create": True,
                "settings.update": True,
                "settings.delete": True,
                "linkedin.enrich": True,
                "search.advanced": True,
                "users.manage": True,
                "companies.manage_own": True,
                "analytics.view": True,
                "costs.view": True,
                "sourcing.read": True,
                "sourcing.config": True,
                "sourcing.sync": True,
                "sourcing.merge": True,
            }
        },
        {
            "name": "company_admin",
            "description": "Administrador de empresa - gerencia usuarios, custos e configuracoes da propria empresa",
            "permissions": {
                "candidates.create": True,
                "candidates.read": True,
                "candidates.update": True,
                "candidates.delete": True,
                "documents.create": True,
                "documents.read": True,
                "documents.update": True,
                "documents.delete": True,
                "settings.read": True,
                "settings.create": False,
                "settings.update": True,
                "settings.delete": False,
                "linkedin.enrich": True,
                "search.advanced": True,
                "users.manage": True,
                "companies.manage_own": True,
                "analytics.view": True,
                "costs.view": True,
                "sourcing.read": True,
                "sourcing.config": True,
                "sourcing.sync": True,
                "sourcing.merge": True,
            }
        },
        {
            "name": "recruiter",
            "description": "Recrutador com acesso a candidatos e currículos",
            "permissions": {
                "candidates.create": True,
                "candidates.read": True,
                "candidates.update": True,
                "candidates.delete": False,  # Não pode deletar
                "documents.create": True,
                "documents.read": True,
                "documents.update": True,
                "documents.delete": False,  # Não pode deletar
                "settings.read": True,
                "settings.create": False,
                "settings.update": False,
                "settings.delete": False,
                "linkedin.enrich": True,
                "search.advanced": True,
                "users.manage": False,
                "sourcing.read": True,
                "sourcing.config": False,
                "sourcing.sync": True,
                "sourcing.merge": False,
            }
        },
        {
            "name": "viewer",
            "description": "Visualizador com acesso apenas de leitura",
            "permissions": {
                "candidates.create": False,
                "candidates.read": True,
                "candidates.update": False,
                "candidates.delete": False,
                "documents.create": False,
                "documents.read": True,
                "documents.update": False,
                "documents.delete": False,
                "settings.read": True,
                "settings.create": False,
                "settings.update": False,
                "settings.delete": False,
                "linkedin.enrich": False,
                "search.advanced": False,
                "users.manage": False,
            }
        }
    ]

    created_roles = []

    for role_data in roles_data:
        # Verificar se role já existe
        existing_role = db.query(Role).filter(Role.name == role_data["name"]).first()

        if existing_role:
            print(f"✓ Role '{role_data['name']}' já existe")
            created_roles.append(existing_role)
        else:
            # Criar role
            role = Role(**role_data)
            db.add(role)
            db.flush()
            created_roles.append(role)
            print(f"✓ Role '{role_data['name']}' criado")

    db.commit()
    return created_roles


def create_superuser(
    db: Session,
    email: str,
    password: str,
    name: str
):
    """
    Cria um superuser

    Args:
        db: Sessão do banco de dados
        email: Email do superuser
        password: Senha
        name: Nome
    """
    # Verificar se usuário já existe
    existing_user = db.query(User).filter(User.email == email).first()

    if existing_user:
        print(f"⚠ Usuário '{email}' já existe")
        return existing_user

    # Criar superuser
    superuser = User(
        email=email,
        name=name,
        password_hash=get_password_hash(password),
        status="active",
        is_superuser=True
    )

    db.add(superuser)

    # Atribuir role admin
    admin_role = db.query(Role).filter(Role.name == "admin").first()
    if admin_role:
        superuser.roles.append(admin_role)

    db.commit()
    db.refresh(superuser)

    print(f"✓ Superuser '{email}' criado com sucesso")
    return superuser


def init_roles():
    """Inicializa roles e superuser padrão"""
    print("Inicializando roles padrão...")

    db = SessionLocal()

    try:
        # Criar roles
        create_default_roles(db)

        # Criar superuser padrão
        print("\nCriando superuser padrão...")
        create_superuser(
            db,
            email="admin@analisador.com",
            password="admin123",  # ALTERE ISSO EM PRODUÇÃO!
            name="Administrador"
        )

        print("\n✓ Roles e superuser inicializados com sucesso!")
        print("\n⚠ IMPORTANTE: Altere a senha padrão do superuser em produção!")
        print("   Email: admin@analisador.com")
        print("   Senha: admin123")

    except Exception as e:
        print(f"\n✗ Erro ao inicializar roles: {e}")
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    init_roles()
