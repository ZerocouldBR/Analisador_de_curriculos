#!/usr/bin/env python3
"""
Script de setup rapido para o Analisador de Curriculos.

Uso:
    python setup.py local    # Configurar para desenvolvimento local
    python setup.py vps      # Configurar para producao em VPS
    python setup.py initdb   # Inicializar banco de dados e usuario admin
"""
import os
import sys
import secrets
import shutil
import subprocess
import time


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

# Banco de Dados (localhost via Docker ou instalacao local)
DATABASE_URL=postgresql+psycopg://analisador:analisador@localhost:5432/analisador_curriculos

# Redis (localhost via Docker ou instalacao local)
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
    flower_password = secrets.token_urlsafe(12)
    grafana_password = secrets.token_urlsafe(12)

    env_content = f"""# === Gerado automaticamente por setup.py (producao VPS) ===

# Aplicacao
APP_VERSION=0.3.0
LOG_LEVEL=WARNING
DEBUG=false

# Banco de Dados (Docker)
DATABASE_URL=postgresql+psycopg://analisador:{db_password}@db:5432/analisador_curriculos

# Redis (Docker com senha)
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
FLOWER_PASSWORD={flower_password}
GRAFANA_USER=admin
GRAFANA_PASSWORD={grafana_password}
FRONTEND_API_URL=https://curriculos.seudominio.com.br
FRONTEND_WS_URL=wss://curriculos.seudominio.com.br
"""
    with open(root_env, "w", encoding="utf-8") as f:
        f.write(root_env_content)

    print(f"  [OK] {env_path} criado")
    print(f"  [OK] {root_env} criado")
    print(f"\n  Senhas geradas automaticamente:")
    print(f"    DB Password:      {db_password}")
    print(f"    Redis Password:   {redis_password}")
    print(f"    Flower Password:  {flower_password}")
    print(f"    Grafana Password: {grafana_password}")
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


