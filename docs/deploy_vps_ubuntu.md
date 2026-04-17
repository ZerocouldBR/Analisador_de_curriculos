# Guia Completo de Deploy - VPS Ubuntu 22.04 (Hostinger)

## Analisador de Curriculos - Sistema de RH com IA

---

## Indice

1. [Visao Geral da Arquitetura](#1-visao-geral-da-arquitetura)
2. [Requisitos Minimos da VPS](#2-requisitos-minimos-da-vps)
3. [Acesso Inicial a VPS](#3-acesso-inicial-a-vps)
4. [Preparacao do Servidor](#4-preparacao-do-servidor)
5. [Instalacao do Docker e Docker Compose](#5-instalacao-do-docker-e-docker-compose)
6. [Instalacao do Tesseract OCR](#6-instalacao-do-tesseract-ocr)
7. [Clone do Repositorio](#7-clone-do-repositorio)
8. [Configuracao das Variaveis de Ambiente](#8-configuracao-das-variaveis-de-ambiente)
9. [Configuracao do Docker Compose para Producao](#9-configuracao-do-docker-compose-para-producao)
10. [Configuracao do Nginx como Reverse Proxy](#10-configuracao-do-nginx-como-reverse-proxy)
11. [SSL/TLS com Certbot (Let's Encrypt)](#11-ssltls-com-certbot-lets-encrypt)
12. [Build e Deploy da Aplicacao](#12-build-e-deploy-da-aplicacao)
13. [Inicializacao do Banco de Dados](#13-inicializacao-do-banco-de-dados)
14. [Configuracao do Firewall (UFW)](#14-configuracao-do-firewall-ufw)
15. [Monitoramento com Prometheus e Grafana](#15-monitoramento-com-prometheus-e-grafana)
16. [Backups Automatizados](#16-backups-automatizados)
17. [Atualizacoes e Manutencao](#17-atualizacoes-e-manutencao)
18. [Troubleshooting](#18-troubleshooting)
19. [Checklist de Seguranca para Producao](#19-checklist-de-seguranca-para-producao)
20. [Referencia de Portas e Servicos](#20-referencia-de-portas-e-servicos)

---

## 1. Visao Geral da Arquitetura

O sistema e composto por **8 servicos** orquestrados via Docker Compose:

```
Internet
   |
   v
[Nginx Reverse Proxy] (porta 80/443)
   |
   +---> [Frontend React] (porta 3000) - Interface do usuario
   |
   +---> [Backend FastAPI] (porta 8000) - API REST + WebSocket
   |        |
   |        +---> [PostgreSQL 16 + pgvector] (porta 5432) - Banco principal + vetorial
   |        |
   |        +---> [Redis 7] (porta 6379) - Cache + Message Broker
   |        |
   |        +---> [Celery Worker] - Processamento assincrono de curriculos
   |
   +---> [Flower] (porta 5555) - Monitoramento de tasks Celery
   |
   +---> [Prometheus] (porta 9090) - Coleta de metricas
   |
   +---> [Grafana] (porta 3001) - Dashboards de monitoramento
```

### Tecnologias Principais

| Componente | Tecnologia | Versao |
|---|---|---|
| Backend API | FastAPI (Python) | 0.115.0 |
| Frontend | React + TypeScript | 18.2.0 |
| Banco de Dados | PostgreSQL + pgvector | 16 |
| Cache/Broker | Redis | 7 |
| Task Queue | Celery | 5.3.4 |
| OCR | Tesseract | 4.x/5.x |
| IA/Embeddings | OpenAI API | GPT-4 Turbo |
| Embeddings Local | sentence-transformers | 2.2.0+ |
| Monitoramento | Prometheus + Grafana | latest |
| Reverse Proxy | Nginx | latest |
| SSL | Let's Encrypt (Certbot) | latest |

### Funcionalidades do Sistema

- **Upload e analise de curriculos** (PDF, DOCX, imagens com OCR)
- **Busca semantica hibrida** (vetorial + full-text + filtros + dominio)
- **Chat com IA** para analise de candidatos (OpenAI GPT-4)
- **Job Matching** - comparacao candidato vs vaga
- **Multi-tenant** - isolamento por empresa
- **RBAC** - controle de acesso por roles (admin, recruiter, viewer)
- **LinkedIn Integration** - enriquecimento de perfis
- **LGPD Compliance** - criptografia PII, audit logs, consentimento
- **WebSocket** - atualizacoes em tempo real
- **Monitoramento** - Prometheus + Grafana dashboards

---

## 2. Requisitos Minimos da VPS

### Plano Recomendado na Hostinger

| Recurso | Minimo | Recomendado |
|---|---|---|
| vCPU | 2 cores | 4 cores |
| RAM | 4 GB | 8 GB |
| SSD | 50 GB | 100 GB |
| Banda | 4 TB | 8 TB |
| SO | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |

> **Nota:** O sentence-transformers (embeddings local) consome ~1-2 GB de RAM.
> Se usar apenas OpenAI API para embeddings, 4 GB de RAM e suficiente.
> Com embeddings locais, recomenda-se 8 GB.

### Dominio e DNS

- Tenha um dominio apontando para o IP da VPS (ex: `curriculos.suaempresa.com.br`)
- Configure o DNS tipo A apontando para o IP da VPS na Hostinger
- Aguarde a propagacao DNS (pode levar ate 24h)

---

## 3. Acesso Inicial a VPS

### 3.1 Conectar via SSH

Apos criar a VPS na Hostinger, acesse via SSH:

```bash
ssh root@SEU_IP_DA_VPS
```

### 3.2 Criar usuario de deploy (nao usar root em producao)

```bash
# Criar usuario
adduser deploy

# Dar permissoes sudo
usermod -aG sudo deploy

# Configurar SSH key (no seu computador local)
# ssh-keygen -t ed25519 -C "deploy@curriculos"

# Copiar chave publica para o servidor
# ssh-copy-id deploy@SEU_IP_DA_VPS

# Testar acesso com o novo usuario
su - deploy
```

### 3.3 Desabilitar login root via SSH (recomendado)

```bash
sudo nano /etc/ssh/sshd_config
```

Altere:
```
PermitRootLogin no
PasswordAuthentication no  # Apenas se ja configurou SSH key
```

```bash
sudo systemctl restart sshd
```

---

## 4. Preparacao do Servidor

### 4.1 Atualizar o sistema

```bash
sudo apt update && sudo apt upgrade -y
```

### 4.2 Instalar dependencias basicas

```bash
sudo apt install -y \
    curl \
    wget \
    git \
    htop \
    nano \
    unzip \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release \
    fail2ban \
    ufw
```

### 4.3 Configurar timezone (Brasil)

```bash
sudo timedatectl set-timezone America/Sao_Paulo
timedatectl
```

### 4.4 Configurar swap (importante para VPS com pouca RAM)

```bash
# Verificar se ja existe swap
sudo swapon --show

# Criar swap de 4 GB
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Tornar permanente
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Ajustar swappiness (usar swap apenas quando necessario)
sudo sysctl vm.swappiness=10
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
```

---

## 5. Instalacao do Docker e Docker Compose

### 5.1 Instalar Docker Engine

```bash
# Remover versoes antigas
sudo apt remove -y docker docker-engine docker.io containerd runc 2>/dev/null

# Adicionar repositorio oficial do Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Instalar Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### 5.2 Configurar Docker para o usuario deploy

```bash
# Adicionar usuario ao grupo docker
sudo usermod -aG docker deploy

# Aplicar grupo (relogar ou executar)
newgrp docker

# Verificar instalacao
docker --version
docker compose version
```

### 5.3 Configurar Docker para iniciar no boot

```bash
sudo systemctl enable docker
sudo systemctl start docker
```

---

## 6. Instalacao do Tesseract OCR

O Tesseract e necessario **dentro do container Docker** para OCR de curriculos em imagem/PDF escaneado. O Dockerfile do backend ja deve incluir a instalacao, mas caso precise instalar no host tambem:

```bash
# Instalar Tesseract com suporte a portugues e ingles
sudo apt install -y tesseract-ocr tesseract-ocr-por tesseract-ocr-eng

# Verificar instalacao
tesseract --version
tesseract --list-langs
```

> **Importante:** Certifique-se de que o Dockerfile do backend inclui o Tesseract.
> Veja a secao 9 para o Dockerfile de producao atualizado.

---

## 7. Clone do Repositorio

```bash
# Logar como usuario deploy
su - deploy

# Criar diretorio da aplicacao
sudo mkdir -p /opt/analisador-curriculos
sudo chown deploy:deploy /opt/analisador-curriculos

# Clonar o repositorio
cd /opt/analisador-curriculos
git clone https://github.com/ZerocouldBR/Analisador_de_curriculos.git .
```

---

## 8. Configuracao das Variaveis de Ambiente

### 8.1 Criar arquivo .env do backend

```bash
cp backend/.env.example backend/.env
nano backend/.env
```

### 8.2 Conteudo completo do .env para producao

```env
# ================================================================
# APLICACAO
# ================================================================
APP_VERSION=0.3.0
LOG_LEVEL=WARNING
DEBUG=false

# ================================================================
# BANCO DE DADOS POSTGRESQL
# ================================================================
# Host 'db' refere-se ao container Docker do PostgreSQL
DATABASE_URL=postgresql+psycopg://analisador:SUA_SENHA_FORTE_DB@db:5432/analisador_curriculos

# Pool de conexoes
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
DATABASE_POOL_TIMEOUT=30

# ================================================================
# REDIS (Cache e Message Broker)
# ================================================================
REDIS_URL=redis://redis:6379/0

# ================================================================
# SEGURANCA E AUTENTICACAO JWT
# ================================================================
# OBRIGATORIO: Gere uma chave secreta forte
# Gerar com: python3 -c "import secrets; print(secrets.token_urlsafe(64))"
SECRET_KEY=GERE_UMA_CHAVE_SECRETA_FORTE_AQUI

ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

# ================================================================
# OPENAI (Embeddings e Chat LLM)
# ================================================================
# Obtenha sua chave em: https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-sua-chave-openai-aqui

# Modelo do chat (gpt-4o recomendado)
CHAT_MODEL=gpt-4o

# Modelo de embeddings
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536

# ================================================================
# MODO DE EMBEDDINGS
# ================================================================
# "api" = OpenAI API (requer OPENAI_API_KEY)
# "code" = Local via sentence-transformers (sem custo, mais lento)
EMBEDDING_MODE=api

# Se usar modo "code" (local):
# EMBEDDING_LOCAL_MODEL=all-MiniLM-L6-v2
# EMBEDDING_LOCAL_DIMENSIONS=384
# EMBEDDING_LOCAL_DEVICE=cpu

# ================================================================
# BANCO DE DADOS VETORIAL
# ================================================================
# Opcoes: pgvector (padrao), supabase, qdrant
VECTOR_DB_PROVIDER=pgvector

# Configuracoes pgvector (usa mesmo PostgreSQL)
PGVECTOR_HNSW_M=16
PGVECTOR_HNSW_EF_CONSTRUCTION=64
PGVECTOR_HNSW_EF_SEARCH=100
PGVECTOR_DISTANCE_METRIC=cosine

# ================================================================
# CORS (origens permitidas)
# ================================================================
# Ajuste para seu dominio
CORS_ORIGINS=["https://curriculos.seudominio.com.br","https://www.curriculos.seudominio.com.br"]

# ================================================================
# UPLOAD / STORAGE
# ================================================================
MAX_UPLOAD_SIZE_MB=20
STORAGE_BACKEND=local
STORAGE_PATH=./uploads

# ================================================================
# CELERY / TASK QUEUE
# ================================================================
CELERY_RESULT_EXPIRES=3600
CELERY_TASK_TIME_LIMIT=300
CELERY_TASK_SOFT_TIME_LIMIT=240
CELERY_WORKER_CONCURRENCY=4

# ================================================================
# OCR (Tesseract)
# ================================================================
OCR_LANGUAGES=por+eng
OCR_MIN_CONFIDENCE=30.0

# ================================================================
# MULTI-TENANT
# ================================================================
MULTI_TENANT_ENABLED=true
DEFAULT_COMPANY_NAME=Minha Empresa

# ================================================================
# PII / CRIPTOGRAFIA (LGPD)
# ================================================================
ENABLE_PII_ENCRYPTION=true

# ================================================================
# LLM CONFIGURACOES
# ================================================================
LLM_MAX_RETRIES=5
LLM_MAX_TOKENS=4096
LLM_TEMPERATURE=0.7
CHAT_TEMPERATURE=0.5
CHAT_MAX_TOKENS=4096

# ================================================================
# RATE LIMITING
# ================================================================
RATE_LIMIT_PER_MINUTE=60

# ================================================================
# PRECIFICACAO IA (opcional)
# ================================================================
AI_PRICING_ENABLED=true
AI_CURRENCY=BRL
AI_CURRENCY_EXCHANGE_RATE=5.0
```

### 8.3 Gerar chave secreta (SECRET_KEY)

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

Copie o resultado e cole no `SECRET_KEY` do `.env`.

### 8.4 Proteger o arquivo .env

```bash
chmod 600 backend/.env
```

---

## 9. Configuracao do Docker Compose para Producao

### 9.1 Criar docker-compose.prod.yml

Crie um arquivo de producao que sobrescreve o de desenvolvimento:

```bash
nano docker-compose.prod.yml
```

```yaml
services:
  # PostgreSQL Database with pgvector extension
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: analisador_curriculos
      POSTGRES_USER: analisador
      POSTGRES_PASSWORD: ${DB_PASSWORD:-SUA_SENHA_FORTE_DB}
    ports:
      - "127.0.0.1:5432:5432"  # Apenas localhost
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U analisador"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 1G

  # Redis Cache & Message Broker
  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD:-redis_senha_forte} --maxmemory 256mb --maxmemory-policy allkeys-lru
    ports:
      - "127.0.0.1:6379:6379"  # Apenas localhost
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD:-redis_senha_forte}", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M

  # FastAPI Backend
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    env_file:
      - ./backend/.env
    ports:
      - "127.0.0.1:8000:8000"  # Apenas localhost (Nginx faz proxy)
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - uploads_data:/app/uploads
      - logos_data:/app/uploads/logos
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 2G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Celery Worker
  celery-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    command: celery -A app.core.celery_app worker --loglevel=warning --queues=documents,search --concurrency=4
    env_file:
      - ./backend/.env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - uploads_data:/app/uploads
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 2G

  # Flower - Celery Monitoring (acesso restrito via Nginx)
  flower:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    command: celery -A app.core.celery_app flower --port=5555 --basic-auth=${FLOWER_USER:-admin}:${FLOWER_PASSWORD:-flower_senha_forte}
    env_file:
      - ./backend/.env
    ports:
      - "127.0.0.1:5555:5555"
    depends_on:
      - redis
      - celery-worker
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 256M

  # Prometheus - Metrics Collection
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "127.0.0.1:9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
      - '--web.console.libraries=/usr/share/prometheus/console_libraries'
      - '--web.console.templates=/usr/share/prometheus/consoles'
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M

  # Grafana - Monitoring Dashboards
  grafana:
    image: grafana/grafana:latest
    ports:
      - "127.0.0.1:3001:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=${GRAFANA_USER:-admin}
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-grafana_senha_forte}
      - GF_USERS_ALLOW_SIGN_UP=false
      - GF_SERVER_ROOT_URL=https://curriculos.seudominio.com.br/grafana/
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources:ro
    depends_on:
      - prometheus
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 256M

  # React Frontend (build de producao servido por Nginx)
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod
      args:
        - REACT_APP_API_URL=https://curriculos.seudominio.com.br
        - REACT_APP_WS_URL=wss://curriculos.seudominio.com.br
    ports:
      - "127.0.0.1:3000:80"
    depends_on:
      - api
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 128M

volumes:
  postgres_data:
  redis_data:
  prometheus_data:
  grafana_data:
  uploads_data:
  logos_data:
```

### 9.2 Criar Dockerfile de producao do Backend

```bash
nano backend/Dockerfile.prod
```

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias do sistema (Tesseract OCR + OpenCV)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-por \
    tesseract-ocr-eng \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copiar codigo da aplicacao
COPY app ./app

# Criar diretorio de uploads
RUN mkdir -p /app/uploads/logos

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Iniciar com Uvicorn (producao: workers = 2 * CPU + 1)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--log-level", "warning"]
```

### 9.3 Criar Dockerfile de producao do Frontend

```bash
nano frontend/Dockerfile.prod
```

```dockerfile
# Stage 1: Build
FROM node:18-alpine AS builder

WORKDIR /app

# Argumentos de build (URLs da API)
ARG REACT_APP_API_URL=http://localhost:8000
ARG REACT_APP_WS_URL=ws://localhost:8000

ENV REACT_APP_API_URL=$REACT_APP_API_URL
ENV REACT_APP_WS_URL=$REACT_APP_WS_URL

# Instalar dependencias
COPY package*.json ./
RUN npm ci --production=false

# Copiar codigo e fazer build
COPY . .
RUN npm run build

# Stage 2: Servir com Nginx
FROM nginx:alpine

# Copiar build do React
COPY --from=builder /app/build /usr/share/nginx/html

# Configuracao Nginx para SPA (React Router)
RUN cat > /etc/nginx/conf.d/default.conf << 'EOF'
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    # Compressao gzip
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript image/svg+xml;

    # Cache para assets estaticos
    location /static/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # SPA fallback - todas as rotas vao para index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Negar acesso a arquivos ocultos
    location ~ /\. {
        deny all;
    }
}
EOF

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s \
    CMD wget --no-verbose --tries=1 --spider http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
```

---

## 10. Configuracao do Nginx como Reverse Proxy

O Nginx no **host** (fora do Docker) atua como reverse proxy, roteando trafego para os containers.

### 10.1 Instalar Nginx

```bash
sudo apt install -y nginx
sudo systemctl enable nginx
```

### 10.2 Criar configuracao do site

```bash
sudo nano /etc/nginx/sites-available/analisador-curriculos
```

```nginx
# Rate limiting
limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;
limit_req_zone $binary_remote_addr zone=upload:10m rate=5r/s;

# Upstream servers
upstream frontend {
    server 127.0.0.1:3000;
}

upstream backend {
    server 127.0.0.1:8000;
}

upstream flower {
    server 127.0.0.1:5555;
}

upstream grafana {
    server 127.0.0.1:3001;
}

# Redirecionar HTTP para HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name curriculos.seudominio.com.br;

    # Excecao para verificacao do Certbot
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS Server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name curriculos.seudominio.com.br;

    # SSL sera configurado pelo Certbot (secao 11)
    # ssl_certificate /etc/letsencrypt/live/curriculos.seudominio.com.br/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/curriculos.seudominio.com.br/privkey.pem;
    # include /etc/letsencrypt/options-ssl-nginx.conf;
    # ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Seguranca headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Tamanho maximo de upload (curriculos)
    client_max_body_size 25M;

    # Timeout para processamento de curriculos
    proxy_read_timeout 300s;
    proxy_connect_timeout 75s;
    proxy_send_timeout 300s;

    # Frontend React (rota principal)
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Backend API
    location /api/ {
        limit_req zone=api burst=20 nodelay;

        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Upload de curriculos (rate limit mais restritivo)
    location /api/v1/documents/upload {
        limit_req zone=upload burst=3 nodelay;

        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeout maior para upload + processamento
        proxy_read_timeout 600s;
    }

    # WebSocket
    location /api/v1/ws {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;  # 24h para WebSocket
    }

    # Metricas Prometheus (acesso restrito)
    location /metrics {
        proxy_pass http://backend/metrics;
        # Restringir acesso
        allow 127.0.0.1;
        deny all;
    }

    # Flower - Monitoramento Celery (protegido por autenticacao)
    location /flower/ {
        proxy_pass http://flower/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # Restringir por IP ou usar autenticacao basica
        # allow SEU_IP_FIXO;
        # deny all;
    }

    # Grafana
    location /grafana/ {
        proxy_pass http://grafana/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Swagger/OpenAPI Docs
    location /docs {
        proxy_pass http://backend/docs;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /openapi.json {
        proxy_pass http://backend/openapi.json;
        proxy_set_header Host $host;
    }

    # Bloquear acesso direto ao Prometheus
    location /prometheus/ {
        allow 127.0.0.1;
        deny all;
    }
}
```

### 10.3 Ativar o site

```bash
# Ativar configuracao
sudo ln -s /etc/nginx/sites-available/analisador-curriculos /etc/nginx/sites-enabled/

# Remover site padrao
sudo rm -f /etc/nginx/sites-enabled/default

# Testar configuracao
sudo nginx -t

# Recarregar Nginx
sudo systemctl reload nginx
```

---

## 11. SSL/TLS com Certbot (Let's Encrypt)

### 11.1 Instalar Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 11.2 Obter certificado SSL

```bash
# Criar diretorio para challenge
sudo mkdir -p /var/www/certbot

# Obter certificado (substitua pelo seu dominio e email)
sudo certbot --nginx -d curriculos.seudominio.com.br --email seu@email.com --agree-tos --no-eff-email
```

O Certbot vai automaticamente:
- Obter o certificado SSL
- Configurar o Nginx com SSL
- Descomentar as linhas SSL no arquivo de configuracao

### 11.3 Renovacao automatica

```bash
# Testar renovacao
sudo certbot renew --dry-run

# O Certbot ja cria um timer para renovacao automatica
# Verificar:
sudo systemctl list-timers | grep certbot
```

### 11.4 Apos obter o SSL - Atualizar variaveis

Atualize o `CORS_ORIGINS` no `backend/.env`:

```env
CORS_ORIGINS=["https://curriculos.seudominio.com.br"]
```

E reconstrua o frontend com as URLs HTTPS:

```bash
cd /opt/analisador-curriculos

docker compose -f docker-compose.prod.yml build frontend \
  --build-arg REACT_APP_API_URL=https://curriculos.seudominio.com.br \
  --build-arg REACT_APP_WS_URL=wss://curriculos.seudominio.com.br

docker compose -f docker-compose.prod.yml up -d frontend
```

---

## 12. Build e Deploy da Aplicacao

### 12.1 Build dos containers

```bash
cd /opt/analisador-curriculos

# Build de todos os servicos
docker compose -f docker-compose.prod.yml build
```

> **Nota:** O primeiro build pode demorar 10-15 minutos (download de imagens + pip install + npm install).

### 12.2 Subir os servicos

```bash
# Subir em modo detached (background)
docker compose -f docker-compose.prod.yml up -d

# Verificar status dos containers
docker compose -f docker-compose.prod.yml ps

# Ver logs de todos os servicos
docker compose -f docker-compose.prod.yml logs -f

# Ver logs de um servico especifico
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f celery-worker
```

### 12.3 Verificar se tudo esta rodando

```bash
# Verificar containers
docker compose -f docker-compose.prod.yml ps

# Output esperado: todos com status "Up" ou "healthy"
# NAME                  STATUS
# db                    Up (healthy)
# redis                 Up (healthy)
# api                   Up (healthy)
# celery-worker         Up
# flower                Up
# prometheus            Up
# grafana               Up
# frontend              Up (healthy)
```

### 12.4 Testar endpoints

```bash
# Health check do backend
curl http://localhost:8000/api/health

# Frontend
curl -I http://localhost:3000

# API Docs (Swagger)
curl -I http://localhost:8000/docs
```

---

## 13. Inicializacao do Banco de Dados

### 13.1 Criar tabelas e indices

```bash
# Executar init_db dentro do container da API
docker compose -f docker-compose.prod.yml exec api python -m app.db.init_db
```

Output esperado:
```
Initializing database...
  Provider: pgvector
  Embedding model: text-embedding-3-small
  Embedding dimensions: 1536
  pgvector extension verified
  Tables created
  HNSW index created (m=16, ef=64, metric=cosine)
  FTS index created (language=portuguese)
  JSON metadata index created
  Database initialized successfully
```

### 13.2 Criar roles e superusuario

```bash
docker compose -f docker-compose.prod.yml exec api python -m app.db.init_roles
```

Output esperado:
```
Inicializando roles padrao...
  Role 'admin' criado
  Role 'recruiter' criado
  Role 'viewer' criado

Criando superuser padrao...
  Superuser 'admin@analisador.com' criado com sucesso

IMPORTANTE: Altere a senha padrao do superuser em producao!
  Email: admin@analisador.com
  Senha: admin123
```

### 13.3 IMPORTANTE: Alterar senha do admin

Acesse o sistema e altere imediatamente a senha padrao do superusuario:

1. Acesse `https://curriculos.seudominio.com.br/login`
2. Login com: `admin@analisador.com` / `admin123`
3. Va em **Settings** e altere a senha

Ou via API:

```bash
# Obter token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -F "username=admin@analisador.com" \
  -F "password=admin123" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Alterar senha
curl -X POST http://localhost:8000/api/v1/auth/change-password \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"old_password":"admin123","new_password":"SUA_NOVA_SENHA_FORTE"}'
```

---

## 14. Configuracao do Firewall (UFW)

### 14.1 Configurar regras

```bash
# Resetar regras (cuidado em producao)
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Permitir SSH
sudo ufw allow 22/tcp

# Permitir HTTP e HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# NÃO abrir portas dos servicos internos (5432, 6379, 8000, 3000, etc.)
# O Nginx faz proxy para eles via localhost

# Ativar firewall
sudo ufw enable

# Verificar status
sudo ufw status verbose
```

### 14.2 Configurar Fail2Ban

```bash
sudo nano /etc/fail2ban/jail.local
```

```ini
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = ssh
logpath = %(sshd_log)s
maxretry = 3

[nginx-http-auth]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log

[nginx-limit-req]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log
maxretry = 10
```

```bash
sudo systemctl enable fail2ban
sudo systemctl restart fail2ban
```

---

## 15. Monitoramento com Prometheus e Grafana

### 15.1 Acessar Grafana

Apos o deploy, acesse:
- URL: `https://curriculos.seudominio.com.br/grafana/`
- Usuario: valor de `GRAFANA_USER` (padrao: admin)
- Senha: valor de `GRAFANA_PASSWORD` (padrao: grafana_senha_forte)

### 15.2 Dashboard disponivel

O sistema inclui um dashboard pre-configurado em `monitoring/grafana/dashboards/analisador-dashboard.json` com:

- **Metricas da API:** Requests/segundo, latencia (p95, p99), status codes
- **Celery Workers:** Tasks em execucao, concluidas, falhadas
- **PostgreSQL:** Conexoes ativas, queries
- **Redis:** Uso de memoria, hits/misses

### 15.3 Metricas do Prometheus

Prometheus coleta metricas de:
- `api:8000` - FastAPI (via prometheus-fastapi-instrumentator)
- `flower:5555` - Celery tasks
- `redis:6379` - Redis stats
- `db:5432` - PostgreSQL stats

Acesse Prometheus em: `http://127.0.0.1:9090` (apenas localhost)

### 15.4 Alertas (opcional)

Para configurar alertas, adicione regras no Prometheus:

```bash
nano monitoring/prometheus_alerts.yml
```

```yaml
groups:
  - name: analisador
    rules:
      - alert: APIDown
        expr: up{job="fastapi"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "API Backend esta fora do ar"

      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{job="fastapi"}[5m])) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Latencia P95 acima de 5 segundos"

      - alert: CeleryWorkerDown
        expr: up{job="celery"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Celery Worker esta fora do ar"
```

---

## 16. Backups Automatizados

### 16.1 Script de backup do PostgreSQL

```bash
sudo mkdir -p /opt/backups/postgres
sudo chown deploy:deploy /opt/backups/postgres

nano /opt/analisador-curriculos/scripts/backup.sh
```

```bash
#!/bin/bash
# Backup automatizado do Analisador de Curriculos

set -euo pipefail

# Configuracoes
BACKUP_DIR="/opt/backups/postgres"
RETENTION_DAYS=30
DATE=$(date +%Y%m%d_%H%M%S)
COMPOSE_FILE="/opt/analisador-curriculos/docker-compose.prod.yml"

echo "[$(date)] Iniciando backup..."

# Backup do PostgreSQL
docker compose -f $COMPOSE_FILE exec -T db \
    pg_dump -U analisador -d analisador_curriculos \
    --format=custom --compress=9 \
    > "$BACKUP_DIR/db_backup_$DATE.dump"

# Backup dos uploads (curriculos)
tar -czf "$BACKUP_DIR/uploads_backup_$DATE.tar.gz" \
    -C /opt/analisador-curriculos/backend uploads/ 2>/dev/null || true

# Backup do .env (configuracoes)
cp /opt/analisador-curriculos/backend/.env \
    "$BACKUP_DIR/env_backup_$DATE.env"

# Remover backups antigos
find "$BACKUP_DIR" -name "*.dump" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "*.env" -mtime +$RETENTION_DAYS -delete

# Tamanho total dos backups
SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
echo "[$(date)] Backup concluido. Tamanho total: $SIZE"
echo "[$(date)] Arquivos:"
ls -lh "$BACKUP_DIR"/db_backup_$DATE.dump
ls -lh "$BACKUP_DIR"/uploads_backup_$DATE.tar.gz
```

```bash
chmod +x /opt/analisador-curriculos/scripts/backup.sh
```

### 16.2 Agendar backup diario (cron)

```bash
crontab -e
```

Adicionar:
```cron
# Backup diario as 3h da manha
0 3 * * * /opt/analisador-curriculos/scripts/backup.sh >> /opt/backups/postgres/backup.log 2>&1
```

### 16.3 Restaurar backup

```bash
# Restaurar banco de dados
docker compose -f docker-compose.prod.yml exec -T db \
    pg_restore -U analisador -d analisador_curriculos \
    --clean --if-exists \
    < /opt/backups/postgres/db_backup_YYYYMMDD_HHMMSS.dump

# Restaurar uploads
tar -xzf /opt/backups/postgres/uploads_backup_YYYYMMDD_HHMMSS.tar.gz \
    -C /opt/analisador-curriculos/backend/
```

---

## 17. Atualizacoes e Manutencao

### 17.1 Atualizar a aplicacao

```bash
cd /opt/analisador-curriculos

# 1. Fazer backup antes de atualizar
./scripts/backup.sh

# 2. Puxar atualizacoes do repositorio
git pull origin main

# 3. Rebuild dos containers
docker compose -f docker-compose.prod.yml build

# 4. Reiniciar servicos (com zero downtime)
docker compose -f docker-compose.prod.yml up -d

# 5. Verificar se migracao do banco e necessaria
docker compose -f docker-compose.prod.yml exec api python -m app.db.init_db

# 6. Verificar logs
docker compose -f docker-compose.prod.yml logs -f --tail=50
```

### 17.2 Reiniciar servicos individuais

```bash
# Reiniciar apenas o backend
docker compose -f docker-compose.prod.yml restart api

# Reiniciar worker do Celery
docker compose -f docker-compose.prod.yml restart celery-worker

# Reiniciar frontend
docker compose -f docker-compose.prod.yml restart frontend
```

### 17.3 Escalar workers do Celery

```bash
# Aumentar para 2 workers
docker compose -f docker-compose.prod.yml up -d --scale celery-worker=2
```

### 17.4 Limpar recursos Docker

```bash
# Remover imagens nao utilizadas
docker image prune -a --filter "until=168h"

# Remover volumes orfaos (CUIDADO: nao remover volumes de dados!)
docker volume prune --filter "label!=com.docker.compose.project"

# Verificar uso de disco
docker system df
```

### 17.5 Monitorar uso de recursos

```bash
# Ver recursos por container
docker stats

# Ver logs em tempo real
docker compose -f docker-compose.prod.yml logs -f --tail=100

# Ver uso de disco dos volumes
docker system df -v
```

---

## 18. Troubleshooting

### 18.1 Container nao inicia

```bash
# Ver logs detalhados
docker compose -f docker-compose.prod.yml logs api
docker compose -f docker-compose.prod.yml logs celery-worker
docker compose -f docker-compose.prod.yml logs db

# Verificar se portas estao em uso
sudo netstat -tlnp | grep -E "3000|8000|5432|6379"

# Reconstruir container com problema
docker compose -f docker-compose.prod.yml up -d --build api
```

### 18.2 Erro de conexao com banco

```bash
# Verificar se o PostgreSQL esta saudavel
docker compose -f docker-compose.prod.yml exec db pg_isready -U analisador

# Verificar logs do banco
docker compose -f docker-compose.prod.yml logs db

# Testar conexao manualmente
docker compose -f docker-compose.prod.yml exec db psql -U analisador -d analisador_curriculos -c "SELECT 1;"

# Verificar extensao pgvector
docker compose -f docker-compose.prod.yml exec db psql -U analisador -d analisador_curriculos -c "SELECT extname FROM pg_extension;"
```

### 18.3 Celery nao processa documentos

```bash
# Verificar se o worker esta rodando
docker compose -f docker-compose.prod.yml exec celery-worker celery -A app.core.celery_app inspect active

# Verificar filas
docker compose -f docker-compose.prod.yml exec celery-worker celery -A app.core.celery_app inspect reserved

# Verificar conexao com Redis
docker compose -f docker-compose.prod.yml exec redis redis-cli ping

# Reiniciar worker
docker compose -f docker-compose.prod.yml restart celery-worker
```

### 18.4 OCR nao funciona

```bash
# Verificar Tesseract dentro do container
docker compose -f docker-compose.prod.yml exec api tesseract --version
docker compose -f docker-compose.prod.yml exec api tesseract --list-langs
docker compose -f docker-compose.prod.yml exec celery-worker tesseract --version
```

### 18.5 Embeddings/OpenAI nao funciona

```bash
# Verificar chave da OpenAI
docker compose -f docker-compose.prod.yml exec api python -c "
from app.core.config import settings
print(f'API Key: {settings.openai_api_key[:10]}...' if settings.openai_api_key else 'API Key NAO configurada')
print(f'Mode: {settings.embedding_mode.value}')
print(f'Model: {settings.embedding_model}')
"

# Testar conexao com OpenAI
docker compose -f docker-compose.prod.yml exec api python -c "
import openai
client = openai.OpenAI()
response = client.embeddings.create(input='teste', model='text-embedding-3-small')
print(f'Embedding OK - {len(response.data[0].embedding)} dimensions')
"
```

### 18.6 WebSocket nao conecta

```bash
# Verificar se o WebSocket esta acessivel
# Instalar wscat para teste
# npm install -g wscat

# Testar WebSocket (substitua TOKEN pelo JWT valido)
# wscat -c "wss://curriculos.seudominio.com.br/api/v1/ws?token=SEU_JWT_TOKEN"

# Verificar configuracao Nginx
sudo nginx -t
sudo tail -f /var/log/nginx/error.log
```

### 18.7 Frontend nao carrega / erro 502

```bash
# Verificar se o container frontend esta rodando
docker compose -f docker-compose.prod.yml ps frontend

# Ver logs do frontend
docker compose -f docker-compose.prod.yml logs frontend

# Verificar build do React
docker compose -f docker-compose.prod.yml exec frontend ls -la /usr/share/nginx/html/

# Rebuild do frontend com URLs corretas
docker compose -f docker-compose.prod.yml build frontend \
    --build-arg REACT_APP_API_URL=https://curriculos.seudominio.com.br \
    --build-arg REACT_APP_WS_URL=wss://curriculos.seudominio.com.br
docker compose -f docker-compose.prod.yml up -d frontend
```

### 18.8 Memoria insuficiente

```bash
# Verificar uso de memoria
free -h
docker stats --no-stream

# Se necessario, reduzir concurrency do Celery
# No docker-compose.prod.yml, altere --concurrency=4 para --concurrency=2

# Verificar swap
swapon --show

# Limpar cache do sistema
sudo sync && sudo sysctl -w vm.drop_caches=3
```

---

## 19. Checklist de Seguranca para Producao

### Obrigatorio (antes de ir ao ar)

- [ ] **SECRET_KEY** gerado com `secrets.token_urlsafe(64)` (nao usar valor padrao)
- [ ] **Senha do PostgreSQL** alterada (nao usar "analisador")
- [ ] **Senha do admin** alterada (nao usar "admin123")
- [ ] **Senha do Redis** configurada (REDIS_PASSWORD)
- [ ] **Senha do Grafana** alterada (nao usar "admin")
- [ ] **Senha do Flower** configurada (FLOWER_USER/FLOWER_PASSWORD)
- [ ] **CORS_ORIGINS** configurado apenas com seu dominio
- [ ] **SSL/TLS** ativo (HTTPS) com certificado Let's Encrypt
- [ ] **Firewall (UFW)** ativo, apenas portas 22, 80, 443 abertas
- [ ] **Fail2Ban** configurado e ativo
- [ ] **Login root desabilitado** via SSH
- [ ] **Portas internas** (5432, 6379, 8000, 3000) **NÃO expostas** para internet
- [ ] Arquivo `.env` com permissao `600`
- [ ] **LOG_LEVEL=WARNING** em producao (nao INFO ou DEBUG)

### Recomendado

- [ ] SSH apenas via chave publica (sem senha)
- [ ] Backups automatizados configurados (cron)
- [ ] Monitoramento de uptime configurado
- [ ] Limite de upload configurado (`MAX_UPLOAD_SIZE_MB`)
- [ ] Rate limiting ativo no Nginx
- [ ] PII encryption habilitado (`ENABLE_PII_ENCRYPTION=true`)
- [ ] Audit log habilitado para LGPD
- [ ] Atualizar sistema operacional regularmente (`sudo apt update && sudo apt upgrade`)

---

## 20. Referencia de Portas e Servicos

### Portas Internas (apenas localhost via Docker)

| Servico | Porta | Descricao |
|---|---|---|
| PostgreSQL | 5432 | Banco de dados principal + pgvector |
| Redis | 6379 | Cache e message broker |
| FastAPI Backend | 8000 | API REST + WebSocket |
| React Frontend | 3000 | Interface do usuario (Nginx interno) |
| Flower | 5555 | Monitor de tasks Celery |
| Prometheus | 9090 | Coleta de metricas |
| Grafana | 3001 | Dashboards de monitoramento |

### Portas Externas (abertas no firewall)

| Porta | Protocolo | Servico |
|---|---|---|
| 22 | TCP | SSH |
| 80 | TCP | HTTP (redireciona para 443) |
| 443 | TCP | HTTPS (Nginx reverse proxy) |

### Rotas da API (principais)

| Metodo | Rota | Descricao |
|---|---|---|
| GET | `/api/health` | Health check |
| POST | `/api/v1/auth/login` | Login (retorna JWT) |
| POST | `/api/v1/auth/register` | Registrar usuario |
| GET | `/api/v1/auth/me` | Usuario autenticado |
| GET | `/api/v1/candidates/` | Listar candidatos |
| POST | `/api/v1/candidates/` | Criar candidato |
| GET | `/api/v1/candidates/{id}` | Detalhe do candidato |
| PUT | `/api/v1/candidates/{id}` | Atualizar candidato |
| DELETE | `/api/v1/candidates/{id}` | Remover candidato (LGPD) |
| POST | `/api/v1/documents/upload` | Upload de curriculo |
| POST | `/api/v1/documents/{id}/reprocess` | Reprocessar documento |
| POST | `/api/v1/search/semantic` | Busca semantica |
| POST | `/api/v1/search/hybrid` | Busca hibrida |
| GET | `/api/v1/search/candidates/by-skill` | Buscar por skill |
| POST | `/api/v1/search/llm-query` | Query com LLM |
| POST | `/api/v1/search/job-analysis` | Analise de vaga |
| POST | `/api/v1/chat/conversations` | Nova conversa |
| POST | `/api/v1/chat/messages` | Enviar mensagem |
| GET | `/api/v1/chat/conversations` | Listar conversas |
| POST | `/api/v1/linkedin/search` | Buscar no LinkedIn |
| POST | `/api/v1/linkedin/candidates/{id}/enrich` | Enriquecer com LinkedIn |
| GET | `/api/v1/settings/` | Configuracoes do sistema |
| PUT | `/api/v1/settings/{key}` | Atualizar configuracao |
| GET | `/api/v1/companies/me` | Empresa atual |
| GET | `/api/v1/vectordb/health` | Status do vector DB |
| WS | `/api/v1/ws?token=JWT` | WebSocket (tempo real) |
| GET | `/docs` | Swagger/OpenAPI UI |
| GET | `/metrics` | Prometheus metrics |

### Roles e Permissoes

| Role | Descricao | Permissoes principais |
|---|---|---|
| **admin** | Acesso completo | Tudo, incluindo gerenciar usuarios e empresas |
| **recruiter** | Recrutador | CRUD candidatos/documentos, busca, chat, LinkedIn |
| **viewer** | Visualizador | Apenas leitura de candidatos e documentos |

---

## Apendice A: Comandos Rapidos de Referencia

```bash
# ============================================================
# DEPLOY INICIAL (resumo)
# ============================================================

# 1. Preparar servidor
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl wget git htop nano fail2ban ufw

# 2. Instalar Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker deploy

# 3. Clonar projeto
cd /opt/analisador-curriculos
git clone https://github.com/ZerocouldBR/Analisador_de_curriculos.git .

# 4. Configurar ambiente
cp backend/.env.example backend/.env
nano backend/.env  # Configurar todas as variaveis

# 5. Build e subir
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

# 6. Inicializar banco
docker compose -f docker-compose.prod.yml exec api python -m app.db.init_db
docker compose -f docker-compose.prod.yml exec api python -m app.db.init_roles

# 7. Instalar Nginx + SSL
sudo apt install -y nginx certbot python3-certbot-nginx
sudo certbot --nginx -d curriculos.seudominio.com.br

# 8. Firewall
sudo ufw allow 22/tcp && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp
sudo ufw enable


# ============================================================
# OPERACOES DO DIA A DIA
# ============================================================

# Ver status
docker compose -f docker-compose.prod.yml ps

# Ver logs
docker compose -f docker-compose.prod.yml logs -f --tail=50

# Reiniciar tudo
docker compose -f docker-compose.prod.yml restart

# Atualizar aplicacao
git pull origin main
docker compose -f docker-compose.prod.yml up -d --build

# Backup
./scripts/backup.sh

# Escalar Celery workers
docker compose -f docker-compose.prod.yml up -d --scale celery-worker=3

# Entrar no container da API (debug)
docker compose -f docker-compose.prod.yml exec api bash

# Entrar no PostgreSQL
docker compose -f docker-compose.prod.yml exec db psql -U analisador -d analisador_curriculos

# Entrar no Redis
docker compose -f docker-compose.prod.yml exec redis redis-cli
```

---

## Apendice B: Configuracao para Embeddings Locais (sem OpenAI)

Se voce nao quiser usar a API da OpenAI (custo por token), pode usar embeddings locais com sentence-transformers:

### No `backend/.env`:

```env
# Modo local (sem custo, mais lento)
EMBEDDING_MODE=code
EMBEDDING_LOCAL_MODEL=all-MiniLM-L6-v2
EMBEDDING_LOCAL_DIMENSIONS=384
EMBEDDING_LOCAL_DEVICE=cpu

# Dimensoes do vetor (DEVE mudar para o modelo local)
EMBEDDING_DIMENSIONS=384
```

> **Atencao:** O modelo sentence-transformers ocupa ~500 MB em disco e ~1-2 GB de RAM.
> No primeiro uso, ele sera baixado automaticamente. Isso requer internet e pode demorar.
>
> **O chat com LLM ainda requer OPENAI_API_KEY.** Apenas os embeddings ficam locais.
> Se nao quiser usar OpenAI para nada, desabilite as funcionalidades de chat/LLM.

---

## Apendice C: Estrutura dos Volumes Docker

```
volumes/
  postgres_data/     # Dados do PostgreSQL (CRITICO - fazer backup!)
  redis_data/        # Cache do Redis (pode ser perdido sem problema)
  prometheus_data/   # Metricas historicas
  grafana_data/      # Dashboards e configuracoes do Grafana
  uploads_data/      # Curriculos enviados (CRITICO - fazer backup!)
  logos_data/        # Logos das empresas
```

---

## Apendice D: Variavel de Ambiente - Referencia Completa

| Variavel | Obrigatoria | Default | Descricao |
|---|---|---|---|
| `SECRET_KEY` | Sim | - | Chave secreta JWT (gerar com secrets.token_urlsafe) |
| `DATABASE_URL` | Sim | postgresql+psycopg://...@db:5432/... | URL do PostgreSQL |
| `REDIS_URL` | Sim | redis://redis:6379/0 | URL do Redis |
| `OPENAI_API_KEY` | Nao* | - | Chave da API OpenAI (*obrigatoria se EMBEDDING_MODE=api) |
| `CORS_ORIGINS` | Sim | ["http://localhost:3000"] | Origens CORS permitidas (JSON array) |
| `LOG_LEVEL` | Nao | INFO | Nivel de log (DEBUG, INFO, WARNING, ERROR) |
| `DEBUG` | Nao | false | Modo debug |
| `EMBEDDING_MODE` | Nao | api | Modo embeddings: api ou code |
| `EMBEDDING_MODEL` | Nao | text-embedding-3-small | Modelo de embeddings (API) |
| `EMBEDDING_DIMENSIONS` | Nao | 1536 | Dimensoes do embedding |
| `CHAT_MODEL` | Nao | gpt-4o | Modelo do chat LLM |
| `VECTOR_DB_PROVIDER` | Nao | pgvector | Provedor vetorial: pgvector, supabase, qdrant |
| `MULTI_TENANT_ENABLED` | Nao | true | Isolamento multi-tenant |
| `ENABLE_PII_ENCRYPTION` | Nao | true | Criptografia de dados pessoais |
| `MAX_UPLOAD_SIZE_MB` | Nao | 20 | Tamanho maximo de upload |
| `CELERY_WORKER_CONCURRENCY` | Nao | 4 | Workers simultaneos do Celery |
| `OCR_LANGUAGES` | Nao | por+eng | Idiomas do Tesseract OCR |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Nao | 30 | Validade do token JWT |
| `RATE_LIMIT_PER_MINUTE` | Nao | 60 | Limite de requests por minuto |
| `AI_PRICING_ENABLED` | Nao | true | Calcular custo de uso da IA |
| `AI_CURRENCY` | Nao | USD | Moeda para custos (USD, BRL) |
| `AI_CURRENCY_EXCHANGE_RATE` | Nao | 1.0 | Taxa de cambio (5.0 para BRL) |
