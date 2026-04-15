#!/usr/bin/env python3
"""
Script de setup rapido para o Analisador de Curriculos.

Uso:
    python setup.py local    # Configurar para desenvolvimento local
    python setup.py vps      # Configurar para producao em VPS (interativo)
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


def mask_secret(value, visible=4):
    """Mascara um segredo, exibindo apenas os primeiros caracteres"""
    if len(value) <= visible:
        return "*" * len(value)
    return value[:visible] + "*" * (len(value) - visible)


def prompt_input(label, default="", sensitive=False):
    """Solicita input do usuario com valor padrao"""
    if default:
        display = "****" if sensitive else default
        raw = input(f"  {label} [{display}]: ").strip()
    else:
        raw = input(f"  {label}: ").strip()
    return raw if raw else default


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
DATABASE_SCHEMA=public

# Redis (localhost via Docker ou instalacao local)
REDIS_URL=redis://localhost:6379/0

# JWT
SECRET_KEY={secret}

# CORS
CORS_ORIGINS=["http://localhost:3000"]

# OpenAI (descomente e preencha para usar embeddings e chat)
# OPENAI_API_KEY=sk-your-api-key-here

# Vector DB - Provedores (multiplos podem estar ativos)
VECTOR_DB_PROVIDER=pgvector
VECTOR_DB_PRIMARY=pgvector
PGVECTOR_ENABLED=true
SUPABASE_ENABLED=false
QDRANT_ENABLED=false

# Embeddings
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
    """Cria .env para producao em VPS com configuracao interativa"""
    root_dir = os.path.dirname(backend_dir)

    print("\n  Configuracao interativa para producao em VPS.")
    print("  Pressione ENTER para aceitar o valor padrao entre colchetes.\n")

    # Dominio
    domain = prompt_input("Dominio (ex: curriculos.meusite.com.br)", "curriculos.seudominio.com.br")

    # Database schema
    print("\n  Schema do banco de dados:")
    print("    public     = Schema padrao do PostgreSQL")
    print("    <custom>   = Schema customizado (ex: analisador, app)")
    db_schema = prompt_input("Schema do banco de dados", "public")

    # Vector DB provider
    print("\n  Provedor de banco vetorial:")
    print("    pgvector  = PostgreSQL com pgvector (recomendado)")
    print("    supabase  = Supabase gerenciado + pgvector")
    print("    qdrant    = Qdrant dedicado (servidor separado)")
    print("    multi     = Multiplos provedores simultaneos")
    vector_provider = prompt_input("Provedor vetorial", "pgvector")

    supabase_url = ""
    supabase_key = ""
    qdrant_url = ""
    pgvector_enabled = "true"
    supabase_enabled = "false"
    qdrant_enabled = "false"

    if vector_provider == "supabase" or vector_provider == "multi":
        supabase_enabled = "true"
        supabase_url = prompt_input("Supabase URL (https://xxx.supabase.co)", "")
        supabase_key = prompt_input("Supabase Key", "", sensitive=True)

    if vector_provider == "qdrant" or vector_provider == "multi":
        qdrant_enabled = "true"
        qdrant_url = prompt_input("Qdrant URL", "http://localhost:6333")

    if vector_provider == "qdrant":
        pgvector_enabled = "false"

    vector_primary = "pgvector" if vector_provider != "qdrant" else "qdrant"
    if vector_provider == "supabase":
        vector_primary = "supabase"

    # Embeddings
    print("\n  Modo de vetorizacao:")
    print("    api  = OpenAI (pago, melhor qualidade)")
    print("    code = Local sentence-transformers (gratis, mais lento)")
    embedding_mode = prompt_input("Modo de vetorizacao", "code")

    openai_key = ""
    if embedding_mode == "api":
        openai_key = prompt_input("OpenAI API Key (sk-...)", "")

    # Chat model
    chat_model = prompt_input("Modelo LLM do chat", "gpt-4-turbo-preview")

    # OCR
    ocr_langs = prompt_input("Idiomas OCR (Tesseract)", "por+eng")

    # Upload
    max_upload = prompt_input("Tamanho max upload em MB", "20")

    # Moeda
    print("\n  Precificacao de IA:")
    currency = prompt_input("Moeda (USD, BRL, EUR)", "BRL")
    exchange_rate = "1.0"
    if currency == "BRL":
        exchange_rate = prompt_input("Taxa de cambio USD->BRL", "5.50")
    elif currency == "EUR":
        exchange_rate = prompt_input("Taxa de cambio USD->EUR", "0.92")

    # Senhas automaticas
    secret = generate_secret()
    db_password = secrets.token_urlsafe(16)
    redis_password = secrets.token_urlsafe(16)
    flower_password = secrets.token_urlsafe(12)
    grafana_password = secrets.token_urlsafe(12)

    # OpenAI line
    openai_line = f"OPENAI_API_KEY={openai_key}" if openai_key else "# OPENAI_API_KEY=sk-your-api-key-here"

    # Supabase lines
    supabase_lines = ""
    if supabase_enabled == "true" and supabase_url:
        supabase_lines = f"""
