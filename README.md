# 🎯 Analisador de Currículos (On-Premises)

Sistema completo de RH on-premises para ingestão, análise, indexação vetorial e busca inteligente de currículos.

## ✨ Funcionalidades Implementadas

### Backend (FastAPI)
- ✅ **Autenticação JWT** com RBAC completo
- ✅ **Upload de currículos** (PDF, DOCX, TXT, imagens com OCR)
- ✅ **Processamento assíncrono** com Celery
- ✅ **WebSocket** para atualizações em tempo real
- ✅ **Busca semântica** com embeddings OpenAI
- ✅ **Busca híbrida** (semântica + texto completo + filtros)
- ✅ **LinkedIn integration** para enriquecimento de perfis
- ✅ **LGPD compliance** com auditoria completa
- ✅ **Configurações dinâmicas** e prompts LLM customizáveis
- ✅ **API documentada** com OpenAPI/Swagger

### Frontend (React + TypeScript)
- ✅ **Interface completa** em Material-UI
- ✅ **Dashboard** com estatísticas e métricas
- ✅ **Gerenciamento de candidatos** (CRUD completo)
- ✅ **Upload com drag & drop** e progresso em tempo real
- ✅ **Busca inteligente** com highlight de resultados
- ✅ **Administração** de funções e permissões
- ✅ **Configurações** do sistema
- ✅ **WebSocket** para notificações instantâneas

### Infraestrutura
- ✅ **Docker Compose** completo com 8 serviços
- ✅ **Celery** para processamento em background
- ✅ **Flower** para monitoramento de tarefas
- ✅ **Prometheus** para coleta de métricas
- ✅ **Grafana** com dashboards customizados
- ✅ **PostgreSQL** com pgvector
- ✅ **Redis** para cache e filas

## Entregas por etapa

1. ✅ **Etapa 1**: Arquitetura, modelo de dados e fluxos do pipeline
2. ✅ **Etapa 2**: Scaffold do repositório + docker-compose
3. ✅ **Etapa 3**: Ingestão + OCR + jobs + UI de progresso
4. ✅ **Etapa 4**: Indexação vetorial + busca híbrida + filtros
5. ✅ **Etapa 5**: Chat RAG + evidências + prompts configuráveis
6. ✅ **Etapa 6**: RBAC + auditoria + LGPD + console admin
7. ✅ **Etapa 7**: Frontend React + WebSocket + Monitoramento

## 📁 Estrutura do Projeto

```
analisador-curriculos/
├── backend/              # API FastAPI
│   ├── app/
│   │   ├── api/         # Endpoints REST
│   │   ├── core/        # Configuração e segurança
│   │   ├── db/          # Modelos e migrations
│   │   ├── schemas/     # Validação Pydantic
│   │   ├── services/    # Lógica de negócio
│   │   └── tasks/       # Tarefas Celery
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/            # Interface React
│   ├── src/
│   │   ├── components/  # Componentes reutilizáveis
│   │   ├── contexts/    # Contextos React
│   │   ├── pages/       # Páginas da aplicação
│   │   ├── services/    # API e WebSocket clients
│   │   └── types/       # TypeScript types
│   ├── package.json
│   └── Dockerfile
├── monitoring/          # Prometheus e Grafana
│   ├── prometheus.yml
│   └── grafana/
│       ├── dashboards/
│       └── datasources/
├── docs/               # Documentação
│   ├── arquitetura.md
│   ├── modelo_dados.md
│   └── novas_implementacoes.md
└── docker-compose.yml  # Orquestração completa
```

## 🚀 Quick Start

### Iniciar todos os serviços (Recomendado)

```bash
# 1. Clonar repositório
git clone https://github.com/ZerocouldBR/Analisador_de_curriculos.git
cd Analisador_de_curriculos

# 2. Configurar ambiente
cp backend/.env.example backend/.env
# Edite backend/.env com suas configurações

# 3. Iniciar stack completa
docker-compose up -d

# 4. Verificar status
docker-compose ps

# 5. Ver logs
docker-compose logs -f
```

### Acessar serviços

| Serviço | URL | Descrição |
|---------|-----|-----------|
| **Frontend** | http://localhost:3000 | Interface React |
| **API** | http://localhost:8000 | Backend FastAPI |
| **API Docs** | http://localhost:8000/docs | Swagger UI |
| **Flower** | http://localhost:5555 | Monitor Celery |
| **Prometheus** | http://localhost:9090 | Métricas |
| **Grafana** | http://localhost:3001 | Dashboards (admin/admin) |

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

## 📖 Documentação

- [Arquitetura do Sistema](docs/arquitetura.md)
- [Modelo de Dados](docs/modelo_dados.md)
- [Novas Implementações](docs/novas_implementacoes.md)
- [Frontend README](frontend/README.md)
- [Backend README](backend/README.md)

## 🎯 Principais Funcionalidades

### 1. Upload de Currículos com Progresso em Tempo Real
- Drag & drop de arquivos
- Suporte a múltiplos formatos (PDF, DOCX, TXT, imagens)
- OCR automático para imagens
- Progresso em tempo real via WebSocket
- Processamento assíncrono com Celery

### 2. Busca Inteligente
- **Busca semântica** usando embeddings OpenAI
- **Busca híbrida** combinando:
  - 40% similaridade semântica
  - 30% busca de texto completo
  - 20% filtros estruturados
  - 10% domínio de conhecimento
- Highlight de trechos relevantes
- Score de relevância

### 3. Gerenciamento de Candidatos
- CRUD completo
- Perfis detalhados
- Histórico de documentos
- Filtros por localização

### 4. Monitoramento
- Dashboard com métricas em tempo real
- Grafana com visualizações customizadas
- Prometheus para coleta de métricas
- Flower para monitorar tarefas Celery

### 5. Segurança e Compliance
- Autenticação JWT
- RBAC com permissões granulares
- Auditoria completa de operações
- LGPD compliance

## 🛠️ Tecnologias

**Backend:**
- FastAPI 0.115
- PostgreSQL 16 + pgvector
- Redis 7
- Celery 5.3
- OpenAI API (embeddings)
- Tesseract OCR

**Frontend:**
- React 18
- TypeScript 5
- Material-UI 5
- Axios
- WebSocket
- React Router 6

**Infraestrutura:**
- Docker & Docker Compose
- Prometheus
- Grafana
- Flower

## 🔧 Configuração

### Variáveis de Ambiente

**Backend (`.env`):**
```env
APP_VERSION=0.3.0
DATABASE_URL=postgresql+psycopg://analisador:analisador@db:5432/analisador_curriculos
REDIS_URL=redis://redis:6379/0
SECRET_KEY=your-secret-key-here
OPENAI_API_KEY=sk-... (opcional)
```

**Frontend (`.env`):**
```env
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000
```

## 🧪 Testes

```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm test
```

## 📊 Monitoramento

### Prometheus
Acesse http://localhost:9090 para queries de métricas.

### Grafana
1. Acesse http://localhost:3001
2. Login: admin/admin
3. Dashboard "Analisador de Currículos - System Dashboard"

Métricas disponíveis:
- Taxa de requisições da API
- Tempo de resposta (p95, p99)
- Tarefas Celery ativas
- Taxa de sucesso de tarefas
- Conexões do banco de dados
- Uso de memória do Redis
- Upload rate
- WebSocket connections

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch (`git checkout -b feature/nova-funcionalidade`)
3. Commit suas mudanças (`git commit -m 'Add nova funcionalidade'`)
4. Push para a branch (`git push origin feature/nova-funcionalidade`)
5. Abra um Pull Request

## 📝 Licença

MIT
