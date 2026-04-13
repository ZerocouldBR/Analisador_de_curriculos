import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.database import Base, get_db
from app.core.security import get_password_hash


# Database de teste em memória
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


class TestAuthentication:
    def test_register_user(self, setup_database):
        """Testa registro de novo usuário"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "name": "Test User",
                "password": "testpass123"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["name"] == "Test User"
        assert "id" in data

    def test_register_duplicate_email(self, setup_database):
        """Testa registro com email duplicado"""
        # Registrar primeiro usuário
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "name": "Test User",
                "password": "testpass123"
            }
        )

        # Tentar registrar com mesmo email
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "name": "Another User",
                "password": "anotherpass123"
            }
        )

        assert response.status_code == 400
        assert "já cadastrado" in response.json()["detail"].lower()

    def test_login_success(self, setup_database):
        """Testa login com credenciais válidas"""
        # Registrar usuário
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "name": "Test User",
                "password": "testpass123"
            }
        )

        # Login (OAuth2 form data)
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "test@example.com",
                "password": "testpass123"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["email"] == "test@example.com"

    def test_login_wrong_password(self, setup_database):
        """Testa login com senha incorreta"""
        # Registrar usuário
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "name": "Test User",
                "password": "testpass123"
            }
        )

        # Tentar login com senha errada
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "test@example.com",
                "password": "wrongpassword"
            }
        )

        assert response.status_code == 401

    def test_get_current_user(self, setup_database):
        """Testa obter informações do usuário autenticado"""
        # Registrar e fazer login
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "name": "Test User",
                "password": "testpass123"
            }
        )

        login_response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "test@example.com",
                "password": "testpass123"
            }
        )

        token = login_response.json()["access_token"]

        # Obter informações do usuário
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["name"] == "Test User"

    def test_access_protected_route_without_token(self, setup_database):
        """Testa acesso a rota protegida sem token"""
        response = client.get("/api/v1/auth/me")

        assert response.status_code == 403  # Forbidden (sem token)
