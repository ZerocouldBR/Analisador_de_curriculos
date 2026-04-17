# Etapa 1 — Arquitetura

## Visão geral

Sistema on-premises para RH com base central na LAN e agentes Windows nas estações. O objetivo é ingerir currículos locais, normalizar perfis, gerar embeddings e permitir busca híbrida e chat RAG com evidências. O desenho segue LGPD by design, com separação de PII, trilha de auditoria e opções de mascaramento/sanitização antes do envio a LLMs.

## Camadas (3 tiers)

### A) Servidor Central (LAN)

- **API Backend (FastAPI)**
  - Autenticação JWT, RBAC, APIs para ingestão, busca, chat e administração.
  - Camada de serviços para RAG, embeddings e normalização.
  - Sanitização/mascaramento de PII antes de embeddings/LLM.
- **Workers (Celery + Redis)**
  - Processamento assíncrono da ingestão (OCR, parsing, chunking, embeddings).
  - Progresso por job com status detalhado.
- **UI Web RH (React/Next.js)**
  - Painel de ingestão, dashboard, candidatos, busca avançada, chat com evidências.
- **Console Web Admin (RBAC)**
  - Serviços, banco/storage, configurações de IA, RAG, prompts, LGPD, usuários e auditoria.
- **PostgreSQL + pgvector + full-text (tsvector)**
  - Dados estruturados, chunks, embeddings e ranking híbrido.
- **Storage de arquivos**
  - NAS/SMB padrão (caminho compartilhado), com opção MinIO (S3 on-prem).

### B) Cliente/Agent Standalone Windows

- **Launcher amigável (Tauri recomendado)**
  - Modo "Somente RH" ou "Importador/Analisador".
  - Seleção de pastas, watch folder, progresso por arquivo.
  - Configuração de servidor/credenciais, botão abrir ERP e abrir Web.
  - Tela de saúde (API, fila, storage, permissões).
- **Ingestão local**
  - OCR local (Tesseract), parsing, normalização e upload seguro.
  - Logs e exportação de relatório de erro.

### C) UI Web (RH e Gestores)

- Busca híbrida (vetor + tsvector) com filtros e pesos por vaga.
- Chat RAG com evidências e recomendações de filtros.
- Separação de PII conforme permissões e LGPD.

## Justificativas tecnológicas

- **FastAPI + Pydantic + SQLAlchemy**: alta produtividade, validação forte e performance suficiente.
- **Celery + Redis**: controle de filas, retry e tracking de jobs.
- **Tesseract**: OCR local e offline.
- **pgvector + tsvector**: busca híbrida eficiente com ranking controlável.
- **OpenAI Responses API**: geração com melhores práticas e parâmetros atuais.
- **Tauri para o agent**: app leve e atualizável, UI moderna e executável compacto.

## Diagrama lógico (texto)

```
[Windows Agent] --(API + Upload)--> [FastAPI] --(Jobs)--> [Celery Workers]
        |                                |                    |
        |                                |                    +--> [OCR/Parsing/Chunking]
        |                                |                    +--> [Extração IA + validadores BR]
        |                                |                    +--> [Análise de fit (jobs)]
        |                                |                    +--> [Embeddings OpenAI/Anthropic]
        |                                |
        |                                +--> [PostgreSQL + pgvector + tsvector]
        |                                +--> [NAS/SMB ou MinIO + photos/<id>]
        |
        +--> [Web UI RH] (abre browser apontando para UI)

[Console Admin] <--> [FastAPI] <--> [Serviços/Configurações/LGPD]

# Fluxos públicos (sem autenticação)
[Candidato] --> [/careers/<company_slug>] --> lista de vagas da empresa
[Candidato] --> [/careers/<company_slug>/<job_slug>] --> detalhes + aplicar
[Candidato] --> [/me/<magic_token>] --> portal (editar perfil + sugerir IA)
```

## Camada pública (PR #33, #34, #35)

Novos endpoints em `/v1/public/...` e páginas frontend `/careers/*` e
`/me/*` que não exigem autenticação:

- **Painel de vagas por empresa**: branding customizado via
  `company.settings_json.brand_color`, `company.logo_url`, `public_about`.
- **Aplicação pública**: upload do currículo + consentimento LGPD → cria
  `Candidate` + `Document` + `JobApplication`. Backend dispara processamento
  + análise de fit via IA (`JobFitService`).
- **Magic link do candidato**: token de 256 bits em `candidate_access_tokens`,
  expiração configurável (default 72h), revogável pelo RH. Cada edição via
  portal cria nova versão em `candidate_profiles`.

## Pipeline de extração (pós PR #32 e hardening)

```
[Documento] -> TextExtractionService
                 ├── pdfplumber (PDF nativo)
                 ├── Tesseract OCR (multi-res, multi-PSM, CLAHE, deskew)
                 └── DOCX parse + imagens embutidas

     -> normalize_text() -> texto limpo

     -> ResumeEnrichmentPipeline
          ├── 1. ResumeParserService (regex) + brazilian_validators
          │      (CPF mod 11, email lowercase, phone E.164,
          │       birth_date flexível, LinkedIn canônico /in/ ou /pub/)
          ├── 2. ResumeAIExtractionService (LLM multi-pass)
          │      - prompt anti-competência
          │      - cross-validate nome vs email prefix
          │      - descarta CPF inválido com note
          ├── 3. ResumeValidationService
          │      - fuzzy match unicode-aware (nome no texto)
          │      - alerta low_ocr_confidence se < 60%
          │      - alerta mismatch_with_email se overlap < 30%
          │      - alerta invalid_checksum em CPF inválido
          └── 4. PhotoExtractionService (Haar cascade + heurísticas)
                 -> <storage>/photos/<candidate_id>/profile.jpg

     -> CandidateProfile (versionado) + Candidate.full_name /
        professional_title / professional_summary /
        linkedin_url / photo_url
```

## Considerações de segurança e LGPD

- Separação de PII em colunas/tabelas específicas com permissão por role.
- Sanitização configurável antes de embeddings e LLM.
- Auditoria completa (quem fez o quê e quando).
- Retenção e exclusão com remoção de embeddings/chunks.
- Sem scraping de áreas autenticadas; apenas links públicos com consentimento.
