# Modelo de Dados

## Entidades Implementadas

### 1) **users**
- id (PK), email (unique), password_hash, name, status, is_superuser, created_at, last_login

### 2) **roles**
- id (PK), name (unique), description, permissions (JSONB), created_at
- Permissions granulares por role (RBAC):
  - `candidates.create`, `candidates.read`, `candidates.update`, `candidates.delete`
  - `documents.create`, `documents.read`, `documents.update`, `documents.delete`
  - `settings.read`, `settings.create`, `settings.update`, `settings.delete`
  - `linkedin.enrich`, `search.advanced`, `users.manage`

### 3) **user_roles** (many-to-many)
- user_id (FK users, CASCADE), role_id (FK roles, CASCADE), assigned_at

### 4) **candidates** (PII separada e protegida)
- id (PK), full_name, email, phone, doc_id (CPF), birth_date, address, city, state, country, created_at, updated_at
- **Campos adicionais (PR #32)**:
  - `professional_title` (String) — headline profissional extraido do curriculo
    (ex: "Senior Project Manager | IA & Transformacao Digital")
  - `professional_summary` (Text) — resumo completo da secao "Sobre/Resumo"
  - `linkedin_url` (String) — URL canonica (preserva `/in/` vs `/pub/`)
  - `photo_url` (String) — caminho relativo no storage (`photos/<id>/profile.jpg`)
- Relacionamentos cascade: profiles, documents, chunks, experiences, consents, external_enrichments, sources

### 5) **candidate_profiles**
- id (PK), candidate_id (FK CASCADE), version, profile_json (JSONB), created_at
- Armazena snapshot completo do curriculo parseado a cada processamento

### 6) **documents**
- id (PK), candidate_id (FK CASCADE), original_filename, mime_type, source_path, sha256_hash (indexado), uploaded_at
- sha256_hash indexado para deduplicacao (nao unique: mesmo arquivo pode ser associado a candidatos diferentes)

### 7) **chunks**
- id (PK), document_id (FK CASCADE), candidate_id (FK CASCADE), section, content, meta_json (JSONB), created_at
- Indice composto: section + candidate_id
- Secoes: full_text, personal_info, experiences, education, skills, languages, certifications, licenses, safety_certifications, equipment, erp_systems, availability, keyword_index

### 8) **embeddings**
- id (PK), chunk_id (FK CASCADE), model, vector (pgvector 1536 dims), created_at
- Indice HNSW para busca vetorial por similaridade de cosseno

### 9) **experiences**
- id (PK), candidate_id (FK CASCADE), company_name, title, start_date, end_date, industry, description, created_at
- Populado automaticamente a partir do parsing do curriculo

### 10) **consents**
- id (PK), candidate_id (FK CASCADE), consent_type, legal_basis, granted_at, expires_at
- Conformidade LGPD

### 11) **external_enrichments**
- id (PK), candidate_id (FK CASCADE), source, source_url, data_json (JSONB), fetched_at, retention_policy, notes
- Indice composto: source + candidate_id
- Fontes suportadas: linkedin, github

### 12) **server_settings**
- id (PK), key (unique), value_json (JSONB), description, version, updated_by (FK users), updated_at
- Armazena configuracoes do sistema e prompts do chat LLM

### 13) **audit_logs**
- id (PK), user_id (FK users), action, entity, entity_id, metadata_json (JSONB), created_at (indexado)
- Registro completo de todas as operacoes para compliance LGPD

## Relacionamentos

```
users <-> roles          via user_roles (many-to-many)
candidates 1:N           candidate_profiles (cascade)
candidates 1:N           documents (cascade)
candidates 1:N           chunks (cascade)
candidates 1:N           experiences (cascade)
candidates 1:N           consents (cascade)
candidates 1:N           external_enrichments (cascade)
documents  1:N           chunks (cascade)
chunks     1:N           embeddings (cascade)
users      1:N           audit_logs
```

## Indices

- `embeddings.vector` - HNSW (vector_cosine_ops) para busca semantica
- `chunks.content` - GIN (tsvector portuguese) para full-text search
- `chunks.meta_json` - GIN (jsonb_path_ops) para busca por metadados
- `chunks.section + candidate_id` - Composto para filtros rapidos
- `external_enrichments.source + candidate_id` - Composto para lookup
- `documents.sha256_hash` - B-tree para deduplicacao
- `candidates.city`, `candidates.state` - B-tree para filtros geograficos
- `audit_logs.created_at` - B-tree para queries temporais

## Tabelas de Sourcing Hibrido

### 15) **candidate_sources**
- id (PK), company_id (FK companies), candidate_id (FK candidates)
- provider_name, provider_type (api/file/manual/webhook)
- external_id, external_url, sync_enabled, consent_status
- source_priority (0-100), source_confidence (0.0-1.0)
- last_sync_at, last_status, last_error, created_at, updated_at
- Unique: (company_id, provider_name, external_id)

### 16) **candidate_snapshots**
- id (PK), company_id (FK), candidate_id (FK), source_id (FK candidate_sources, nullable)
- snapshot_hash (SHA-256), canonical_json (JSONB), extracted_text, embedding_version
- created_at

### 17) **candidate_change_logs**
- id (PK), company_id (FK), candidate_id (FK)
- snapshot_from_id (FK nullable), snapshot_to_id (FK)
- changed_fields_json (JSONB), diff_summary, created_at

### 18) **sourcing_sync_runs**
- id (PK), company_id (FK), provider_name
- run_type (manual/scheduled/webhook), status (pending/running/completed/failed)
- started_at, finished_at, total_scanned/created/updated/unchanged/failed
- metadata_json, error_detail

### 19) **provider_configs**
- id (PK), company_id (FK), provider_name
- is_enabled, config_json_encrypted, schedule_cron
- rate_limit_rpm, rate_limit_daily, created_at, updated_at
- Unique: (company_id, provider_name)

## Tabelas de Vagas e Portal do Candidato (PR #33, #34, #35)

### 20) **jobs** (Vagas publicas da empresa)
- id (PK), company_id (FK companies, CASCADE)
- `slug` (String, UNIQUE, indexado) — identificador publico da vaga no link
  `/careers/<company_slug>/<job_slug>`
- title, description (markdown permitido), requirements, responsibilities, benefits
- location, employment_type (CLT, PJ, Estagio...), seniority_level, work_mode
  (presencial/remoto/hibrido)
- salary_range_min, salary_range_max, salary_currency (default BRL), salary_visible
- skills_required (JSONB, lista), skills_desired (JSONB, lista)
- is_active (indexado), published_at, closes_at, created_by, created_at, updated_at
- Indice composto: (company_id, is_active)
- Relacionamento 1:N com `job_applications` (cascade)
- **Nota do ROADMAP:** o UNIQUE em `slug` deveria ser composto com `company_id`
  (bug #3.3 do ROADMAP).

### 21) **job_applications** (Candidaturas a vagas)
- id (PK), job_id (FK jobs CASCADE), candidate_id (FK candidates CASCADE)
- document_id (FK documents SET NULL) — curriculo usado na candidatura
- applicant_name, applicant_email (indexado), applicant_phone, cover_letter
- `fit_score` (Integer, 0-100) — pontuacao da IA
- `fit_analysis` (JSONB) — estrutura com strengths, gaps, matched_skills,
  missing_skills, recommendation (`strong_match`/`good_match`/`weak_match`/`no_match`)
- `fit_status` — `pending`, `analyzed`, `failed`
- `stage` (indexado) — pipeline: `received` → `screening` → `interview` →
  `technical` → `offer` → `hired` / `rejected`
- stage_notes, source (default `public_form`), consent_given (LGPD), created_at
  (indexado), updated_at
- Indice composto: (job_id, stage), (applicant_email, job_id)

### 22) **candidate_access_tokens** (Magic link do portal do candidato)
- id (PK), candidate_id (FK candidates CASCADE)
- `token` (String, UNIQUE) — 256 bits gerado com `secrets.token_urlsafe(32)`
- `expires_at` — tipicamente 72h apos criacao
- created_by (FK users, SET NULL), created_at, last_used_at, use_count, revoked_at
- `purpose` — `self_edit` ou `apply_with_profile`
- Indice: candidate_id
- URL gerada: `<PUBLIC_BASE_URL>/me/<token>`

## Roles Padrao

| Role | Descricao | Permissoes Principais |
|------|-----------|----------------------|
| admin | Acesso completo | Todas as permissoes (incl. sourcing.*, jobs.*) |
| company_admin | Admin de empresa | Todas as permissoes (incl. sourcing.*, jobs.*) |
| recruiter | Gerencia candidatos + vagas | CRUD candidatos/docs/vagas (sem delete), LinkedIn, busca avancada, sourcing.read, sourcing.sync, jobs.create/read/update |
| viewer | Apenas leitura | Leitura de candidatos, docs, settings e vagas |

Novas permissoes introduzidas pelo PR #33: `jobs.create`, `jobs.read`,
`jobs.update`, `jobs.delete`. Sao adicionadas a roles existentes via merge
nao-destrutivo no `init_roles.py`.

## Fluxo de Dados no Processamento

1. Upload do arquivo -> `documents` (com sha256 para dedup)
2. Celery task processa o documento:
   - Extrai texto (PDF/DOCX/OCR) -> normaliza
   - Parseia estrutura do curriculo (ResumeParserService) com validacoes de:
     - **CPF** via checksum mod 11 (descarta CPFs invalidos)
     - **Email** normalizado (lowercase + strip + regex de formato)
     - **Telefone** normalizado para E.164 (`+5511999998888`)
     - **Data de nascimento** via parser flexivel (aceita "15 de janeiro de 1990")
     - **LinkedIn URL** canonica preservando `/in/` vs `/pub/`
   - Executa pipeline de enriquecimento (`ResumeEnrichmentPipeline`):
     1. Regex (ResumeParserService)
     2. IA (ResumeAIExtractionService) — multi-pass com 24k/16k/10k chars
     3. Validacao cruzada (ResumeValidationService) incluindo:
        - **Nome vs email**: se `name_email_match_ratio < 0.3`, gera alerta
        - **Nome no texto bruto**: fuzzy match unicode-aware (ignora acentos)
        - **CPF**: checksum mod 11
        - **OCR**: alerta se `ocr_confidence < 0.6` em paginas OCR'ed
     4. Scoring de confianca por campo
   - Extrai foto de perfil (PhotoExtractionService) -> `candidates.photo_url`
   - Atualiza `candidates` com dados pessoais + `professional_title` + `professional_summary` + `linkedin_url`
   - Popula tabela `experiences` com experiencias profissionais
   - Salva snapshot versionado em `candidate_profiles` (cada edit pelo portal
     cria nova versao)
   - Limpa chunks/embeddings antigos do documento
   - Cria novos `chunks` por secao com metadados enriquecidos
   - Extrai keywords categorizadas (producao, logistica, qualidade, TI)
   - Cria `audit_logs` do processamento
3. Embeddings gerados sob demanda para busca semantica -> `embeddings`
4. Quando vinculado a candidatura: `job_fit_tasks.analyze_application_fit_task`
   aguarda o processamento do curriculo (ate 90s) e entao chama a IA para
   gerar `fit_score`, `fit_analysis` e `recommendation` em `job_applications`.