# Supabase
SUPABASE_URL={supabase_url}
SUPABASE_KEY={supabase_key}"""

    # Qdrant lines
    qdrant_lines = ""
    if qdrant_enabled == "true" and qdrant_url:
        qdrant_lines = f"""
# Qdrant
QDRANT_URL={qdrant_url}"""

    env_content = f"""# ================================================================
# Analisador de Curriculos - Configuracao de Producao
# Gerado automaticamente por setup.py
# ================================================================

# Aplicacao
APP_VERSION=0.3.0
LOG_LEVEL=WARNING
DEBUG=false

# Banco de Dados (Docker)
DATABASE_URL=postgresql+psycopg://analisador:{db_password}@db:5432/analisador_curriculos
DATABASE_SCHEMA={db_schema}

# Redis (Docker com senha)
REDIS_URL=redis://:{redis_password}@redis:6379/0

# JWT
SECRET_KEY={secret}
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS (dominio configurado)
CORS_ORIGINS=["https://{domain}"]

# Embeddings
EMBEDDING_MODE={embedding_mode}
EMBEDDING_LOCAL_MODEL=all-MiniLM-L6-v2
EMBEDDING_MODEL=text-embedding-3-small

# OpenAI
{openai_line}

# LLM / Chat
CHAT_MODEL={chat_model}

# Vector DB - Provedores
VECTOR_DB_PROVIDER={vector_primary}
VECTOR_DB_PRIMARY={vector_primary}
PGVECTOR_ENABLED={pgvector_enabled}
SUPABASE_ENABLED={supabase_enabled}
QDRANT_ENABLED={qdrant_enabled}
{supabase_lines}
{qdrant_lines}

# Upload / Storage
MAX_UPLOAD_SIZE_MB={max_upload}
STORAGE_BACKEND=local
STORAGE_PATH=/app/uploads

# OCR
OCR_LANGUAGES={ocr_langs}

# LGPD
ENABLE_PII_ENCRYPTION=true

# Precificacao IA
AI_PRICING_ENABLED=true
AI_CURRENCY={currency}
AI_CURRENCY_EXCHANGE_RATE={exchange_rate}
"""
    env_path = os.path.join(backend_dir, ".env")
    if os.path.exists(env_path):
        print(f"\n  [!] {env_path} ja existe. Criando backup .env.bak")
        shutil.copy2(env_path, env_path + ".bak")

    with open(env_path, "w", encoding="utf-8") as f:
        f.write(env_content)

    # Criar .env na raiz para docker-compose.prod.yml
    root_env = os.path.join(root_dir, ".env")
    root_env_content = f"""# Variaveis para docker-compose.prod.yml
