import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.database import Base, get_db
from app.db.models import User, Role
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


@pytest.fixture(scope="function")
def db():
    """Database session for tests"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    """Test client"""
    return TestClient(app)


@pytest.fixture
def test_user(db):
    """Cria usuário de teste"""
    user = User(
        email="testuser@example.com",
        name="Test User",
        password_hash=get_password_hash("testpass123"),
        status="active"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_user(db):
    """Cria usuário admin de teste"""
    # Criar role admin
    admin_role = Role(
        name="admin",
        description="Administrator",
        permissions={
            "candidates.create": True,
            "candidates.delete": True,
            "documents.create": True,
            "documents.delete": True,
            "settings.update": True,
        }
    )
    db.add(admin_role)

    # Criar usuário admin
    user = User(
        email="admin@example.com",
        name="Admin User",
        password_hash=get_password_hash("adminpass123"),
        status="active",
        is_superuser=True
    )
    user.roles.append(admin_role)

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@pytest.fixture
def auth_token(client, test_user):
    """Obtém token de autenticação para o usuário de teste"""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "testuser@example.com",
            "password": "testpass123"
        }
    )
    return response.json()["access_token"]


@pytest.fixture
def admin_token(client, admin_user):
    """Obtém token de autenticação para o admin"""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@example.com",
            "password": "adminpass123"
        }
    )
    return response.json()["access_token"]
