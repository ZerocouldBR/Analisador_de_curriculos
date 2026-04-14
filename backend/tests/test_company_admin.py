"""
Testes do role company_admin

Testa:
- Permissoes do company_admin na propria empresa
- Restricoes de acesso a outras empresas
- Gerenciamento de roles (recruiter/viewer apenas)
- Acesso a custos e analytics da propria empresa
- Bloqueio de operacoes de superuser
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.database import Base, get_db
from app.db.models import User, Role, Company
from app.core.security import get_password_hash


SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture
def setup_database():
    """Criar e limpar banco de dados para cada teste"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def setup_company_admin(setup_database):
    """Cria cenario com empresa, company_admin, recruiter e viewer"""
    db = TestingSessionLocal()

    # Criar roles
    company_admin_role = Role(
        name="company_admin",
        description="Admin da empresa",
        permissions={
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
        }
    )
    db.add(company_admin_role)

    recruiter_role = Role(
        name="recruiter",
        description="Recrutador",
        permissions={
            "candidates.create": True,
            "candidates.read": True,
            "candidates.update": True,
            "candidates.delete": False,
            "documents.create": True,
            "documents.read": True,
            "documents.update": True,
            "documents.delete": False,
            "settings.read": True,
            "settings.create": False,
            "settings.update": False,
            "settings.delete": False,
            "linkedin.enrich": True,
            "search.advanced": True,
            "users.manage": False,
        }
    )
    db.add(recruiter_role)

    viewer_role = Role(
        name="viewer",
        description="Visualizador",
        permissions={
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
    )
    db.add(viewer_role)

    admin_role = Role(
        name="admin",
        description="Admin completo",
        permissions={
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
        }
    )
    db.add(admin_role)
    db.flush()

    # Criar empresa 1
    company1 = Company(
        name="Empresa RH Alpha",
        slug="empresa-rh-alpha",
        plan="pro",
        is_active=True,
    )
    db.add(company1)

    # Criar empresa 2
    company2 = Company(
        name="Empresa RH Beta",
        slug="empresa-rh-beta",
        plan="basic",
        is_active=True,
    )
    db.add(company2)
    db.flush()

    # Criar company_admin da empresa 1
    ca_user = User(
        email="ca@alpha.com",
        name="Company Admin Alpha",
        password_hash=get_password_hash("Capass123!"),
        status="active",
        company_id=company1.id,
        is_superuser=False,
    )
    ca_user.roles.append(company_admin_role)
    db.add(ca_user)

    # Criar recruiter da empresa 1
    rec_user = User(
        email="rec@alpha.com",
        name="Recruiter Alpha",
        password_hash=get_password_hash("Recpass123!"),
        status="active",
        company_id=company1.id,
        is_superuser=False,
    )
    rec_user.roles.append(recruiter_role)
    db.add(rec_user)

    # Criar viewer da empresa 1 (sem roles ainda, para teste de atribuicao)
    viewer_user = User(
        email="viewer@alpha.com",
        name="Viewer Alpha",
        password_hash=get_password_hash("Viewpass123!"),
        status="active",
        company_id=company1.id,
        is_superuser=False,
    )
    db.add(viewer_user)

    # Criar user da empresa 2
    other_user = User(
        email="user@beta.com",
        name="User Beta",
        password_hash=get_password_hash("Betapass123!"),
        status="active",
        company_id=company2.id,
        is_superuser=False,
    )
    other_user.roles.append(recruiter_role)
    db.add(other_user)

    # Criar superuser (sem empresa)
    superuser = User(
        email="super@system.com",
        name="Superuser",
        password_hash=get_password_hash("Superpass123!"),
        status="active",
        is_superuser=True,
    )
    superuser.roles.append(admin_role)
    db.add(superuser)

    db.commit()

    # Extrair IDs antes de fechar a sessao para evitar DetachedInstanceError
    result = {
        "company1_id": company1.id,
        "company2_id": company2.id,
        "ca_user_id": ca_user.id,
        "rec_user_id": rec_user.id,
        "viewer_user_id": viewer_user.id,
        "other_user_id": other_user.id,
        "superuser_id": superuser.id,
    }

    db.close()

    yield result


def _login(email: str, password: str) -> str:
    """Helper para obter token de login"""
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password}
    )
    assert response.status_code == 200, f"Login falhou para {email}: {response.text}"
    return response.json()["access_token"]


