# Etapa 1 — Modelo de Dados (ERD textual)

## Entidades principais

1) **users**
- id (PK), email, password_hash, name, status, created_at, last_login

2) **roles**
- id (PK), name, description

3) **user_roles**
- user_id (FK users), role_id (FK roles)

4) **candidates** (PII separada e protegida)
- id (PK), full_name, email, phone, doc_id, birth_date (opcional), address, city, state, country, created_at
- **Observação**: colunas com PII protegidas por RBAC e máscara.

5) **candidate_profiles**
- id (PK), candidate_id (FK), version, profile_json (JSONB), created_at

6) **documents**
- id (PK), candidate_id (FK), original_filename, mime_type, source_path (NAS/MinIO), sha256_hash, uploaded_at

7) **chunks**
- id (PK), document_id (FK), candidate_id (FK), section, content, meta_json (JSONB)

8) **embeddings**
- id (PK), chunk_id (FK), model, vector (pgvector), created_at

9) **dictionary_skills**
- id (PK), canonical_name, category, aliases (array/json)

10) **companies**
- id (PK), name, industry, city, state

11) **competitor_flags**
- id (PK), company_id (FK), flag_type, notes

12) **experiences** (opcional para filtros)
- id (PK), candidate_id (FK), company_name, title, start_date, end_date, industry, description

13) **consents / legal_basis**
- id (PK), candidate_id (FK), consent_type, legal_basis, granted_at, expires_at

14) **audit_log**
- id (PK), user_id (FK), action, entity, entity_id, metadata_json, created_at

15) **ingestion_jobs**
- id (PK), created_by (FK users), status, progress, started_at, finished_at

16) **ingestion_job_items**
- id (PK), job_id (FK), document_id (FK), status, progress, error_message

17) **external_enrichment** (opcional)
- id (PK), candidate_id (FK), source, source_url, fetched_at, retention_policy, notes

18) **server_settings**
- id (PK), key, value_json, version, updated_by (FK users), updated_at

19) **client_agents**
- id (PK), machine_name, agent_version, last_seen_at, permissions_json

## Relacionamentos (resumo)

- users <-> roles via user_roles
- candidates 1:N candidate_profiles
- candidates 1:N documents
- documents 1:N chunks
- chunks 1:N embeddings
- candidates 1:N experiences
- candidates 1:N consents
- users 1:N ingestion_jobs
- ingestion_jobs 1:N ingestion_job_items
- candidates 1:N external_enrichment

## Índices sugeridos

- documents.sha256_hash (único) para deduplicação
- chunks.section + candidate_id para filtros rápidos
- embeddings.vector (pgvector ivfflat/hnsw)
- tsvector em chunks.content para full-text
- candidates.city/state para filtros geográficos
