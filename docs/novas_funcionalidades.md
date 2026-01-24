# Novas Funcionalidades - Sistema de Análise de Currículos

## 1. Configuração de Prompts do Chat LLM

### Descrição
Sistema completo para gerenciar e personalizar os prompts utilizados pelo chat LLM (GPT-4/OpenAI).

### Endpoints Disponíveis

#### Obter Configuração Atual de Prompts
```http
GET /v1/settings/prompts/chat
```

**Resposta:**
```json
{
  "system_prompt": "Você é um assistente de RH...",
  "user_prompt_template": "Com base nos currículos disponíveis, {query}...",
  "temperature": 0.7,
  "max_tokens": 1000,
  "model": "gpt-4-turbo-preview"
}
```

#### Atualizar Prompts do Chat
```http
PUT /v1/settings/prompts/chat
```

**Body:**
```json
{
  "system_prompt": "Novo prompt do sistema...",
  "temperature": 0.5,
  "max_tokens": 1500
}
```

#### Restaurar Prompts Padrão
```http
POST /v1/settings/prompts/chat/reset
```

### Configurações Disponíveis

- **system_prompt**: Prompt do sistema que define o comportamento do assistente
- **user_prompt_template**: Template para formatar perguntas dos usuários (use `{query}` como placeholder)
- **temperature**: Controla aleatoriedade (0.0 = determinístico, 2.0 = muito criativo)
- **max_tokens**: Número máximo de tokens na resposta
- **model**: Modelo do OpenAI a usar (ex: gpt-4-turbo-preview, gpt-3.5-turbo)

### Exemplos de Uso

**Tornar o assistente mais focado em hard skills:**
```json
{
  "system_prompt": "Você é um especialista técnico em RH. Priorize hard skills e experiências técnicas ao analisar currículos. Seja objetivo e direto."
}
```

**Tornar respostas mais criativas:**
```json
{
  "temperature": 1.2
}
```

---

## 2. Remoção de Currículos

### Descrição
Sistema completo para remoção de candidatos e currículos, com cascata automática e auditoria LGPD-compliant.

### Endpoints Disponíveis

#### Remover Candidato Completo
```http
DELETE /v1/candidates/{candidate_id}
```

**O que é removido:**
- Dados pessoais do candidato
- Todos os currículos/documentos
- Chunks extraídos dos documentos
- Embeddings vetoriais
- Experiências profissionais
- Dados de enriquecimento (LinkedIn, etc.)
- Consentimentos LGPD

**⚠️ Esta operação é irreversível!**

Um log de auditoria é criado antes da remoção para compliance com LGPD.

#### Remover Currículo Específico
```http
DELETE /v1/candidates/documents/{document_id}
```

**O que é removido:**
- O documento/currículo
- Todos os chunks extraídos
- Todos os embeddings gerados

O candidato permanece no sistema com seus outros currículos (se existirem).

#### Listar Currículos de um Candidato
```http
GET /v1/candidates/{candidate_id}/documents
```

**Resposta:**
```json
[
  {
    "id": 1,
    "candidate_id": 123,
    "original_filename": "curriculo_joao.pdf",
    "mime_type": "application/pdf",
    "source_path": "/storage/curriculos/abc123.pdf",
    "sha256_hash": "d2d2...",
    "uploaded_at": "2024-01-15T10:30:00"
  }
]
```

### Auditoria e LGPD

Todas as remoções são registradas na tabela `audit_logs` com:
- Usuário que executou a ação
- Timestamp da operação
- Dados removidos (resumo)
- Motivo da remoção (se fornecido)

---

## 3. Análise de Perfis do LinkedIn

### Descrição
Sistema para enriquecer dados de candidatos com informações do LinkedIn.

### Endpoints Disponíveis

#### Extrair Dados de Perfil Público (Experimental)
```http
POST /v1/linkedin/extract
```

**Body:**
```json
{
  "profile_url": "https://www.linkedin.com/in/joao-silva/"
}
```

**Resposta:**
```json
{
  "profile_url": "https://www.linkedin.com/in/joao-silva/",
  "full_name": "João Silva",
  "headline": "Senior Software Engineer",
  "location": "São Paulo, SP",
  "about": "Engenheiro com 10 anos de experiência...",
  "experiences": [...],
  "education": [...],
  "skills": ["Python", "JavaScript", "AWS"],
  "certifications": [...],
  "languages": [...]
}
```