@pytest.mark.unit
class TestCompanyAdminAccess:
    """Testes de acesso do company_admin"""

    def test_company_admin_can_list_own_users(self, setup_company_admin):
        """company_admin pode listar usuarios da propria empresa"""
        data = setup_company_admin
        token = _login("ca@alpha.com", "Capass123!")

        response = client.get(
            "/api/v1/companies/me/users",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        users = response.json()
        # Deve ver 3 usuarios da empresa alpha
        emails = [u["email"] for u in users]
        assert "ca@alpha.com" in emails
        assert "rec@alpha.com" in emails
        assert "viewer@alpha.com" in emails
        # Nao deve ver usuario da empresa beta
        assert "user@beta.com" not in emails

    def test_company_admin_can_view_own_company(self, setup_company_admin):
        """company_admin pode ver dados da propria empresa"""
        token = _login("ca@alpha.com", "Capass123!")

        response = client.get(
            "/api/v1/companies/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Empresa RH Alpha"

    def test_company_admin_can_update_own_company(self, setup_company_admin):
        """company_admin pode atualizar dados da propria empresa"""
        token = _login("ca@alpha.com", "Capass123!")

        response = client.put(
            "/api/v1/companies/me",
            json={"phone": "(11) 99999-0000"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        assert response.json()["phone"] == "(11) 99999-0000"

    def test_company_admin_cannot_access_other_company_users(self, setup_company_admin):
        """company_admin NAO pode listar usuarios de outra empresa"""
        data = setup_company_admin
        token = _login("ca@alpha.com", "Capass123!")

        response = client.get(
            f"/api/v1/companies/{data['company2_id']}/users",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403

    def test_company_admin_cannot_cleanup_database(self, setup_company_admin):
        """company_admin NAO pode fazer cleanup do banco"""
        token = _login("ca@alpha.com", "Capass123!")

        response = client.post(
            "/api/v1/admin/cleanup",
            json={
                "delete_candidates": True,
                "delete_documents": True,
                "delete_chunks": True,
                "delete_experiences": True,
                "confirm": "CONFIRMAR",
            },
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403

    def test_company_admin_can_view_stats(self, setup_company_admin):
        """company_admin pode ver estatisticas (filtradas por empresa)"""
        token = _login("ca@alpha.com", "Capass123!")

        response = client.get(
            "/api/v1/admin/stats",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200


@pytest.mark.unit
class TestCompanyAdminRoleManagement:
    """Testes de gerenciamento de roles pelo company_admin"""

    def test_company_admin_can_assign_recruiter(self, setup_company_admin):
        """company_admin pode atribuir role recruiter a user da propria empresa"""
        data = setup_company_admin
        token = _login("ca@alpha.com", "Capass123!")

        response = client.post(
            f"/api/v1/companies/me/users/{data['viewer_user_id']}/roles/recruiter",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        assert response.json()["status"] == "assigned"

    def test_company_admin_can_assign_viewer(self, setup_company_admin):
        """company_admin pode atribuir role viewer"""
        data = setup_company_admin
        token = _login("ca@alpha.com", "Capass123!")

        response = client.post(
            f"/api/v1/companies/me/users/{data['viewer_user_id']}/roles/viewer",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200

    def test_company_admin_cannot_assign_admin_role(self, setup_company_admin):
        """company_admin NAO pode atribuir role admin"""
        data = setup_company_admin
        token = _login("ca@alpha.com", "Capass123!")

        response = client.post(
            f"/api/v1/companies/me/users/{data['viewer_user_id']}/roles/admin",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403

    def test_company_admin_cannot_assign_company_admin_role(self, setup_company_admin):
        """company_admin NAO pode atribuir role company_admin"""
        data = setup_company_admin
        token = _login("ca@alpha.com", "Capass123!")

        response = client.post(
            f"/api/v1/companies/me/users/{data['viewer_user_id']}/roles/company_admin",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403

    def test_company_admin_cannot_assign_role_to_other_company_user(self, setup_company_admin):
        """company_admin NAO pode atribuir role a user de outra empresa"""
        data = setup_company_admin
        token = _login("ca@alpha.com", "Capass123!")

        response = client.post(
            f"/api/v1/companies/me/users/{data['other_user_id']}/roles/recruiter",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403

    def test_company_admin_can_remove_recruiter_role(self, setup_company_admin):
        """company_admin pode remover role recruiter"""
        data = setup_company_admin
        token = _login("ca@alpha.com", "Capass123!")

        response = client.delete(
            f"/api/v1/companies/me/users/{data['rec_user_id']}/roles/recruiter",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        assert response.json()["status"] == "removed"


@pytest.mark.unit
class TestCompanyAdminVsSuperuser:
    """Testes comparando acesso company_admin vs superuser"""

    def test_superuser_can_list_all_companies(self, setup_company_admin):
        """superuser pode listar todas as empresas"""
        token = _login("super@system.com", "Superpass123!")

        response = client.get(
            "/api/v1/companies/",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        assert len(response.json()) >= 2

    def test_company_admin_cannot_list_all_companies(self, setup_company_admin):
        """company_admin NAO pode listar todas as empresas"""
        token = _login("ca@alpha.com", "Capass123!")

        response = client.get(
            "/api/v1/companies/",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403

    def test_superuser_can_create_company(self, setup_company_admin):
        """superuser pode criar empresa"""
        token = _login("super@system.com", "Superpass123!")

        response = client.post(
            "/api/v1/companies/",
            json={"name": "Nova Empresa", "plan": "free"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 201

    def test_recruiter_cannot_manage_roles(self, setup_company_admin):
        """recruiter NAO pode gerenciar roles"""
        data = setup_company_admin
        token = _login("rec@alpha.com", "Recpass123!")

        response = client.get(
            "/api/v1/companies/me/users",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
