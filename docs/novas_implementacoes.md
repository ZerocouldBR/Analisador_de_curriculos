# Novas Implementações - Sistema de Análise de Currículos

Documentação das funcionalidades implementadas para expandir o sistema de análise de currículos.

## 📋 Índice

1. [Processamento Assíncrono com Celery](#processamento-assíncrono-com-celery)
2. [WebSocket para Atualizações em Tempo Real](#websocket-para-atualizações-em-tempo-real)
3. [Frontend React](#frontend-react)
4. [Orquestração com Docker Compose](#orquestração-com-docker-compose)
5. [Monitoramento com Prometheus e Grafana](#monitoramento-com-prometheus-e-grafana)

---

## ⚡ Processamento Assíncrono com Celery

### Visão Geral

Implementamos **Celery** para processamento assíncrono de uploads de currículos, permitindo que o sistema:

- Processe documentos em background sem bloquear a API
- Escale horizontalmente adicionando mais workers
- Gerencie filas de tarefas por prioridade
- Retry automático em caso de falhas

### Arquitetura

```
Upload → FastAPI → Celery Broker (Redis) → Celery Worker → Banco de Dados
                                          ↓
                                    WebSocket ← Progresso em tempo real
```

### Componentes

#### 1. Celery App (`backend/app/core/celery_app.py`)

```python
celery_app = Celery(
    "analisador_curriculos",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.document_tasks"]
)
```

**Configurações:**
- Serialização: JSON
- Timezone: America/Sao_Paulo
- Time limit: 5 minutos por tarefa
- Result expiration: 1 hora
- Task tracking habilitado para progresso

#### 2. Tasks de Processamento (`backend/app/tasks/document_tasks.py`)

**Task: `process_document_task`**

Fluxo de execução:
1. ✅ Carrega documento do banco de dados
2. ✅ Extrai texto (PDF, DOCX, OCR para imagens)
3. ✅ Normaliza e limpa texto
4. ✅ Parse estruturado (nome, email, experiências, skills)
5. ✅ Cria chunks por seção
6. ✅ Atualiza candidato com informações extraídas
7. ✅ Registra auditoria
8. ✅ Envia progresso via WebSocket

**Progresso reportado:**
- 0%: Iniciando
- 10%: Documento carregado
- 20%: Extraindo texto
- 40%: Texto extraído
- 50%: Normalizando
- 60%: Parseando currículo
- 70%: Criando chunks
- 90%: Chunks criados
- 100%: Concluído

### Configuração

**Dependências (`requirements.txt`):**
```
celery==5.3.4
flower==2.0.1
redis==5.0.1
```

**Docker Compose:**
```yaml
celery-worker:
  build:
    context: ./backend
  command: celery -A app.core.celery_app worker --loglevel=info --queues=documents,search --concurrency=4
  depends_on:
    - redis
    - db
```

### Uso

**Enfileirar tarefa:**
```python
from app.tasks.document_tasks import process_document_task

# Assíncrono
task = process_document_task.delay(document_id, user_id)

# Obter resultado
result = task.get(timeout=300)
```

### Monitoramento

**Flower UI:** http://localhost:5555

- Visualizar tarefas ativas
- Taxa de sucesso/falha
- Workers conectados
- Latência de processamento

---

## 📡 WebSocket para Atualizações em Tempo Real

### Visão Geral

Sistema de WebSocket para notificações em tempo real sobre processamento de documentos.

### Arquitetura

```
Frontend → WebSocket Connection → FastAPI WebSocket → WebSocket Manager
                                                      ↓
                                              Celery Task → Send Progress
```

### Componentes

#### 1. WebSocket Manager (`backend/app/core/websocket_manager.py`)

Gerencia conexões e broadcasts:

```python
class WebSocketManager:
    - active_connections: Dict[user_id, List[WebSocket]]
    - document_subscriptions: Dict[document_id, List[user_id]]

    async def connect(websocket, user_id)
    async def disconnect(websocket, user_id)
    async def subscribe_document(document_id, user_id)
    async def send_document_progress(document_id, status, progress, message)
```

#### 2. WebSocket Endpoint (`backend/app/api/v1/websocket.py`)

**Endpoint:** `ws://localhost:8000/api/v1/ws?token=<jwt_token>`

**Mensagens recebidas do cliente:**
```json
{
  "action": "subscribe_document",
  "document_id": 123
}
```

**Mensagens enviadas ao cliente:**
```json
{
  "type": "document_progress",
  "document_id": 123,
  "status": "processing",
  "progress": 50,
  "message": "Analisando estrutura do currículo"
}
```

### Protocolo

**Estados de processamento:**
- `started`: Iniciado
- `processing`: Em processamento
- `completed`: Concluído com sucesso
- `error`: Erro no processamento

### Uso no Frontend

```typescript
import { websocketService } from './services/websocket';

// Conectar
websocketService.connect(token);

// Subscrever documento
websocketService.subscribeDocument(documentId);

// Escutar progresso
websocketService.on('document_progress', (message) => {
  console.log(`${message.progress}%: ${message.message}`);
});
```

### Segurança

- ✅ Autenticação via JWT token
- ✅ Validação de permissões por usuário
- ✅ Reconexão automática
- ✅ Heartbeat (ping/pong)

---

## 🎨 Frontend React

### Visão Geral

Interface visual completa em React + TypeScript + Material-UI para todas as funcionalidades do sistema.

### Stack Tecnológico

- **React 18** - Framework UI
- **TypeScript** - Tipagem estática
- **Material-UI (MUI)** - Componentes
- **React Router** - Navegação
- **Axios** - HTTP Client
- **WebSocket** - Tempo real
- **React Dropzone** - Upload de arquivos

### Estrutura de Páginas

| Página | Rota | Funcionalidade |
|--------|------|----------------|
| Login | `/login` | Autenticação JWT |
| Register | `/register` | Cadastro de usuários |
| Dashboard | `/dashboard` | Visão geral e estatísticas |
| Candidatos | `/candidates` | CRUD de candidatos |
| Detalhes | `/candidates/:id` | Perfil completo do candidato |
| Upload | `/upload` | Upload com progresso em tempo real |
| Busca | `/search` | Busca semântica e híbrida |
| Configurações | `/settings` | Configurações do sistema |
| Funções | `/roles` | Gerenciamento RBAC |

### Funcionalidades Implementadas

#### 1. Autenticação
- ✅ Login com email e senha
- ✅ Registro de novos usuários
- ✅ Token JWT em localStorage
- ✅ Proteção de rotas
- ✅ Auto-refresh de token
- ✅ Logout

#### 2. Dashboard
- ✅ Cards de estatísticas
  - Total de candidatos
  - Total de documentos
  - Uploads recentes
  - Processados hoje
- ✅ Lista de candidatos recentes
- ✅ Feed de atividades

#### 3. Gerenciamento de Candidatos
- ✅ DataGrid com paginação
- ✅ Filtros por cidade/estado
- ✅ Criar candidato
- ✅ Editar candidato
- ✅ Excluir candidato (com confirmação)
- ✅ Ver detalhes
- ✅ Listagem de documentos do candidato

#### 4. Upload de Currículos ⭐
- ✅ Drag & drop de arquivos
- ✅ Múltiplos formatos (PDF, DOCX, TXT, imagens)
- ✅ Preview de arquivos
- ✅ Seleção de candidato existente ou criação automática
- ✅ **Progresso em tempo real via WebSocket**
  - Barra de progresso animada
  - Status atual (uploading, processing, completed, error)
  - Mensagens de cada etapa
- ✅ Upload paralelo de múltiplos arquivos
- ✅ Indicadores visuais de status
- ✅ Tratamento de erros

#### 5. Busca Inteligente
- ✅ Busca semântica com embeddings
- ✅ Busca híbrida (semântica + texto completo)
- ✅ Exibição de trechos relevantes
- ✅ Score de similaridade
- ✅ Highlight de matches
- ✅ Navegação para perfil do candidato

#### 6. Configurações
- ✅ Listagem de configurações do sistema
- ✅ Edição de valores JSON
- ✅ Versionamento de configurações
- ✅ Histórico de alterações
- ✅ Editor de prompts LLM

#### 7. Gerenciamento de Funções (RBAC)
- ✅ Criação de funções
- ✅ Edição de permissões
- ✅ Visualização de permissões ativas
- ✅ Atribuição de funções a usuários
- ✅ Chips visuais para permissões

### Componentes Principais

#### Layout (`components/Layout.tsx`)
- Sidebar responsivo
- AppBar com informações do usuário
- Menu de navegação
- Logout

#### AuthContext (`contexts/AuthContext.tsx`)
- Gerenciamento de estado de autenticação
- Métodos de login/logout
- Proteção de rotas
- WebSocket connection management

#### API Service (`services/api.ts`)
- Cliente Axios configurado
- Interceptors para JWT
- Métodos para todas as operações CRUD
- Tratamento de erros

#### WebSocket Service (`services/websocket.ts`)
- Conexão WebSocket
- Gerenciamento de listeners
- Auto-reconnect
- Subscrição de eventos

### Responsividade

- ✅ Layout adaptativo mobile/tablet/desktop
- ✅ Sidebar colapsável
- ✅ DataGrid responsivo
- ✅ Formulários otimizados para touch

### Temas

Material-UI com tema customizado:
- Cores primárias: Azul (#1976d2)
- Cores secundárias: Rosa (#dc004e)
- Modo claro (dark mode pode ser adicionado)

---

## 🚀 Orquestração com Docker Compose

### Visão Geral

Sistema completo orquestrado com Docker Compose, incluindo todos os serviços necessários.

### Arquitetura Completa

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Frontend  │────▶│   FastAPI   │────▶│  PostgreSQL │
│  React:3000 │     │   API:8000  │     │     :5432   │
└─────────────┘     └─────────────┘     └─────────────┘
                           │                    │
                           ▼                    │
                    ┌─────────────┐             │
                    │    Redis    │◀────────────┘
                    │    :6379    │
                    └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Celery    │
                    │   Worker    │
                    └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Flower    │
                    │    :5555    │
                    └─────────────┘

┌─────────────┐     ┌─────────────┐
│ Prometheus  │────▶│   Grafana   │
│    :9090    │     │    :3001    │
└─────────────┘     └─────────────┘
```

### Serviços

#### 1. **db** - PostgreSQL 16
```yaml
ports: ["5432:5432"]
volumes: [postgres_data:/var/lib/postgresql/data]
healthcheck: pg_isready
```

#### 2. **redis** - Redis 7
```yaml
ports: ["6379:6379"]
volumes: [redis_data:/data]
healthcheck: redis-cli ping
```

#### 3. **api** - FastAPI Backend
```yaml
ports: ["8000:8000"]
depends_on: [db, redis]
volumes: [./backend/uploads:/app/uploads]
```

#### 4. **celery-worker** - Processamento Assíncrono
```yaml
command: celery -A app.core.celery_app worker --loglevel=info --queues=documents,search --concurrency=4
depends_on: [db, redis]
```

#### 5. **flower** - Monitoramento Celery
```yaml
ports: ["5555:5555"]
command: celery -A app.core.celery_app flower
```

#### 6. **prometheus** - Métricas
```yaml
ports: ["9090:9090"]
volumes: [./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml]
```

#### 7. **grafana** - Dashboards
```yaml
ports: ["3001:3000"]
volumes: [grafana_data:/var/lib/grafana]
environment:
  GF_SECURITY_ADMIN_USER: admin
  GF_SECURITY_ADMIN_PASSWORD: admin
```

#### 8. **frontend** - React UI
```yaml
ports: ["3000:3000"]
environment:
  REACT_APP_API_URL: http://localhost:8000
  REACT_APP_WS_URL: ws://localhost:8000
```

### Volumes Persistentes

- `postgres_data`: Dados do PostgreSQL
- `redis_data`: Dados do Redis
- `prometheus_data`: Métricas do Prometheus
- `grafana_data`: Dashboards e configurações do Grafana

### Comandos

```bash
# Iniciar todos os serviços
docker-compose up -d

# Ver logs
docker-compose logs -f

# Ver logs de um serviço específico
docker-compose logs -f api

# Parar todos os serviços
docker-compose down

# Rebuild e restart
docker-compose up -d --build

# Limpar tudo (cuidado: apaga volumes!)
docker-compose down -v
```

### Healthchecks

Todos os serviços críticos possuem healthchecks:

- **PostgreSQL**: `pg_isready -U analisador`
- **Redis**: `redis-cli ping`
- **API**: Depende de db e redis estarem healthy

### Redes

Todos os serviços compartilham a mesma rede Docker, permitindo comunicação entre eles usando nomes de serviço:

- `db`: PostgreSQL
- `redis`: Redis
- `api`: FastAPI
- `prometheus`: Prometheus
- etc.

---

## 📈 Monitoramento com Prometheus e Grafana

### Visão Geral

Sistema completo de monitoramento e observabilidade com métricas em tempo real.

### Arquitetura

```
FastAPI (Prometheus Client) → Prometheus (Scraper) → Grafana (Visualização)
Celery (Flower)            ↗
Redis                     ↗
```

### Prometheus

#### Configuração (`monitoring/prometheus.yml`)

**Jobs configurados:**

1. **fastapi** - Métricas da API
   - Request rate
   - Response time (p50, p95, p99)
   - Status codes
   - Endpoints mais usados

2. **celery** - Métricas do Celery via Flower
   - Tarefas ativas
   - Taxa de sucesso/falha
   - Tempo de execução
   - Fila de tarefas

3. **redis** - Métricas do Redis
   - Uso de memória
   - Conexões ativas
   - Hit rate do cache

4. **postgres** - Métricas do PostgreSQL
   - Conexões ativas
   - Queries por segundo
   - Cache hit ratio

#### Métricas do FastAPI

**Instrumentação automática:**
```python
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app, endpoint="/metrics")
```

**Métricas disponíveis:**
- `http_requests_total` - Total de requisições
- `http_request_duration_seconds` - Duração das requisições
- `http_requests_in_progress` - Requisições em andamento
- `http_request_size_bytes` - Tamanho das requisições
- `http_response_size_bytes` - Tamanho das respostas

**Endpoint:** http://localhost:8000/metrics

### Grafana

#### Acesso
- **URL:** http://localhost:3001
- **Usuário:** admin
- **Senha:** admin

#### Datasources

**Prometheus** configurado automaticamente:
- URL: http://prometheus:9090
- Scrape interval: 15s
- Default datasource

#### Dashboards

**Dashboard Principal** (`monitoring/grafana/dashboards/analisador-dashboard.json`):

1. **API Request Rate**
   - Requisições por segundo
   - Breakdown por método HTTP
   - Breakdown por endpoint

2. **API Response Time**
   - Percentil 95 e 99
   - Média de resposta
   - Gráfico de linha temporal

3. **Celery Active Tasks**
   - Tarefas em execução
   - Stat panel com contador

4. **Celery Task Success Rate**
   - Taxa de sucesso vs falha
   - Gauge com thresholds:
     - Verde: > 95%
     - Amarelo: 80-95%
     - Vermelho: < 80%

5. **Database Connections**
   - Conexões ativas no PostgreSQL
   - Stat panel

6. **Redis Memory Usage**
   - Uso de memória em MB
   - Stat panel

7. **Document Upload Rate**
   - Uploads por segundo
   - Gráfico de linha

8. **Document Processing Duration**
   - Tempo médio de processamento
   - Percentil 95 e 99

9. **WebSocket Connections**
   - Conexões WebSocket ativas
   - Stat panel

10. **Total Candidates & Documents**
    - Contadores totais
    - Stat panels

#### Alertas (Configuração Futura)

Alertas sugeridos:
- Taxa de erro > 5%
- Response time p95 > 2s
- Celery success rate < 90%
- Redis memory > 80%
- PostgreSQL connections > 80%

### Métricas Customizadas

**Adicionar métricas customizadas:**

```python
from prometheus_client import Counter, Histogram, Gauge

# Contador de uploads
upload_counter = Counter(
    'document_uploads_total',
    'Total de uploads de documentos'
)

# Tempo de processamento
processing_duration = Histogram(
    'document_processing_duration_seconds',
    'Duração do processamento de documentos'
)

# Documentos ativos
active_documents = Gauge(
    'total_documents',
    'Total de documentos no sistema'
)

# Uso
upload_counter.inc()
with processing_duration.time():
    # processo aqui
    pass
active_documents.set(count)
```

### Monitoramento de Performance

**Métricas chave para observar:**

1. **Latência da API**
   - p50 < 100ms
   - p95 < 500ms
   - p99 < 1s

2. **Taxa de Sucesso**
   - > 99% de requisições bem-sucedidas
   - < 1% de erros 5xx

3. **Processamento de Documentos**
   - Tempo médio < 30s
   - Taxa de sucesso > 95%

4. **Recursos**
   - CPU < 70%
   - Memória < 80%
   - Disco < 85%

---

## 🔧 Configuração e Deploy

### Pré-requisitos

- Docker 20+
- Docker Compose 2+
- Node.js 18+ (para desenvolvimento local do frontend)
- Python 3.11+ (para desenvolvimento local do backend)

### Instalação Completa

```bash
# 1. Clonar repositório
git clone https://github.com/ZerocouldBR/Analisador_de_curriculos.git
cd Analisador_de_curriculos

# 2. Configurar variáveis de ambiente
cp backend/.env.example backend/.env
# Editar backend/.env com suas configurações

# 3. Iniciar todos os serviços
docker-compose up -d

# 4. Verificar logs
docker-compose logs -f

# 5. Acessar serviços
# Frontend: http://localhost:3000
# API: http://localhost:8000
# API Docs: http://localhost:8000/docs
# Flower: http://localhost:5555
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3001
```

### Desenvolvimento Local

**Backend:**
```bash
cd backend
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

### Variáveis de Ambiente

**Backend (`.env`):**
```env
APP_VERSION=0.3.0
LOG_LEVEL=INFO
DATABASE_URL=postgresql+psycopg://analisador:analisador@db:5432/analisador_curriculos
REDIS_URL=redis://redis:6379/0
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
OPENAI_API_KEY=your-openai-key (opcional)
```

**Frontend (`.env`):**
```env
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000
```

### Produção

**Considerações para produção:**

1. **Segurança**
   - Trocar SECRET_KEY
   - Usar HTTPS/WSS
   - Configurar CORS adequadamente
   - Habilitar autenticação no Grafana
   - Firewall para Prometheus

2. **Performance**
   - Aumentar workers do Celery
   - Configurar Redis persistence
   - PostgreSQL tuning
   - Frontend com CDN
   - Load balancer

3. **Backup**
   - Backup regular do PostgreSQL
   - Backup de volumes Docker
   - Backup de configurações

4. **Monitoramento**
   - Alertas configurados
   - Logs centralizados
   - Métricas de negócio

---

## 📊 Fluxo Completo

### Upload de Currículo com Progresso em Tempo Real

```
1. Usuário seleciona arquivo no frontend
   └─▶ React Dropzone

2. Frontend faz upload via API
   └─▶ POST /api/v1/documents/upload

3. API salva arquivo e cria registro
   └─▶ DocumentService.upload_resume()

4. API enfileira processamento no Celery
   └─▶ process_document_task.delay(document_id)
   └─▶ Retorna documento para frontend

5. Frontend subscreve WebSocket
   └─▶ websocketService.subscribeDocument(documentId)

6. Celery Worker processa documento
   ├─▶ 0%: Iniciando
   ├─▶ 20%: Extraindo texto
   ├─▶ 40%: Texto extraído
   ├─▶ 60%: Parseando currículo
   ├─▶ 70%: Criando chunks
   ├─▶ 90%: Chunks criados
   └─▶ 100%: Concluído

7. A cada etapa, worker envia progresso
   └─▶ websocket_manager.send_document_progress()

8. WebSocket Manager faz broadcast
   └─▶ Para todos os usuários subscritos

9. Frontend recebe e atualiza UI
   ├─▶ Barra de progresso
   ├─▶ Mensagem de status
   └─▶ Ícone de status

10. Conclusão
    └─▶ Documento processado e disponível para busca
```

---

## 🧪 Testes

### Backend

```bash
# Testes unitários
cd backend
pytest

# Com cobertura
pytest --cov=app --cov-report=html

# Testes específicos
pytest tests/test_auth.py
```

### Frontend

```bash
# Testes
cd frontend
npm test

# Cobertura
npm test -- --coverage
```

### Testes de Integração

```bash
# Iniciar ambiente de teste
docker-compose -f docker-compose.test.yml up -d

# Executar testes
pytest tests/integration/

# Limpar
docker-compose -f docker-compose.test.yml down -v
```

---

## 📝 Conclusão

Este sistema agora possui:

✅ **Processamento Assíncrono** - Celery com múltiplos workers
✅ **Atualizações em Tempo Real** - WebSocket para progresso
✅ **Interface Visual Completa** - React + TypeScript + Material-UI
✅ **Orquestração Completa** - Docker Compose com 8 serviços
✅ **Monitoramento Avançado** - Prometheus + Grafana com dashboards

O sistema está pronto para produção e pode escalar horizontalmente adicionando mais workers, instâncias da API, e recursos de banco de dados conforme necessário.
