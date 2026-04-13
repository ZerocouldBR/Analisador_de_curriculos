# Guia Completo de Deploy em VPS - Analisador de Curriculos

Guia passo a passo para instalar e configurar o sistema completo em uma VPS (Ubuntu 22.04+).

---

## Indice

1. [Requisitos Minimos](#1-requisitos-minimos)
2. [Preparacao da VPS](#2-preparacao-da-vps)
3. [Instalacao do Docker](#3-instalacao-do-docker)
4. [Clone do Projeto](#4-clone-do-projeto)
5. [Configuracao de Senhas e Segredos](#5-configuracao-de-senhas-e-segredos)
6. [Configuracao do Banco de Dados (PostgreSQL + pgvector)](#6-configuracao-do-banco-de-dados)
7. [Configuracao do Redis](#7-configuracao-do-redis)
8. [Build e Deploy da Aplicacao](#8-build-e-deploy-da-aplicacao)
9. [Inicializacao do Banco de Dados](#9-inicializacao-do-banco-de-dados)
10. [Configuracao do Nginx e SSL](#10-configuracao-do-nginx-e-ssl)
11. [Configuracao pelo Frontend](#11-configuracao-pelo-frontend)
12. [Monitoramento (Prometheus + Grafana)](#12-monitoramento)
13. [Backup Automatizado](#13-backup-automatizado)
14. [Atualizacoes e Manutencao](#14-atualizacoes-e-manutencao)
15. [Troubleshooting](#15-troubleshooting)
16. [Deploy Automatico (Script)](#16-deploy-automatico)
17. [Referencia de API](#17-referencia-de-api)
18. [Historico de Melhorias e Correcoes](#18-historico-de-melhorias-e-correcoes)

---

## 1. Requisitos Minimos

| Recurso | Minimo | Recomendado |
|---------|--------|-------------|
| CPU     | 2 vCPUs | 4 vCPUs |
| RAM     | 4 GB | 8 GB |
| Disco   | 40 GB SSD | 80 GB SSD |
| SO      | Ubuntu 22.04 LTS | Ubuntu 24.04 LTS |
| Rede    | IPv4 publico | IPv4 + dominio configurado |

**Portas necessarias:**
- 22 (SSH)
- 80 (HTTP)
- 443 (HTTPS)

---

## 2. Preparacao da VPS

### 2.1. Conectar via SSH

```bash
ssh root@SEU_IP_DA_VPS
```

### 2.2. Criar usuario de deploy (nao usar root)

```bash
adduser deploy
usermod -aG sudo deploy
```

### 2.3. Configurar chave SSH (recomendado)

No seu computador local:
```bash
ssh-copy-id deploy@SEU_IP_DA_VPS
```

### 2.4. Atualizar o sistema

```bash
sudo apt-get update -y && sudo apt-get upgrade -y
```

### 2.5. Instalar dependencias basicas

```bash
sudo apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    ufw \
    fail2ban \
    unattended-upgrades
```

### 2.6. Configurar firewall

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status
```

### 2.7. Configurar Fail2Ban (protecao contra brute-force)

```bash
sudo tee /etc/fail2ban/jail.local > /dev/null <<'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
EOF

sudo systemctl enable fail2ban
sudo systemctl restart fail2ban
```

---

## 3. Instalacao do Docker

### 3.1. Instalar Docker Engine

```bash
curl -fsSL https://get.docker.com | sudo sh
```

### 3.2. Adicionar usuario ao grupo docker

```bash
sudo usermod -aG docker deploy
# Saia e entre novamente para aplicar:
exit
ssh deploy@SEU_IP_DA_VPS
```

### 3.3. Verificar instalacao

```bash
docker --version
docker compose version
```

Resultado esperado:
```
Docker version 27.x.x
Docker Compose version v2.x.x
```

### 3.4. Configurar Docker para iniciar automaticamente

```bash
sudo systemctl enable docker
sudo systemctl start docker
```

---

## 4. Clone do Projeto

### 4.1. Criar diretorio da aplicacao

```bash
sudo mkdir -p /opt/analisador-curriculos
sudo chown deploy:deploy /opt/analisador-curriculos
cd /opt/analisador-curriculos
```

### 4.2. Clonar o repositorio

```bash
git clone https://github.com/zerocouldbr/analisador_de_curriculos.git .
```

Ou se estiver usando outro metodo (rsync, scp):
```bash
# Do seu computador local:
rsync -avz --exclude='.git' --exclude='node_modules' --exclude='__pycache__' --exclude='.venv' \
    ./ deploy@SEU_IP_DA_VPS:/opt/analisador-curriculos/
```

---

## 5. Configuracao de Senhas e Segredos

### 5.1. Metodo automatico (recomendado)

```bash
cd /opt/analisador-curriculos
python3 setup.py vps
```

Este comando:
- Gera senhas seguras para PostgreSQL, Redis, Grafana, Flower
- Cria `backend/.env` com todas as configuracoes
- Cria `.env` na raiz para o docker-compose.prod.yml
- Exibe as credenciais geradas na tela

**SALVE AS CREDENCIAIS EXIBIDAS EM LOCAL SEGURO!**

### 5.2. Metodo manual

Se preferir configurar manualmente, crie os arquivos:

#### Arquivo `backend/.env`:

```bash
# Gere senhas seguras:
SECRET_KEY=$(openssl rand -hex 32)
DB_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=')
REDIS_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=')

cat > backend/.env <<EOF
# ================================================================
# Analisador de Curriculos - Configuracao de Producao
# ================================================================

# Aplicacao
APP_VERSION=0.3.0
LOG_LEVEL=WARNING
DEBUG=false

# Banco de Dados (container Docker)
DATABASE_URL=postgresql+psycopg://analisador:${DB_PASSWORD}@db:5432/analisador_curriculos

# Redis (container Docker com senha)
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0

# Seguranca JWT
SECRET_KEY=${SECRET_KEY}
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS - ALTERE para seu dominio!
CORS_ORIGINS=["https://SEU_DOMINIO.com.br"]

# Vector DB
VECTOR_DB_PROVIDER=pgvector

# Embeddings
# Modo local (gratis): EMBEDDING_MODE=code
# Modo API (OpenAI, pago): EMBEDDING_MODE=api
EMBEDDING_MODE=code
EMBEDDING_LOCAL_MODEL=all-MiniLM-L6-v2

# OpenAI (necessario apenas se EMBEDDING_MODE=api)
# OPENAI_API_KEY=sk-...

# Upload
MAX_UPLOAD_SIZE_MB=20
STORAGE_BACKEND=local
STORAGE_PATH=/app/uploads

# OCR
OCR_LANGUAGES=por+eng

# LGPD
ENABLE_PII_ENCRYPTION=true
EOF
```

#### Arquivo `.env` (raiz - para docker-compose.prod.yml):

```bash
GRAFANA_PASSWORD=$(openssl rand -base64 16 | tr -d '/+=')
FLOWER_PASSWORD=$(openssl rand -base64 16 | tr -d '/+=')

cat > .env <<EOF
DB_PASSWORD=${DB_PASSWORD}
REDIS_PASSWORD=${REDIS_PASSWORD}
GRAFANA_USER=admin
GRAFANA_PASSWORD=${GRAFANA_PASSWORD}
FLOWER_USER=admin
FLOWER_PASSWORD=${FLOWER_PASSWORD}
FRONTEND_API_URL=https://SEU_DOMINIO.com.br
FRONTEND_WS_URL=wss://SEU_DOMINIO.com.br
EOF
```

### 5.3. Configurar dominio

Edite os arquivos para substituir o dominio:

```bash
# No backend/.env - editar CORS_ORIGINS:
nano backend/.env

# No .env raiz - editar FRONTEND_API_URL e FRONTEND_WS_URL:
nano .env
```

---

## 6. Configuracao do Banco de Dados

O PostgreSQL 16 com extensao pgvector roda como container Docker.

### 6.1. O container e configurado automaticamente pelo docker-compose.prod.yml

Especificacoes:
- **Imagem:** `pgvector/pgvector:pg16`
- **Usuario:** `analisador`
- **Senha:** Gerada automaticamente (variavel `DB_PASSWORD`)
- **Banco:** `analisador_curriculos`
- **Porta interna:** 5432
- **Porta externa:** 127.0.0.1:5432 (apenas acesso local)
- **Memoria maxima:** 1 GB
- **Dados:** Volume Docker `postgres_data` (persistente)

### 6.2. Extensao pgvector

A extensao pgvector e instalada automaticamente no primeiro start.
Ela permite armazenar e buscar vetores de embeddings diretamente no PostgreSQL.

### 6.3. Otimizacoes para producao (opcional)

Para bancos grandes (>100K curriculos), ajuste no PostgreSQL:

```bash
# Criar arquivo de configuracao customizada
mkdir -p /opt/analisador-curriculos/docker/postgres

cat > /opt/analisador-curriculos/docker/postgres/custom.conf <<EOF
# Memoria
shared_buffers = 256MB
effective_cache_size = 768MB
work_mem = 16MB
maintenance_work_mem = 128MB

# Conexoes
max_connections = 100

# WAL
wal_buffers = 16MB

# Performance
random_page_cost = 1.1
effective_io_concurrency = 200
EOF
```

E adicione ao servico `db` no `docker-compose.prod.yml`:
```yaml
volumes:
  - postgres_data:/var/lib/postgresql/data
  - ./docker/postgres/custom.conf:/etc/postgresql/conf.d/custom.conf:ro
command: postgres -c config_file=/etc/postgresql/conf.d/custom.conf
```

---

## 7. Configuracao do Redis

O Redis 7 tambem roda como container Docker.

### 7.1. Especificacoes

- **Imagem:** `redis:7-alpine`
- **Senha:** Gerada automaticamente (variavel `REDIS_PASSWORD`)
- **Memoria maxima:** 256 MB
- **Politica de evicao:** allkeys-lru (remove chaves menos usadas)
- **Porta interna:** 6379
- **Porta externa:** 127.0.0.1:6379 (apenas acesso local)
- **Dados:** Volume Docker `redis_data`

### 7.2. Funcoes do Redis no sistema

- **Cache:** Resultados de busca, sessoes
- **Message Broker:** Fila de tarefas assincronas (Celery)
- **Result Backend:** Armazena resultados de tasks completadas

---

## 8. Build e Deploy da Aplicacao

### 8.1. Construir todas as imagens Docker

```bash
cd /opt/analisador-curriculos
docker compose -f docker-compose.prod.yml build --no-cache
```

Isso vai construir:
- **api:** Backend FastAPI (Python 3.11)
- **celery-worker:** Worker de processamento assincrono
- **flower:** Interface de monitoramento do Celery
- **frontend:** React + Nginx

Tempo estimado: 5-15 minutos na primeira vez.

### 8.2. Iniciar todos os servicos

```bash
docker compose -f docker-compose.prod.yml up -d
```

### 8.3. Verificar se todos os servicos estao rodando

```bash
docker compose -f docker-compose.prod.yml ps
```

Resultado esperado - todos com status `Up (healthy)`:
```
NAME                    STATUS              PORTS
analisador-api-1        Up (healthy)        127.0.0.1:8000->8000/tcp
analisador-celery-1     Up (healthy)
analisador-db-1         Up (healthy)        127.0.0.1:5432->5432/tcp
analisador-flower-1     Up                  127.0.0.1:5555->5555/tcp
analisador-frontend-1   Up                  127.0.0.1:3000->80/tcp
analisador-grafana-1    Up                  127.0.0.1:3001->3000/tcp
analisador-prometheus-1 Up                  127.0.0.1:9090->9090/tcp
analisador-redis-1      Up (healthy)        127.0.0.1:6379->6379/tcp
```

### 8.4. Verificar logs

```bash
# Todos os servicos
docker compose -f docker-compose.prod.yml logs -f

# Apenas a API
docker compose -f docker-compose.prod.yml logs -f api

# Apenas o worker
docker compose -f docker-compose.prod.yml logs -f celery-worker
```

---

## 9. Inicializacao do Banco de Dados

### 9.1. Criar tabelas, extensoes e indices

```bash
docker compose -f docker-compose.prod.yml exec api python -m app.db.init_db
```

Isso cria:
- Extensao pgvector
- Todas as tabelas (candidates, documents, embeddings, etc.)
- Indices HNSW para busca vetorial
- Indices de full-text search

### 9.2. Criar roles e usuario admin

```bash
docker compose -f docker-compose.prod.yml exec api python -m app.db.init_roles
```

Isso cria:
- **Role admin:** Acesso total ao sistema
- **Role recruiter:** Acesso a candidatos, busca e chat
- **Role viewer:** Acesso somente leitura
- **Usuario admin:** admin@analisador.com / admin123

**IMPORTANTE:** Troque a senha do admin imediatamente apos o primeiro login!

### 9.3. Verificar conexao com o banco

```bash
docker compose -f docker-compose.prod.yml exec api python -c "
from app.db.database import engine
from sqlalchemy import text
with engine.connect() as conn:
    result = conn.execute(text('SELECT version()'))
    print('PostgreSQL:', result.scalar())
    result = conn.execute(text('SELECT extversion FROM pg_extension WHERE extname = \'vector\''))
    row = result.first()
    print('pgvector:', row[0] if row else 'NAO INSTALADO')
"
```

---

## 10. Configuracao do Nginx e SSL

### 10.1. Instalar Nginx e Certbot

```bash
sudo apt-get install -y nginx certbot python3-certbot-nginx
```

### 10.2. Criar configuracao do Nginx

```bash
sudo tee /etc/nginx/sites-available/analisador > /dev/null <<'EOF'
server {
    listen 80;
    server_name SEU_DOMINIO.com.br;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;

    server_tokens off;
    client_max_body_size 20M;

    # Frontend (React via Nginx container)
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API (FastAPI)
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    # Grafana (opcional - monitoramento)
    location /grafana/ {
        proxy_pass http://127.0.0.1:3001/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF
```

**IMPORTANTE:** Substitua `SEU_DOMINIO.com.br` pelo seu dominio real!

### 10.3. Ativar o site

```bash
sudo ln -sf /etc/nginx/sites-available/analisador /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

### 10.4. Configurar SSL com Let's Encrypt (gratuito)

**Pre-requisito:** O dominio deve estar apontando para o IP da VPS (DNS configurado).

```bash
sudo certbot --nginx -d SEU_DOMINIO.com.br
```

O Certbot vai:
1. Verificar a propriedade do dominio
2. Gerar certificado SSL gratuito
3. Configurar redirecionamento HTTP -> HTTPS automaticamente
4. Configurar renovacao automatica

### 10.5. Verificar renovacao automatica

```bash
sudo certbot renew --dry-run
```

### 10.6. Apos SSL, reconstruir frontend com HTTPS

```bash
# Atualizar .env raiz
nano .env
# Certificar que FRONTEND_API_URL=https://SEU_DOMINIO.com.br
# Certificar que FRONTEND_WS_URL=wss://SEU_DOMINIO.com.br

# Reconstruir o frontend com as URLs corretas
docker compose -f docker-compose.prod.yml build frontend
docker compose -f docker-compose.prod.yml up -d frontend
```

---

## 11. Configuracao pelo Frontend

Apos o deploy, TODAS as configuracoes do sistema podem ser gerenciadas pelo frontend.

### 11.1. Primeiro acesso

1. Acesse `https://SEU_DOMINIO.com.br`
2. Faca login com: `admin@analisador.com` / `admin123`
3. **TROQUE A SENHA IMEDIATAMENTE** em Perfil

### 11.2. Pagina de Configuracoes

Acesse **Configuracoes** no menu lateral. A pagina esta organizada em abas:

#### Aba: Geral
- Nome da aplicacao
- Nivel de log (DEBUG/INFO/WARNING)
- Modo debug
- Multi-tenant (empresas separadas)

#### Aba: Banco de Dados
- URL de conexao PostgreSQL
- Tamanho do pool de conexoes
- Overflow e timeout

#### Aba: Redis / Celery
- URL do Redis
- Workers concorrentes
- Timeouts de tasks

#### Aba: IA & Embeddings
- **Modo de vetorizacao:**
  - `code` = Local (gratis, usa sentence-transformers)
  - `api` = OpenAI (pago, melhor qualidade)
- Chave API OpenAI (se modo api)
- Modelo de embeddings
- Dimensoes dos vetores
- Dispositivo (CPU/CUDA/MPS)

#### Aba: Banco Vetorial
- Provedor: pgvector (padrao), Supabase ou Qdrant
- Parametros HNSW (qualidade do indice)
- Metrica de distancia
- Configuracoes de cada provedor

#### Aba: LLM & Chat
- Modelo do chat (ex: gpt-4-turbo-preview)
- Temperatura (criatividade)
- Limites de tokens
- Contexto de conversa

#### Aba: Busca & Ranking
- Threshold de similaridade
- Pesos da busca hibrida (vetorial, full-text, filtros, dominio)
- Parametros de confianca

#### Aba: Matching de Vagas
- Thresholds de pontos fortes e lacunas
- Bonus (CNH, experiencia, keywords)

#### Aba: OCR
- Idiomas do Tesseract
- Confianca minima
- Resolucoes DPI

#### Aba: Chunking & Indexacao
- Tamanho dos chunks
- Sobreposicao
- Extracao de keywords

#### Aba: Armazenamento
- Backend (local/S3/MinIO)
- Tamanho max de upload
- Configuracoes S3

#### Aba: Seguranca
- Chave JWT
- Expiracao de tokens
- Criptografia PII (LGPD)
- Rate limiting
- CORS origins

#### Aba: Custos de IA
- Moeda (USD/BRL/EUR)
- Taxa de cambio
- Precos por 1K tokens
- Limites mensais

#### Aba: LinkedIn
- Habilitar integracao
- Credenciais OAuth

#### Aba: Saude do Sistema
- Status de todos os servicos
- Versao do sistema

### 11.3. Como as configuracoes funcionam

- Configuracoes alteradas pelo frontend sao salvas no **banco de dados**
- Elas **sobrescrevem** os valores do arquivo `.env`
- Campos marcados com **"restart"** requerem reiniciar os containers
- Para reiniciar apos mudancas:
  ```bash
  docker compose -f docker-compose.prod.yml restart api celery-worker
  ```

### 11.4. Resetar configuracoes

No frontend, o botao **"Resetar"** remove todas as personalizacoes,
voltando aos valores do `.env` e padroes do sistema.

---

## 12. Monitoramento

### 12.1. Grafana

- **URL:** `https://SEU_DOMINIO.com.br/grafana/`
- **Login:** admin / (senha gerada no setup)
- Dashboards pre-configurados para FastAPI e Celery
- Datasource Prometheus ja conectado

### 12.2. Flower (Celery Monitor)

- **URL:** `http://SEU_IP:5555` (acesso local apenas)
- **Login:** admin / (senha gerada no setup)
- Monitoramento em tempo real de tasks

### 12.3. Prometheus

- **URL:** `http://127.0.0.1:9090` (acesso local apenas)
- Metricas coletadas a cada 15 segundos
- Retencao: 30 dias

### 12.4. Verificar saude via API

```bash
curl https://SEU_DOMINIO.com.br/api/health
```

Resposta esperada:
```json
{
  "status": "healthy",
  "version": "0.3.0",
  "database": "connected",
  "redis": "connected",
  "celery": "ok",
  "vector_db": "connected"
}
```

---

## 13. Backup Automatizado

### 13.1. Configurar backup diario

```bash
# Criar diretorio de backups
sudo mkdir -p /opt/backups/postgres
sudo chown deploy:deploy /opt/backups/postgres

# Testar backup manual
cd /opt/analisador-curriculos
bash scripts/backup.sh
```

### 13.2. Agendar via cron (diario as 3h)

```bash
crontab -e
# Adicionar a linha:
0 3 * * * /opt/analisador-curriculos/scripts/backup.sh >> /opt/backups/postgres/backup.log 2>&1
```

### 13.3. O que e feito backup

- **PostgreSQL:** Dump completo compactado (curriculos, usuarios, configuracoes)
- **Uploads:** Arquivos de curriculos (PDF, DOCX)
- **Configuracoes:** Arquivo `.env` com todas as configuracoes
- **Retencao:** 30 dias (configuravel)

### 13.4. Restaurar backup

```bash
# Restaurar banco de dados
docker compose -f docker-compose.prod.yml exec -T db \
    pg_restore -U analisador -d analisador_curriculos --clean --if-exists \
    < /opt/backups/postgres/db_backup_YYYYMMDD_HHMMSS.dump

# Restaurar uploads
docker compose -f docker-compose.prod.yml exec -T api \
    tar -xzf - -C /app \
    < /opt/backups/postgres/uploads_backup_YYYYMMDD_HHMMSS.tar.gz
```

---

## 14. Atualizacoes e Manutencao

### 14.1. Atualizar o sistema

```bash
cd /opt/analisador-curriculos

# Baixar atualizacoes
git pull origin main

# Reconstruir e reiniciar
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d

# Se houver mudancas no banco de dados
docker compose -f docker-compose.prod.yml exec api python -m app.db.init_db
```

### 14.2. Ver logs de erro

```bash
# API
docker compose -f docker-compose.prod.yml logs --tail=100 api

# Worker
docker compose -f docker-compose.prod.yml logs --tail=100 celery-worker

# Todos
docker compose -f docker-compose.prod.yml logs --tail=100
```

### 14.3. Reiniciar servicos

```bash
# Todos
docker compose -f docker-compose.prod.yml restart

# Apenas API e worker
docker compose -f docker-compose.prod.yml restart api celery-worker

# Apenas frontend (apos mudanca de configuracao)
docker compose -f docker-compose.prod.yml restart frontend
```

### 14.4. Parar tudo

```bash
docker compose -f docker-compose.prod.yml down
```

### 14.5. Parar e remover dados (CUIDADO!)

```bash
# Remove containers E volumes (PERDE TODOS OS DADOS!)
docker compose -f docker-compose.prod.yml down -v
```

---

## 15. Troubleshooting

### Container nao inicia

```bash
# Ver logs do container especifico
docker compose -f docker-compose.prod.yml logs api

# Erros comuns:
# "connection refused" -> Banco nao esta pronto ainda, aguarde
# "authentication failed" -> Senha do DB nao bate entre .env e .env raiz
# "port already in use" -> Outra aplicacao usando a porta
```

### API retorna 502 Bad Gateway

```bash
# Verificar se a API esta rodando
docker compose -f docker-compose.prod.yml ps api

# Verificar logs
docker compose -f docker-compose.prod.yml logs api

# Reiniciar
docker compose -f docker-compose.prod.yml restart api
```

### Banco de dados lento

```bash
# Ver conexoes ativas
docker compose -f docker-compose.prod.yml exec db psql -U analisador -d analisador_curriculos \
    -c "SELECT count(*) FROM pg_stat_activity;"

# Ver queries lentas
docker compose -f docker-compose.prod.yml exec db psql -U analisador -d analisador_curriculos \
    -c "SELECT pid, now() - pg_stat_activity.query_start AS duration, query
        FROM pg_stat_activity
        WHERE state != 'idle'
        ORDER BY duration DESC LIMIT 5;"
```

### Worker Celery parado

```bash
# Verificar status
docker compose -f docker-compose.prod.yml exec celery-worker \
    celery -A app.core.celery_app inspect ping

# Reiniciar worker
docker compose -f docker-compose.prod.yml restart celery-worker
```

### Disco cheio

```bash
# Ver uso de disco por container
docker system df

# Limpar imagens/containers nao usados
docker system prune -f

# Limpar imagens antigas
docker image prune -a -f
```

### Memoria alta

```bash
# Ver uso de memoria por container
docker stats --no-stream

# Os limites estao no docker-compose.prod.yml:
# api: 2G, celery: 2G, db: 1G, redis: 512M
```

---

## 16. Deploy Automatico

Para fazer o deploy completo de uma vez, use o script automatizado:

```bash
cd /opt/analisador-curriculos

# Define o dominio antes de executar
export DOMAIN="curriculos.seudominio.com.br"

# Executa o deploy completo
sudo bash scripts/deploy-vps.sh
```

O script faz automaticamente:
1. Atualiza o sistema
2. Instala Docker
3. Configura firewall
4. Configura Fail2Ban
5. Gera senhas seguras
6. Configura Nginx
7. Constroi e inicia todos os containers

**Apos o script:**
1. Configure SSL: `sudo certbot --nginx -d SEU_DOMINIO`
2. Inicialize o banco: passos da [secao 9](#9-inicializacao-do-banco-de-dados)
3. Acesse o frontend e configure tudo pela interface

---

## Resumo Rapido

```bash
# 1. Preparar VPS
ssh root@IP && adduser deploy && usermod -aG sudo deploy

# 2. Instalar Docker
curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker deploy

# 3. Clonar projeto
sudo mkdir -p /opt/analisador-curriculos && cd /opt/analisador-curriculos
git clone https://github.com/zerocouldbr/analisador_de_curriculos.git .

# 4. Gerar configuracoes
python3 setup.py vps

# 5. Editar dominios
nano backend/.env    # CORS_ORIGINS
nano .env            # FRONTEND_API_URL, FRONTEND_WS_URL

# 6. Build e deploy
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d

# 7. Inicializar banco
docker compose -f docker-compose.prod.yml exec api python -m app.db.init_db
docker compose -f docker-compose.prod.yml exec api python -m app.db.init_roles

# 8. Configurar Nginx + SSL
sudo apt install nginx certbot python3-certbot-nginx
# (criar config do nginx - secao 10)
sudo certbot --nginx -d SEU_DOMINIO.com.br

# 9. Reconstruir frontend com HTTPS
docker compose -f docker-compose.prod.yml build frontend
docker compose -f docker-compose.prod.yml up -d frontend

# 10. Acessar e configurar tudo pelo frontend
# https://SEU_DOMINIO.com.br
# Login: admin@analisador.com / admin123
# Ir em Configuracoes e preencher tudo!

# 11. Configurar backup diario
crontab -e
# 0 3 * * * /opt/analisador-curriculos/scripts/backup.sh >> /opt/backups/postgres/backup.log 2>&1
```

---

## 17. Referencia de API

### 17.1. Autenticacao

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| POST | `/api/v1/auth/login` | Login (form data: username + password). Retorna tokens + dados do usuario |
| POST | `/api/v1/auth/register` | Registrar novo usuario (JSON: email, name, password) |
| POST | `/api/v1/auth/refresh` | Renovar access token usando refresh token |
| GET | `/api/v1/auth/me` | Dados do usuario autenticado |
| POST | `/api/v1/auth/change-password` | Alterar senha |

**Login:** O endpoint `/auth/login` aceita `application/x-www-form-urlencoded` (padrao OAuth2) com campos `username` (email) e `password`. Retorna:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "admin@analisador.com",
    "name": "Admin",
    "status": "active",
    "is_superuser": true,
    "roles": ["admin"]
  }
}
```

**Refresh Token:** Quando o `access_token` expira (15min), use o `refresh_token` (7 dias) para obter novos tokens:
```bash
curl -X POST https://SEU_DOMINIO/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "eyJ..."}'
```

### 17.2. Candidatos

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| GET | `/api/v1/candidates/` | Listar candidatos (filtros: city, state) |
| GET | `/api/v1/candidates/{id}` | Detalhes do candidato |
| POST | `/api/v1/candidates/` | Criar candidato |
| PUT | `/api/v1/candidates/{id}` | Atualizar candidato |
| DELETE | `/api/v1/candidates/{id}` | Remover candidato (LGPD) |
| GET | `/api/v1/candidates/{id}/documents` | Documentos do candidato |
| GET | `/api/v1/candidates/{id}/experiences` | Experiencias profissionais |
| GET | `/api/v1/candidates/{id}/profiles` | Snapshots/perfis versionados |

### 17.3. Busca

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| POST | `/api/v1/search/semantic` | Busca semantica (query + limit) |
| POST | `/api/v1/search/hybrid` | Busca hibrida (query + filters + limit) |
| POST | `/api/v1/search/keywords/extract` | Extrair keywords de texto |
| GET | `/api/v1/search/keywords/candidate/{id}` | Keywords de um candidato |
| POST | `/api/v1/search/job-match` | Matching candidato x vaga |
| GET | `/api/v1/search/job-profiles` | Perfis de vagas disponiveis |

**Importante:** Os endpoints de busca usam o campo `limit` (nao `top_k`) para controlar o numero de resultados.

### 17.4. VectorDB

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| GET | `/api/v1/vectordb/config` | Configuracao do vector DB |
| GET | `/api/v1/vectordb/health` | Saude do vector store |
| GET | `/api/v1/vectordb/info` | Informacoes detalhadas |
| GET | `/api/v1/vectordb/count` | Contagem de vetores |
| POST | `/api/v1/vectordb/initialize` | Inicializar/reinicializar vector store |
| GET | `/api/v1/vectordb/providers` | Provedores disponiveis |

### 17.5. Configuracoes

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| GET | `/api/v1/settings/system/config` | Todas as configuracoes do sistema |
| PUT | `/api/v1/settings/system/config` | Atualizar configuracoes |
| POST | `/api/v1/settings/system/config/reset` | Restaurar padroes |

### 17.6. Documentacao Interativa

A API possui documentacao interativa (Swagger UI) acessivel em:
- **Swagger:** `https://SEU_DOMINIO/api/docs`
- **ReDoc:** `https://SEU_DOMINIO/api/redoc`

---

## 18. Historico de Melhorias e Correcoes

### v0.3.1 - Correcoes Criticas do Portal

#### Problema: Erro "Algo deu errado" ao fazer login
**Causa raiz:** Tres problemas encadeados no fluxo de autenticacao:

1. **Incompatibilidade de formato:** O frontend enviava `FormData` (OAuth2) mas o backend esperava JSON puro (`UserLogin` Pydantic model). Isso gerava erro 422.
2. **Crash na renderizacao:** O erro 422 retorna `detail` como array de objetos. O React tentava renderizar o array diretamente, causando "Objects are not valid as a React child" que era capturado pelo ErrorBoundary.
3. **Resposta sem dados do usuario:** O backend retornava apenas tokens, mas o frontend esperava um campo `user` na resposta.

**Correcoes aplicadas:**
- Backend: Endpoint `/auth/login` agora usa `OAuth2PasswordRequestForm` para aceitar form data
- Backend: Novo schema `LoginResponse` retorna tokens + dados do usuario
- Frontend: Tratamento seguro de erros da API (converte arrays para string)
- Frontend: Fallback para `/auth/me` se resposta nao incluir usuario

#### Novos Endpoints Adicionados

| Endpoint | Descricao |
|----------|-----------|
| `POST /v1/auth/refresh` | Renovacao de tokens (refresh token) |
| `GET /v1/candidates/{id}/experiences` | Experiencias profissionais do candidato |
| `GET /v1/candidates/{id}/profiles` | Perfis/snapshots versionados do candidato |

#### Correcoes de Consistencia Frontend-Backend

| Problema | Correcao |
|----------|----------|
| Frontend enviava `top_k`, backend esperava `limit` | Parametro corrigido para `limit` em todas as buscas |
| Frontend chamava `GET /v1/search/keywords`, backend esperava `POST /v1/search/keywords/extract` | Frontend corrigido para usar POST |
| Frontend chamava `/v1/vectordb/embeddings/refresh`, nao existia | Corrigido para `/v1/vectordb/initialize` |
| Frontend chamava `/v1/vectordb/status`, nao existia | Corrigido para `/v1/vectordb/health` |
| WebSocket usava `payload.get("sub")` em vez de `token_data.user_id` | Corrigido para usar `TokenData` corretamente |
| WebSocket usava `print()` para logs | Substituido por `logging.getLogger()` |
| Tipo `User` no frontend sem campo `last_login` | Campo adicionado ao TypeScript |
| Endpoints DELETE sem `return` explicito (204 No Content) | `return` adicionado para consistencia |

#### Stack Tecnologica na VPS

Componentes instalados e configurados na VPS de producao:

| Componente | Versao | Funcao |
|------------|--------|--------|
| Ubuntu Server | 22.04+ LTS | Sistema operacional |
| Docker Engine | 27.x | Containerizacao |
| Docker Compose | v2.x (plugin) | Orquestracao de containers |
| Nginx | 1.18+ | Reverse proxy + SSL termination |
| Certbot | 2.x | Certificados SSL Let's Encrypt |
| PostgreSQL | 16 + pgvector | Banco relacional + vetorial |
| Redis | 7 Alpine | Cache + message broker |
| Python | 3.11 (container) | Runtime do backend |
| Node.js | 18 (build) | Build do frontend |
| Tesseract OCR | 5.x (container) | Processamento de imagens/PDFs |
| Celery | 5.x (container) | Processamento assincrono |
| Flower | 2.x (container) | Monitoramento de tasks |
| Prometheus | latest (container) | Coleta de metricas |
| Grafana | latest (container) | Dashboards de monitoramento |
| UFW | - | Firewall |
| Fail2Ban | - | Protecao anti brute-force |

#### Limites de Recursos (Producao)

| Container | Memoria Max | Porta |
|-----------|-------------|-------|
| API (FastAPI) | 2 GB | 127.0.0.1:8000 |
| Celery Worker | 2 GB | - |
| PostgreSQL | 1 GB | 127.0.0.1:5432 |
| Redis | 512 MB | 127.0.0.1:6379 |
| Frontend (Nginx) | - | 127.0.0.1:3000 |
| Prometheus | - | 127.0.0.1:9090 |
| Grafana | - | 127.0.0.1:3001 |
| Flower | - | 127.0.0.1:5555 |

> **Nota:** Todas as portas estao expostas apenas em 127.0.0.1 (localhost). O acesso externo e feito exclusivamente via Nginx (portas 80/443).
