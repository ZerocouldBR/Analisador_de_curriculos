# Analisador de Curriculos (On-Premises)

Sistema completo de RH on-premises para ingestao, analise, indexacao vetorial e busca inteligente de curriculos.

## Funcionalidades Implementadas

### Backend (FastAPI)
- Autenticacao JWT com RBAC completo (admin, recruiter, viewer)
- Upload de curriculos (PDF, DOCX, TXT, imagens com OCR avancado)
- Processamento assincrono com Celery
- WebSocket para atualizacoes em tempo real
- Busca semantica com embeddings OpenAI
- Busca hibrida (semantica + texto completo + filtros)
- LinkedIn integration para enriquecimento de perfis
- LGPD compliance com auditoria completa
- Configuracoes dinamicas e prompts LLM customizaveis
- API documentada com OpenAPI/Swagger
- Extracao automatica de experiencias profissionais para tabela dedicada
- Snapshot de perfis de candidatos versionado

### Frontend (React + TypeScript)
- Interface completa em Material-UI
- Dashboard com estatisticas e metricas
- Gerenciamento de candidatos (CRUD completo)
- Upload com drag & drop e progresso em tempo real
- Busca inteligente com highlight de resultados
- Administracao de funcoes e permissoes
- Configuracoes do sistema
- WebSocket para notificacoes instantaneas

### Infraestrutura
- Docker Compose completo com 8 servicos
- Celery para processamento em background
- Flower para monitoramento de tarefas
- Prometheus para coleta de metricas
- Grafana com dashboards customizados
- PostgreSQL 16 com pgvector
- Redis para cache e filas

## Estrutura do Projeto

```
analisador-curriculos/
├── backend/              # API FastAPI
│   ├── app/
│   │   ├── api/         # Endpoints REST (v1/)
│   │   │   └── v1/     # auth, candidates, documents, linkedin, search, settings, websocket
│   │   ├── core/        # Configuracao, seguranca, celery, websocket
│   │   ├── db/          # Models, database, init_db, init_roles
│   │   ├── schemas/     # Validacao Pydantic
│   │   ├── services/    # Logica de negocio
│   │   └── tasks/       # Tarefas Celery (document_tasks)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/            # Interface React
│   ├── src/
│   │   ├── components/  # Componentes reutilizaveis
│   │   ├── contexts/    # Contextos React
│   │   ├── pages/       # Paginas da aplicacao
│   │   ├── services/    # API e WebSocket clients
│   │   └── types/       # TypeScript types
│   ├── package.json
│   └── Dockerfile
├── monitoring/          # Prometheus e Grafana
│   ├── prometheus.yml
│   └── grafana/
│       ├── dashboards/
│       └── datasources/
├── docs/               # Documentacao
│   ├── arquitetura.md
│   ├── modelo_dados.md
│   ├── fluxos.md
│   └── novas_implementacoes.md
└── docker-compose.yml  # Orquestracao completa
```

## Quick Start

### Iniciar todos os servicos (Recomendado)

```bash
# 1. Clonar repositorio
git clone https://github.com/ZerocouldBR/Analisador_de_curriculos.git
cd Analisador_de_curriculos

# 2. Configurar ambiente
cp backend/.env.example backend/.env
# Edite backend/.env com suas configuracoes

# 3. Iniciar stack completa
docker-compose up -d

# 4. Verificar status
docker-compose ps

# 5. Ver logs
docker-compose logs -f
```

### Acessar servicos

| Servico | URL | Descricao |
|---------|-----|-----------|
| Frontend | http://localhost:3000 | Interface React |
| API | http://localhost:8000 | Backend FastAPI |
| API Docs | http://localhost:8000/docs | Swagger UI |
| Flower | http://localhost:5555 | Monitor Celery |
| Prometheus | http://localhost:9090 | Metricas |
| Grafana | http://localhost:3001 | Dashboards (admin/admin) |

### Desenvolvimento Local

