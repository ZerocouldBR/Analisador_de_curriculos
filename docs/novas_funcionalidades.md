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

## Funcionalidades entregues recentemente

### Hardening da extração de dados (PR #32 + hardening atual)

Corrigido o bug que fazia a extração via IA falhar silenciosamente
(`response.usage.total_tokens` → `response.tokens_used`). Além disso:

- **Multi-pass LLM**: 24k/16k/10k chars, até 8k tokens de resposta,
  parser JSON tolerante.
- **Prompt anti-competência**: rejeita "Gestão de data center",
  "Senior Project Manager", "Active Directory" como nome.
- **Validadores brasileiros** em `brazilian_validators.py`:
  - CPF com checksum mod 11 (descarta CPFs inválidos).
  - Telefone normalizado para E.164 (`+5511999998888`).
  - Email em lowercase + strip + validação de formato.
  - Data de nascimento flexível (aceita `15/01/1990`, `1990-01-15`,
    "15 de janeiro de 1990").
  - LinkedIn canônico preservando `/in/` vs `/pub/`.
- **Cross-validation nome↔email**: se o prefixo do email não bate
  com tokens do nome (< 30%), baixa a confiança e gera alerta.
- **Fuzzy match unicode-aware**: verifica se o nome aparece no texto
  bruto ignorando acentos e preposições.
- **Flag de OCR baixo**: quando páginas OCR'ed têm confiança < 60%,
  um alerta `low_ocr_confidence` é propagado para a validação.
- **Foto de perfil**: `PhotoExtractionService` extrai de PDFs/DOCX
  com heurística de proporção + Haar cascade quando OpenCV disponível.
  Servida via `GET /v1/candidates/{id}/photo`.
- **Novos campos em `candidates`**: `professional_title`,
  `professional_summary`, `linkedin_url`, `photo_url`.

### Painel público de vagas + análise de fit por IA (PR #33)

- CRUD de vagas em `/v1/jobs/*` (novas permissões `jobs.*`).
- Endpoints públicos sem auth em `/v1/public/careers/{company_slug}[/*]`.
- Página pública por empresa com branding customizado
  (`logo_url` + `brand_color` + `public_about` em `company.settings_json`).
- `JobFitService` compara perfil vs vaga e retorna score 0–100,
  `strengths`, `gaps`, `matched_skills`, `missing_skills`, `recommendation`.
- Task Celery `analyze_application_fit_task` roda em background.

### Portal do candidato via magic link (PR #34)

- `CandidateAccessToken` de 256 bits, expiração default 72h, revogável.
- Endpoints HR: `POST/GET/DELETE /v1/candidates/{id}/access-tokens[/*]`.
- Endpoints públicos (`/v1/public/me/{token}[/*]`):
  - `GET` — perfil | `PATCH` — edita campos (cria nova versão de `candidate_profiles`)
  - `POST /improve` — sugestão de melhoria via `ProfileImprovementService`
  - `POST /apply-suggestion` — aplica sugestão aprovada pelo candidato.

### Portal aplica em vagas sem reupload (PR #35)

- `GET /v1/public/me/{token}/jobs` — vagas ativas com flag `already_applied`.
- `GET /v1/public/me/{token}/applications` — candidaturas com `fit_score`.
- `POST /v1/public/me/{token}/apply/{job_slug}` — aplica reusando o
  `Document` mais recente. Dedup por `(candidate_id, job_id)`.

---

## Próximos Passos

Ver `docs/ROADMAP.md` para a lista priorizada. Principais itens:

1. **Emails transacionais** (magic link, confirmação de candidatura, mudança de estágio).
2. **Dashboard HR** com contadores de aplicações novas.
3. **Comparador de candidatos** para uma mesma vaga.
4. **Migração para Alembic** (hoje usa `create_all` + `ALTER IF NOT EXISTS`).
5. **Rate limiting** nos endpoints públicos (magic link + apply).
6. **Testes automatizados** (validadores, pipeline, endpoints públicos).
7. **Conta real de candidato** (alternativa ao magic link).
8. **Bugs concretos** listados em `ROADMAP.md` §3.3 (slug global unique,
   N+1 em `/public/careers`, race em `CandidateProfile.version`, etc.).
