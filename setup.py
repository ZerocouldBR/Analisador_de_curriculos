#!/usr/bin/env python3
"""
Script de setup rapido para o Analisador de Curriculos.

Uso:
    python setup.py local    # Configurar para desenvolvimento local
    python setup.py vps      # Configurar para producao em VPS
"""
import os
import sys
import secrets
import shutil
import subprocess


def generate_secret():
    return secrets.token_urlsafe(32)


def create_env_local(backend_dir):
    """Cria .env para desenvolvimento local (localhost)"""
    secret = generate_secret()
    env_content = f"""# === Gerado automaticamente por setup.py (desenvolvimento local) ===

# Aplicacao
APP_VERSION=0.3.0
LOG_LEVEL=DEBUG
DEBUG=true

# Banco de Dados (local - use 'db' se rodar via Docker Compose)
DATABASE_URL=postgresql+psycopg://analisador:analisador@localhost:5432/analisador_curriculos

# Redis (local - use 'redis' se rodar via Docker Compose)
REDIS_URL=redis://localhost:6379/0

# JWT
SECRET_KEY={secret}

# CORS
CORS_ORIGINS=["http://localhost:3000"]

# OpenAI (descomente e preencha para usar embeddings e chat)
# OPENAI_API_KEY=sk-your-api-key-here

# Vector DB
VECTOR_DB_PROVIDER=pgvector
EMBEDDING_MODE=api
"""
    env_path = os.path.join(backend_dir, ".env")
    if os.path.exists(env_path):
        print(f"  [!] {env_path} ja existe. Criando backup .env.bak")
        shutil.copy2(env_path, env_path + ".bak")

    with open(env_path, "w", encoding="utf-8") as f:
        f.write(env_content)
    print(f"  [OK] {env_path} criado")
    return secret


def create_env_vps(backend_dir):
    """Cria .env para producao em VPS"""
    secret = generate_secret()
    db_password = secrets.token_urlsafe(16)
    redis_password = secrets.token_urlsafe(16)

    env_content = f"""# === Gerado automaticamente por setup.py (producao VPS) ===

# Aplicacao
APP_VERSION=0.3.0
LOG_LEVEL=WARNING
DEBUG=false

# Banco de Dados (Docker)
DATABASE_URL=postgresql+psycopg://analisador:{db_password}@db:5432/analisador_curriculos

# Redis (Docker)
REDIS_URL=redis://:{redis_password}@redis:6379/0

# JWT
SECRET_KEY={secret}

# CORS (altere para seu dominio)
CORS_ORIGINS=["https://curriculos.seudominio.com.br"]

# OpenAI (descomente e preencha)
# OPENAI_API_KEY=sk-your-api-key-here

# Vector DB
VECTOR_DB_PROVIDER=pgvector
EMBEDDING_MODE=api
"""
    env_path = os.path.join(backend_dir, ".env")
    if os.path.exists(env_path):
        print(f"  [!] {env_path} ja existe. Criando backup .env.bak")
        shutil.copy2(env_path, env_path + ".bak")

    with open(env_path, "w", encoding="utf-8") as f:
        f.write(env_content)

    # Criar .env na raiz para docker-compose.prod.yml
    root_dir = os.path.dirname(backend_dir)
    root_env = os.path.join(root_dir, ".env")
    root_env_content = f"""# Variaveis para docker-compose.prod.yml
DB_PASSWORD={db_password}
REDIS_PASSWORD={redis_password}
FLOWER_USER=admin
FLOWER_PASSWORD={secrets.token_urlsafe(12)}
GRAFANA_USER=admin
GRAFANA_PASSWORD={secrets.token_urlsafe(12)}
FRONTEND_API_URL=https://curriculos.seudominio.com.br
FRONTEND_WS_URL=wss://curriculos.seudominio.com.br
"""
    with open(root_env, "w", encoding="utf-8") as f:
        f.write(root_env_content)

    print(f"  [OK] {env_path} criado")
    print(f"  [OK] {root_env} criado")
    print(f"\n  Senhas geradas automaticamente:")
    print(f"    DB Password:    {db_password}")
    print(f"    Redis Password: {redis_password}")
    return secret, db_password, redis_password


def check_docker():
    try:
        result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def check_docker_compose():
    try:
        result = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(script_dir, "backend")

    if len(sys.argv) < 2 or sys.argv[1] not in ("local", "vps"):
        print(__doc__)
        print("Modos disponiveis:")
        print("  local  - Desenvolvimento local (PostgreSQL e Redis no localhost ou Docker)")
        print("  vps    - Producao em VPS (tudo via Docker Compose)")
        sys.exit(1)

    mode = sys.argv[1]
    print(f"\n{'='*60}")
    print(f"  Setup: Analisador de Curriculos ({mode.upper()})")
    print(f"{'='*60}\n")

    if mode == "local":
        print("[1/3] Criando .env para desenvolvimento local...")
        secret = create_env_local(backend_dir)

        print("\n[2/3] Verificando Docker...")
        has_docker = check_docker() and check_docker_compose()
        if has_docker:
            print("  [OK] Docker encontrado")
        else:
            print("  [!] Docker nao encontrado - instale PostgreSQL e Redis manualmente")

        print(f"\n[3/3] Proximos passos:\n")
        if has_docker:
            print("  Opcao A - Banco via Docker (recomendado):")
            print("    docker compose up db redis -d")
            print()
        print("  Opcao B - Banco local:")
        print("    Instale PostgreSQL 16 com pgvector e Redis")
        print("    Crie o banco: CREATE DATABASE analisador_curriculos;")
        print("    Crie o usuario: CREATE USER analisador WITH PASSWORD 'analisador';")
        print()
        print("  Depois, inicie o backend:")
        print("    cd backend")
        print("    python -m venv .venv")
        if sys.platform == "win32":
            print("    .venv\\Scripts\\activate")
        else:
            print("    source .venv/bin/activate")
        print("    pip install -r requirements.txt")
        print("    uvicorn app.main:app --reload")
        print()
        print("  E o frontend:")
        print("    cd frontend")
        print("    npm install")
        print("    npm start")

    elif mode == "vps":
        print("[1/3] Criando .env para producao...")
        secret, db_pass, redis_pass = create_env_vps(backend_dir)

        print("\n[2/3] Verificando Docker...")
        has_docker = check_docker() and check_docker_compose()
        if has_docker:
            print("  [OK] Docker encontrado")
        else:
            print("  [ERRO] Docker nao encontrado!")
            print("  Instale: https://docs.docker.com/engine/install/")
            sys.exit(1)

        print(f"\n[3/3] Proximos passos:\n")
        print("  1. Edite os dominios nos arquivos .env:")
        print("     - backend/.env  (CORS_ORIGINS)")
        print("     - .env          (FRONTEND_API_URL, FRONTEND_WS_URL)")
        print()
        print("  2. Adicione sua OPENAI_API_KEY no backend/.env")
        print()
        print("  3. Suba tudo com Docker Compose:")
        print("    docker compose -f docker-compose.prod.yml up -d --build")
        print()
        print("  4. Acesse:")
        print("    - Frontend: http://seu-ip:3000")
        print("    - API Docs: http://seu-ip:8000/docs")
        print("    - Flower:   http://seu-ip:5555")
        print("    - Grafana:  http://seu-ip:3001")

    print(f"\n{'='*60}")
    print("  Setup concluido!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