**Backend:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm start
```

**Celery Worker:**
```bash
cd backend
celery -A app.core.celery_app worker --loglevel=info
```

## Modelo de Dados

O sistema utiliza PostgreSQL 16 com a extensao pgvector para busca vetorial. Principais tabelas:

- **users / roles / user_roles** - Autenticacao e RBAC
- **candidates** - Dados pessoais dos candidatos (PII protegida)
- **candidate_profiles** - Snapshots versionados do curriculo parseado
- **documents** - Arquivos de curriculo (PDF, DOCX, etc.)
- **chunks** - Secoes extraidas com metadados enriquecidos
- **embeddings** - Vetores para busca semantica (pgvector)
- **experiences** - Experiencias profissionais estruturadas
- **external_enrichments** - Dados de fontes externas (LinkedIn)
- **server_settings** - Configuracoes dinamicas do sistema
- **audit_logs** - Registro completo de operacoes (LGPD)

Para detalhes completos, veja [docs/modelo_dados.md](docs/modelo_dados.md).

## Pipeline de Processamento

1. **Upload**: Arquivo enviado via API com deduplicacao por SHA-256
2. **Extracao de Texto**: PDF (pdfplumber), DOCX (python-docx), OCR (Tesseract) com preprocessamento avancado
3. **Parsing**: Extracao estruturada de dados pessoais, experiencias, formacao, habilidades, certificacoes
4. **Atualizacao**: Candidato atualizado com dados extraidos (nome, email, CPF, etc.)
5. **Experiencias**: Tabela `experiences` populada com historico profissional
6. **Perfil**: Snapshot salvo em `candidate_profiles`
7. **Chunks**: Secoes criadas com metadados (keywords, perfil industrial)
8. **Embeddings**: Vetores gerados sob demanda para busca semantica

## Busca Inteligente

O sistema suporta busca hibrida combinando:
- **40%** Similaridade semantica (embeddings + pgvector)
- **30%** Busca de texto completo (tsvector Portuguese)
- **20%** Filtros estruturados (cidade, estado, habilidades)
- **10%** Dominio de conhecimento (producao, logistica, TI)

## Seguranca e Compliance

### RBAC (Role-Based Access Control)

| Role | Descricao |
|------|-----------|
| admin | Acesso completo ao sistema |
| recruiter | CRUD de candidatos/docs, LinkedIn, busca avancada |
| viewer | Apenas leitura |

### Permissoes Granulares

Todos os endpoints de escrita requerem autenticacao JWT e permissoes especificas:
- `candidates.*` - Operacoes com candidatos
- `documents.*` - Operacoes com documentos
- `settings.*` - Configuracoes do sistema
- `linkedin.enrich` - Enriquecimento via LinkedIn
- `search.advanced` - Busca avancada
- `users.manage` - Gerenciamento de usuarios

### LGPD
- Auditoria completa de todas as operacoes
- Remocao em cascata de dados pessoais
- Separacao de PII

## Configuracao

### Variaveis de Ambiente

**Backend (`.env`):**
```env
APP_VERSION=0.3.0
DATABASE_URL=postgresql+psycopg://analisador:analisador@db:5432/analisador_curriculos
REDIS_URL=redis://redis:6379/0
SECRET_KEY=your-secret-key-here
OPENAI_API_KEY=sk-... (opcional, para embeddings)
```

**Frontend (`.env`):**
```env
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000
```

## Testes

```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm test
```

## Monitoramento

### Prometheus
Acesse http://localhost:9090 para queries de metricas.

### Grafana
1. Acesse http://localhost:3001
2. Login: admin/admin
3. Dashboard "Analisador de Curriculos - System Dashboard"

Metricas disponiveis:
- Taxa de requisicoes da API
- Tempo de resposta (p95, p99)
- Tarefas Celery ativas
- Taxa de sucesso de tarefas
- Conexoes do banco de dados
- Uso de memoria do Redis
- Upload rate
- WebSocket connections

## Tecnologias

**Backend:** FastAPI 0.115, PostgreSQL 16 + pgvector, Redis 7, Celery 5.3, OpenAI API, Tesseract OCR

**Frontend:** React 18, TypeScript 5, Material-UI 5, Axios, WebSocket, React Router 6

**Infraestrutura:** Docker & Docker Compose, Prometheus, Grafana, Flower

## Licenca

MIT
