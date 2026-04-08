# Analisador de Curriculos (On-Premises)

Sistema completo de RH on-premises para ingestao, analise, indexacao vetorial e busca inteligente de curriculos.

## Funcionalidades

- Upload e analise de curriculos (PDF, DOCX, TXT, imagens com OCR)
- Busca semantica com embeddings OpenAI + pgvector
- Busca hibrida (semantica + texto completo + filtros)
- Chat inteligente com LLM sobre os curriculos
- Autenticacao JWT com RBAC (admin, recruiter, viewer)
- Processamento assincrono com Celery
- WebSocket para atualizacoes em tempo real
- LinkedIn integration para enriquecimento de perfis
- LGPD compliance com auditoria completa
- Monitoramento com Prometheus + Grafana

---

## Inicio Rapido

### Pre-requisitos

- **Python 3.11+**
- **Node.js 18+**
- **Docker e Docker Compose** (para PostgreSQL e Redis)

### 1. Clonar o repositorio

```bash
git clone https://github.com/ZerocouldBR/Analisador_de_curriculos.git
cd Analisador_de_curriculos
```

### 2. Gerar arquivo de configuracao

```bash
python setup.py local
```

Isso cria `backend/.env` com todas as variaveis configuradas para localhost.

### 3. Subir PostgreSQL e Redis

```bash
docker compose -f docker-compose.dev.yml up -d
```

Isso inicia apenas o banco de dados (PostgreSQL 16 + pgvector) e Redis.

> **Sem Docker?** Instale PostgreSQL 16 com extensao pgvector e Redis 7 manualmente.
> Crie o banco: `CREATE DATABASE analisador_curriculos;`
> Crie o usuario: `CREATE USER analisador WITH PASSWORD 'analisador';`

### 4. Configurar o backend

```bash
cd backend
python -m venv .venv

# Linux/Mac:
source .venv/bin/activate

# Windows:
.venv\Scripts\activate

pip install -r requirements.txt
```

### 5. Inicializar o banco de dados

```bash
# Ainda dentro de backend/ com o venv ativado:
python -m app.db.init_db
python -m app.db.init_roles
```

Isso cria todas as tabelas, indices vetoriais, roles e o usuario admin.

### 6. Iniciar o backend

```bash
uvicorn app.main:app --reload
```

API disponivel em http://localhost:8000/docs

### 7. Iniciar o frontend (novo terminal)

```bash
cd frontend
npm install
npm start
```

Frontend disponivel em http://localhost:3000

### 8. Login

```
Email: admin@analisador.com
Senha: admin123
```

> **IMPORTANTE:** Altere a senha do admin em producao!

---

## Deploy em VPS (Docker Compose)

Para instalar tudo em uma VPS com Docker:

### 1. Clonar e configurar

```bash
git clone https://github.com/ZerocouldBR/Analisador_de_curriculos.git
cd Analisador_de_curriculos
python3 setup.py vps
```

O script gera senhas seguras automaticamente para o banco, Redis, Flower e Grafana.

### 2. Editar configuracoes

```bash
# Ajuste o dominio e CORS:
nano backend/.env

# Ajuste o dominio do frontend:
nano .env

# Adicione sua chave da OpenAI (se usar embeddings):
# OPENAI_API_KEY=sk-...
```

### 3. Subir todos os servicos

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

### 4. Inicializar o banco de dados (primeira vez)

```bash
docker compose -f docker-compose.prod.yml exec api python -m app.db.init_db
docker compose -f docker-compose.prod.yml exec api python -m app.db.init_roles
```

### 5. Acessar

| Servico | URL | Descricao |
|---------|-----|-----------|
| Frontend | http://seu-ip:3000 | Interface React |
| API | http://seu-ip:8000 | Backend FastAPI |
| API Docs | http://seu-ip:8000/docs | Swagger UI |
| Flower | http://seu-ip:5555 | Monitor Celery |
| Prometheus | http://seu-ip:9090 | Metricas |
| Grafana | http://seu-ip:3001 | Dashboards |

Login: `admin@analisador.com` / `admin123`