**⚠️ IMPORTANTE:** Esta funcionalidade é experimental. Em produção, use:
- API oficial do LinkedIn
- Serviços terceirizados autorizados (PhantomBuster, Apify)
- Conformidade com termos de serviço e LGPD

#### Enriquecer Candidato com LinkedIn
```http
POST /v1/linkedin/candidates/{candidate_id}/enrich
```

**Body:**
```json
{
  "profile_url": "https://www.linkedin.com/in/joao-silva/",
  "full_name": "João Silva",
  "headline": "Senior Software Engineer",
  "location": "São Paulo, SP",
  "about": "...",
  "experiences": [...],
  "skills": [...]
}
```

**Query Parameter:**
- `update_candidate=true`: Atualiza informações do candidato (nome, cidade, estado)

#### Adicionar Dados Manualmente
```http
POST /v1/linkedin/candidates/{candidate_id}/manual
```

**Body:**
```json
{
  "profile_url": "https://www.linkedin.com/in/joao-silva/",
  "full_name": "João Silva",
  "headline": "Senior Software Engineer",
  "skills": ["Python", "AWS", "Docker"]
}
```

Útil quando você já possui os dados ou a extração automática não está disponível.

#### Obter Dados do LinkedIn de um Candidato
```http
GET /v1/linkedin/candidates/{candidate_id}/linkedin
```

**Resposta:**
```json
{
  "id": 1,
  "candidate_id": 123,
  "source": "linkedin",
  "source_url": "https://www.linkedin.com/in/joao-silva/",
  "data_json": {
    "full_name": "João Silva",
    "skills": ["Python", "AWS"]
  },
  "fetched_at": "2024-01-15T10:30:00",
  "retention_policy": "90_days"
}
```

#### Sincronizar Candidato com LinkedIn
```http
PUT /v1/linkedin/candidates/{candidate_id}/sync-from-linkedin
```

Atualiza informações do candidato (nome, localização) com dados do LinkedIn já armazenados.

### Dados Extraídos do LinkedIn

- **Informações Básicas:** Nome, headline, localização, sobre
- **Experiências:** Empresas, cargos, períodos, descrições
- **Formação:** Instituições, cursos, períodos
- **Skills:** Lista de habilidades
- **Certificações:** Cursos e certificações
- **Idiomas:** Idiomas e níveis de proficiência

### Privacidade e Retenção

- Dados do LinkedIn são armazenados em `external_enrichments`
- Política de retenção padrão: 90 dias
- Conformidade com LGPD
- Auditoria completa de todas as operações

---

## Como Testar

### 1. Inicializar o Banco de Dados

```bash
cd backend
python -m app.db.init_db
```

### 2. Iniciar o Servidor

```bash
uvicorn app.main:app --reload
```

### 3. Acessar Documentação Interativa

Abra no navegador:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 4. Exemplos de Teste

**Criar um candidato:**
```bash
curl -X POST "http://localhost:8000/v1/candidates/" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "João Silva",
    "email": "joao@email.com",
    "city": "São Paulo",
    "state": "SP"
  }'
```

**Configurar prompts do chat:**
```bash
curl -X PUT "http://localhost:8000/v1/settings/prompts/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "temperature": 0.5,
    "max_tokens": 1500
  }'
```

**Adicionar dados do LinkedIn:**
```bash
curl -X POST "http://localhost:8000/v1/linkedin/candidates/1/manual" \
  -H "Content-Type: application/json" \
  -d '{
    "profile_url": "https://www.linkedin.com/in/joao-silva/",
    "skills": ["Python", "AWS", "Docker"]
  }'
```

**Remover um candidato:**
```bash
curl -X DELETE "http://localhost:8000/v1/candidates/1"
```

---

## Próximos Passos

1. **Autenticação:** Adicionar JWT para proteger endpoints
2. **Permissões:** Implementar RBAC (Role-Based Access Control)
3. **Interface Web:** Criar frontend React para gerenciar configurações
4. **Validações:** Adicionar validações mais robustas
5. **Testes:** Implementar testes unitários e de integração
6. **LinkedIn API:** Integrar com API oficial do LinkedIn
7. **Storage:** Implementar upload de currículos para MinIO/S3
8. **OCR:** Adicionar extração de texto de PDFs e imagens
