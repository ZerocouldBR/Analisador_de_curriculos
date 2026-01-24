# Backend API (FastAPI)

Sistema de análise de currículos com IA, configuração de prompts LLM e integração com LinkedIn.

## 🚀 Início Rápido

### Executar com Docker Compose (Recomendado)

```bash
# Copiar arquivo de configuração
cp .env.example .env

# Subir todos os serviços (API, PostgreSQL, Redis)
cd ..
docker compose up --build
```

A API estará disponível em: http://localhost:8000

### Executar localmente

```bash
# Criar ambiente virtual
python -m venv .venv
source .venv/bin/activate  # No Windows: .venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
cp .env.example .env
# Edite o .env conforme necessário

# Inicializar banco de dados
python -m app.db.init_db

# Iniciar servidor
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 📚 Documentação da API

Após iniciar o servidor, acesse:

- **Swagger UI (interativo):** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **OpenAPI JSON:** http://localhost:8000/openapi.json

## 🎯 Novas Funcionalidades

### 1. Configuração de Prompts do Chat LLM

Configure e personalize os prompts usados pelo assistente de IA:

```bash
# Obter configuração atual
GET /api/v1/settings/prompts/chat

# Atualizar prompts
PUT /api/v1/settings/prompts/chat

# Restaurar padrão
POST /api/v1/settings/prompts/chat/reset
```

### 2. Gerenciamento de Currículos

Gerencie candidatos e currículos com remoção completa (LGPD-compliant):

```bash
# Listar candidatos
GET /api/v1/candidates/

# Criar candidato
POST /api/v1/candidates/

# Listar currículos de um candidato
GET /api/v1/candidates/{id}/documents

# Remover currículo específico
DELETE /api/v1/candidates/documents/{document_id}

# Remover candidato completo
DELETE /api/v1/candidates/{id}
```

### 3. Integração com LinkedIn

Enriqueça perfis de candidatos com dados do LinkedIn:

```bash
# Extrair perfil público (experimental)
POST /api/v1/linkedin/extract

# Adicionar dados manualmente
POST /api/v1/linkedin/candidates/{id}/manual

# Obter dados do LinkedIn
GET /api/v1/linkedin/candidates/{id}/linkedin

# Sincronizar candidato
PUT /api/v1/linkedin/candidates/{id}/sync-from-linkedin
```

## 🗄️ Banco de Dados

### Inicializar banco de dados

```bash
python -m app.db.init_db
```

### Remover todas as tabelas (⚠️ CUIDADO!)

```bash
python -m app.db.init_db --drop
```

### Extensões PostgreSQL Necessárias

- **pgvector**: Para armazenar embeddings vetoriais

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

## 🧪 Testar a API

### Endpoint de saúde

```bash
curl http://localhost:8000/api/health
```

### Criar um candidato

```bash
curl -X POST "http://localhost:8000/api/v1/candidates/" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "João Silva",
    "email": "joao@email.com",
    "city": "São Paulo",
    "state": "SP"
  }'
```

### Configurar prompts do chat

```bash
curl -X PUT "http://localhost:8000/api/v1/settings/prompts/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "system_prompt": "Você é um assistente de RH focado em tecnologia...",
    "temperature": 0.5
  }'
```

## 🔧 Configuração

Edite o arquivo `.env`:

```env
# Aplicação
APP_VERSION=0.2.0
LOG_LEVEL=INFO

# Banco de Dados PostgreSQL
DATABASE_URL=postgresql+psycopg://analisador:analisador@db:5432/analisador_curriculos

# Redis
REDIS_URL=redis://redis:6379/0

# OpenAI (futuro)
# OPENAI_API_KEY=sk-...
```

## 📦 Dependências Principais

- **FastAPI**: Framework web assíncrono
- **SQLAlchemy**: ORM para PostgreSQL
- **Pydantic**: Validação de dados
- **pgvector**: Embeddings vetoriais
- **httpx**: Cliente HTTP assíncrono
- **BeautifulSoup**: Parsing de HTML

## 🔒 Segurança e LGPD

- ✅ Auditoria completa de todas as operações
- ✅ Remoção em cascata de dados relacionados
- ✅ Separação de PII (Personally Identifiable Information)
- ✅ Logs de auditoria imutáveis
- ✅ Políticas de retenção de dados

## 📖 Documentação Adicional

- [Novas Funcionalidades](../docs/novas_funcionalidades.md)
- [Arquitetura](../docs/arquitetura.md)
- [Modelo de Dados](../docs/modelo_dados.md)
- [Fluxos](../docs/fluxos.md)

## 🛠️ Desenvolvimento

### Estrutura de Diretórios

```
backend/
├── app/
│   ├── api/
│   │   └── v1/          # Endpoints da API
│   ├── core/            # Configurações
│   ├── db/              # Modelos e database
│   ├── schemas/         # Schemas Pydantic
│   └── services/        # Lógica de negócio
├── requirements.txt
└── Dockerfile
```

### Adicionar nova funcionalidade

1. Criar schema em `app/schemas/`
2. Adicionar lógica em `app/services/`
3. Criar endpoints em `app/api/v1/`
4. Registrar router em `app/api/routes.py`
5. Atualizar documentação

## 📝 TODO

- [ ] Implementar autenticação JWT
- [ ] Adicionar RBAC (Role-Based Access Control)
- [ ] Implementar upload de currículos
- [ ] Adicionar OCR para PDFs/imagens
- [ ] Integrar com API oficial do LinkedIn
- [ ] Implementar busca semântica com embeddings
- [ ] Adicionar testes unitários
- [ ] Implementar processamento assíncrono com Celery