def init_database(backend_dir):
    """Inicializa banco de dados: tabelas, extensoes, indices e usuario admin"""
    print("\n[DB] Inicializando banco de dados...")

    # Verifica se o .env existe
    env_path = os.path.join(backend_dir, ".env")
    if not os.path.exists(env_path):
        print("  [ERRO] Arquivo .env nao encontrado!")
        print("  Execute primeiro: python setup.py local")
        return False

    # Tenta conectar ao banco
    print("  Verificando conexao com PostgreSQL...")
    result = subprocess.run(
        [sys.executable, "-c", """
import sys
sys.path.insert(0, '.')
os.chdir('backend')
from app.db.database import engine
from sqlalchemy import text
with engine.connect() as conn:
    conn.execute(text('SELECT 1'))
print('OK')
"""],
        capture_output=True, text=True,
        cwd=os.path.dirname(backend_dir),
        env={**os.environ, "PYTHONPATH": backend_dir}
    )

    # Run init_db
    print("  Criando tabelas e indices...")
    result = subprocess.run(
        [sys.executable, "-m", "app.db.init_db"],
        capture_output=True, text=True,
        cwd=backend_dir
    )
    if result.returncode != 0:
        print(f"  [ERRO] Falha ao criar tabelas:")
        print(f"  {result.stderr}")
        if "connection refused" in result.stderr.lower() or "could not connect" in result.stderr.lower():
            print("\n  O PostgreSQL esta rodando? Tente:")
            print("    docker compose -f docker-compose.dev.yml up -d")
        return False
    print(result.stdout)

    # Run init_roles
    print("  Criando roles e usuario admin...")
    result = subprocess.run(
        [sys.executable, "-m", "app.db.init_roles"],
        capture_output=True, text=True,
        cwd=backend_dir
    )
    if result.returncode != 0:
        print(f"  [ERRO] Falha ao criar roles: {result.stderr}")
        return False
    print(result.stdout)

    print("  [OK] Banco de dados inicializado!")
    print("\n  Usuario admin criado:")
    print("    Email: admin@analisador.com")
    print("    Senha: admin123")
    print("    ** ALTERE A SENHA EM PRODUCAO! **")
    return True


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(script_dir, "backend")

    if len(sys.argv) < 2 or sys.argv[1] not in ("local", "vps", "initdb"):
        print(__doc__)
        print("Modos disponiveis:")
        print("  local   - Gerar .env para desenvolvimento local")
        print("  vps     - Gerar .env para producao em VPS com Docker")
        print("  initdb  - Inicializar banco de dados e criar usuario admin")
        print()
        print("Fluxo completo para desenvolvimento local:")
        print("  1. python setup.py local")
        print("  2. docker compose -f docker-compose.dev.yml up -d")
        print("  3. python setup.py initdb")
        print("  4. cd backend && uvicorn app.main:app --reload")
        print("  5. cd frontend && npm install && npm start")
        sys.exit(1)

    mode = sys.argv[1]
    print(f"\n{'='*60}")
    print(f"  Setup: Analisador de Curriculos ({mode.upper()})")
    print(f"{'='*60}\n")

    if mode == "local":
        print("[1/2] Criando .env para desenvolvimento local...")
        secret = create_env_local(backend_dir)

        print("\n[2/2] Verificando Docker...")
        has_docker = check_docker() and check_docker_compose()
        if has_docker:
            print("  [OK] Docker encontrado")
        else:
            print("  [!] Docker nao encontrado - instale PostgreSQL e Redis manualmente")

        print(f"\n{'='*60}")
        print("  Proximos passos:")
        print(f"{'='*60}\n")

        if has_docker:
            print("  1. Subir PostgreSQL + Redis via Docker:")
            print("     docker compose -f docker-compose.dev.yml up -d\n")
        else:
            print("  1. Instale PostgreSQL 16 (com pgvector) e Redis 7")
            print("     Crie o banco: CREATE DATABASE analisador_curriculos;")
            print("     Crie o usuario: CREATE USER analisador WITH PASSWORD 'analisador';")
            print("     GRANT ALL ON DATABASE analisador_curriculos TO analisador;\n")

        print("  2. Inicializar o banco de dados:")
        print("     python setup.py initdb\n")

        print("  3. Iniciar o backend:")
        print("     cd backend")
        if sys.platform == "win32":
            print("     python -m venv .venv")
            print("     .venv\\Scripts\\activate")
        else:
            print("     python3 -m venv .venv")
            print("     source .venv/bin/activate")
        print("     pip install -r requirements.txt")
        print("     uvicorn app.main:app --reload\n")

        print("  4. Iniciar o frontend (novo terminal):")
        print("     cd frontend")
        print("     npm install")
        print("     npm start\n")

        print("  5. Acessar:")
        print("     Frontend: http://localhost:3000")
        print("     API Docs: http://localhost:8000/docs")
        print("     Login:    admin@analisador.com / admin123")

    elif mode == "vps":
        print("[1/2] Criando .env para producao...")
        secret, db_pass, redis_pass = create_env_vps(backend_dir)

        print("\n[2/2] Verificando Docker...")
        has_docker = check_docker() and check_docker_compose()
        if has_docker:
            print("  [OK] Docker encontrado")
        else:
            print("  [ERRO] Docker nao encontrado!")
            print("  Instale: https://docs.docker.com/engine/install/")
            sys.exit(1)

        print(f"\n{'='*60}")
        print("  Proximos passos:")
        print(f"{'='*60}\n")

        print("  1. Edite os dominios:")
        print("     backend/.env  -> CORS_ORIGINS")
        print("     .env          -> FRONTEND_API_URL, FRONTEND_WS_URL\n")

        print("  2. Adicione sua OPENAI_API_KEY no backend/.env\n")

        print("  3. Suba tudo com Docker Compose:")
        print("     docker compose -f docker-compose.prod.yml up -d --build\n")

        print("  4. Inicialize o banco (executar uma vez apos o primeiro deploy):")
        print("     docker compose -f docker-compose.prod.yml exec api python -m app.db.init_db")
        print("     docker compose -f docker-compose.prod.yml exec api python -m app.db.init_roles\n")

        print("  5. Acesse:")
        print("     Frontend: http://seu-ip:3000")
        print("     API Docs: http://seu-ip:8000/docs")
        print("     Flower:   http://seu-ip:5555")
        print("     Grafana:  http://seu-ip:3001")
        print("     Login:    admin@analisador.com / admin123")

    elif mode == "initdb":
        init_database(backend_dir)

    print(f"\n{'='*60}")
    print("  Setup concluido!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