# Gerado automaticamente por setup.py
DB_PASSWORD={db_password}
REDIS_PASSWORD={redis_password}
FLOWER_USER=admin
FLOWER_PASSWORD={flower_password}
GRAFANA_USER=admin
GRAFANA_PASSWORD={grafana_password}
FRONTEND_API_URL=https://{domain}
FRONTEND_WS_URL=wss://{domain}
"""
    if os.path.exists(root_env):
        shutil.copy2(root_env, root_env + ".bak")

    with open(root_env, "w", encoding="utf-8") as f:
        f.write(root_env_content)

    print(f"\n  [OK] {env_path} criado")
    print(f"  [OK] {root_env} criado")
    print(f"\n  ========================================")
    print(f"  CREDENCIAIS GERADAS (SALVE EM LOCAL SEGURO!)")
    print(f"  ========================================")
    print(f"    Dominio:          {domain}")
    print(f"    DB Password:      {mask_secret(db_password)}")
    print(f"    Redis Password:   {mask_secret(redis_password)}")
    print(f"    Flower Password:  {mask_secret(flower_password)}")
    print(f"    Grafana Password: {mask_secret(grafana_password)}")
    print(f"    JWT Secret:       {mask_secret(secret)}")
    print(f"    Embedding Mode:   {embedding_mode}")
    print(f"    Moeda:            {currency}")
    if supabase_enabled == "true":
        print(f"    Supabase:         {supabase_url or 'NAO CONFIGURADO'}")
    if qdrant_enabled == "true":
        print(f"    Qdrant:           {qdrant_url or 'NAO CONFIGURADO'}")
    print(f"    DB Schema:        {db_schema}")
    print(f"\n  As senhas completas estao nos arquivos .env gerados.")
    if supabase_enabled == "true":
        print(f"\n  [SUPABASE] Execute o SQL de setup no Supabase SQL Editor:")
        print(f"    cd backend && python -m app.db.init_db --supabase-sql")
    print(f"  ========================================")
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
import os, sys
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
    print("    ** ALTERE A SENHA APOS O PRIMEIRO LOGIN! **")
    return True


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(script_dir, "backend")

    if len(sys.argv) < 2 or sys.argv[1] not in ("local", "vps", "initdb"):
        print(__doc__)
        print("Modos disponiveis:")
        print("  local   - Gerar .env para desenvolvimento local")
        print("  vps     - Gerar .env para producao em VPS com Docker (interativo)")
        print("  initdb  - Inicializar banco de dados e criar usuario admin")
        print()
        print("Fluxo completo para VPS:")
        print("  1. python setup.py vps           # Gera configs (interativo)")
        print("  2. docker compose -f docker-compose.prod.yml build --no-cache")
        print("  3. docker compose -f docker-compose.prod.yml up -d")
        print("  4. docker compose -f docker-compose.prod.yml exec api python -m app.db.init_db")
        print("  5. docker compose -f docker-compose.prod.yml exec api python -m app.db.init_roles")
        print("  6. Acessar o frontend e configurar tudo pela interface!")
        print()
        print("Guia completo: DEPLOY_VPS.md")
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
        print("[1/2] Configuracao interativa para producao...")
        secret, db_pass, redis_pass = create_env_vps(backend_dir)

        print("\n[2/2] Verificando Docker...")
        has_docker = check_docker() and check_docker_compose()
        if has_docker:
            print("  [OK] Docker encontrado")
        else:
            print("  [!] Docker nao encontrado")
            print("  Instale: curl -fsSL https://get.docker.com | sudo sh")

        print(f"\n{'='*60}")
        print("  Proximos passos:")
        print(f"{'='*60}\n")

        print("  1. Construir e subir os containers:")
        print("     docker compose -f docker-compose.prod.yml build --no-cache")
        print("     docker compose -f docker-compose.prod.yml up -d\n")

        print("  2. Inicializar o banco de dados:")
        print("     docker compose -f docker-compose.prod.yml exec api python -m app.db.init_db")
        print("     docker compose -f docker-compose.prod.yml exec api python -m app.db.init_roles\n")

        print("  3. Configurar Nginx e SSL (veja DEPLOY_VPS.md secao 10)\n")

        print("  4. Acessar o frontend e configurar TUDO pela interface:")
        print("     - IA & Embeddings (modo, modelo, API key)")
        print("     - LLM & Chat (modelo, temperatura)")
        print("     - Busca (pesos, thresholds)")
        print("     - OCR, Storage, Seguranca, Custos...")
        print("     Ir em: Configuracoes do Sistema\n")

        print("  5. Login inicial:")
        print("     Email: admin@analisador.com")
        print("     Senha: admin123")
        print("     ** TROQUE A SENHA NO PRIMEIRO LOGIN! **\n")

        print("  Guia completo: DEPLOY_VPS.md")

    elif mode == "initdb":
        init_database(backend_dir)

    print(f"\n{'='*60}")
    print("  Setup concluido!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