---

## Docker Compose Completo (Desenvolvimento)

Para rodar **tudo** via Docker (sem instalar Python/Node localmente):

```bash
cp backend/.env.example backend/.env
# Edite backend/.env e defina SECRET_KEY

docker compose up -d --build

# Inicializar banco:
docker compose exec api python -m app.db.init_db
docker compose exec api python -m app.db.init_roles
```

---

## Celery Worker (processamento assincrono)

Para processar curriculos em background (upload e indexacao):

```bash
# Terminal separado, dentro de backend/ com venv ativado:
celery -A app.core.celery_app worker --loglevel=info
```

> No Docker Compose, o Celery ja roda automaticamente.

---

## Estrutura do Projeto

```
Analisador_de_curriculos/
├── backend/                 # API FastAPI
│   ├── app/
│   │   ├── api/v1/         # Endpoints REST
│   │   ├── core/           # Config, seguranca, celery
│   │   ├── db/             # Models, database, init
│   │   ├── schemas/        # Validacao Pydantic
│   │   ├── services/       # Logica de negocio
│   │   ├── tasks/          # Tarefas Celery
│   │   └── vectorstore/    # Integracao vetorial
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/                # Interface React + TypeScript
│   ├── src/
│   │   ├── components/     # Componentes reutilizaveis
│   │   ├── pages/          # Paginas da aplicacao
│   │   ├── services/       # API clients
│   │   └── types/          # TypeScript types
│   ├── package.json
│   └── Dockerfile
├── monitoring/              # Prometheus + Grafana
├── docker-compose.yml       # Dev completo (todos os servicos)
├── docker-compose.dev.yml   # Dev minimo (so DB + Redis)
├── docker-compose.prod.yml  # Producao
└── setup.py                 # Script de setup automatico
```

## Configuracao

### Variaveis de Ambiente Principais

| Variavel | Descricao | Default |
|----------|-----------|---------|
| `SECRET_KEY` | Chave JWT (obrigatoria em prod) | Auto-gerada para dev |
| `DATABASE_URL` | URL do PostgreSQL | `localhost:5432` |
| `REDIS_URL` | URL do Redis | `localhost:6379` |
| `OPENAI_API_KEY` | Chave da API OpenAI | (opcional) |
| `CORS_ORIGINS` | Origens permitidas | `["http://localhost:3000"]` |
| `VECTOR_DB_PROVIDER` | pgvector, supabase, qdrant | `pgvector` |
| `EMBEDDING_MODE` | api (OpenAI) ou code (local) | `api` |
| `DEBUG` | Modo debug | `false` |

Veja todas as opcoes em `backend/.env.example`.

## Modelo de Dados

PostgreSQL 16 com extensao pgvector. Principais tabelas:

- **users / roles** - Autenticacao e RBAC
- **candidates** - Dados dos candidatos
- **candidate_profiles** - Snapshots versionados
- **documents** - Arquivos de curriculo
- **chunks** - Secoes extraidas com metadados
- **embeddings** - Vetores para busca semantica
- **experiences** - Experiencias profissionais
- **audit_logs** - Registro de operacoes (LGPD)

## Busca Inteligente

Busca hibrida combinando:
- **40%** Similaridade semantica (embeddings + pgvector)
- **30%** Busca de texto completo (tsvector Portuguese)
- **20%** Filtros estruturados (cidade, estado, habilidades)
- **10%** Dominio de conhecimento

## Seguranca

| Role | Descricao |
|------|-----------|
| admin | Acesso completo |
| recruiter | CRUD candidatos/docs, busca, LinkedIn |
| viewer | Apenas leitura |

## Tecnologias

**Backend:** FastAPI, PostgreSQL 16 + pgvector, Redis 7, Celery, OpenAI API, Tesseract OCR

**Frontend:** React 18, TypeScript, Material-UI 5, WebSocket

**Infra:** Docker Compose, Prometheus, Grafana, Flower

## Testes

```bash
# Backend
cd backend && pytest

# Frontend
cd frontend && npm test
```

## Licenca

MIT
