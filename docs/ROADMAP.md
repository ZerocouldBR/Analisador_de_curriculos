# ROADMAP — Analisador de Curriculos

Este documento registra o estado atual das entregas relacionadas ao fluxo
**extracao de curriculo + painel publico de vagas + portal do candidato**,
e lista as acoes futuras acordadas.

Atualizado em: 2026-04-17.

---

## 1. PRs desta cadeia (merged)

Todos os 4 PRs desta serie ja foram merged em `main`:

| PR  | Titulo                                                        | Status |
| --- | ------------------------------------------------------------- | ------ |
| #32 | Fix extracao de curriculo + foto + LinkedIn + titulo          | merged |
| #33 | Painel publico de vagas + analise de fit por IA               | merged |
| #34 | Portal do candidato via magic link + sugestoes de melhoria    | merged |
| #35 | Portal aplica em vagas sem reupload (fecha o loop com #33/34) | merged |

---

## 2. Resumo do que cada PR entrega

### #32 — Fix da extracao do curriculo

- Corrige bug critico `response.usage.total_tokens` em
  `resume_ai_extraction_service.py` e `career_advisory_service.py` que
  derrubava a IA em silencio e fazia o sistema cair em `regex_only`.
- Multi-pass de extracao (24k / 16k / 10k chars, `max_tokens` 8k/6k/4k)
  com parser JSON tolerante.
- Prompt reescrito com regras anti-competencia (rejeita "Gestao de data
  center", "Active Directory", "Senior Project Manager" como nome).
- Normalizacao canonica de URL do LinkedIn + recuperacao de URLs
  quebradas em varias linhas.
- `PhotoExtractionService` extrai foto de perfil de PDFs/DOCX
  (heuristica + Haar cascade quando OpenCV disponivel) e salva em
  `<storage>/photos/<candidate_id>/profile.jpg`.
- Endpoint `GET /v1/candidates/{id}/photo` para servir a imagem.
- Novas colunas em `candidates`: `professional_title`,
  `professional_summary`, `linkedin_url`, `photo_url` (migracao leve
  via `ALTER TABLE ADD COLUMN IF NOT EXISTS` no startup).

### #33 — Painel publico de vagas + fit AI

- Modelos `Job` e `JobApplication` com slug publico, pipeline
  (`received` → `screening` → `interview` → ... → `hired` / `rejected`),
  `skills_required` / `skills_desired`.
- `JobFitService` compara perfil enriquecido vs vaga e retorna
  `score` 0-100, `strengths`, `gaps`, `matched_skills`,
  `missing_skills`, `recommendation`.
- Celery task `analyze_application_fit_task` roda em background apos
  o processamento do curriculo.
- Endpoints HR (`/v1/jobs/*`) com novas permissoes `jobs.*` injetadas
  em roles existentes sem sobrescrever permissoes customizadas.
- Endpoints publicos `/v1/public/careers/{company_slug}[/*]`.
- Frontend HR: `/jobs`, `/jobs/new`, `/jobs/:id/edit`, `/jobs/:id`
  (com tabela de aplicacoes ordenada por score, mudanca de estagio
  inline, dialog com analise de fit).
- Frontend publico: `/careers/:slug` e `/careers/:slug/:jobSlug`, com
  branding (logo + `brand_color` + `public_about`) lidos de
  `company.settings_json`.

### #34 — Portal do candidato (magic link) + IA de melhoria

- Modelo `CandidateAccessToken` (token url-safe 256 bits, `expires_at`,
  `use_count`, `revoked_at`, `purpose`).
- `CandidateAccessTokenService` (gerar / validar / revogar / listar).
- `ProfileImprovementService` com 3 prompts dedicados: reescrever
  resumo, headline e descricao de experiencia em bullets STAR.
- Endpoints HR (`/v1/candidates/{id}/access-tokens[/*]`) e publicos
  (`/v1/public/me/{token}[/*]`). Cada edicao cria nova versao de
  `CandidateProfile` (historico preservado).
- Config opcional `PUBLIC_BASE_URL`.
- Frontend HR: `CandidateAccessTokenDialog` com geracao/copia/lista/revogacao
  de links, acessado via botao "Link do candidato" no
  `CandidateDetailPage`.
- Frontend publico: `/me/:token` com branding + edicao inline +
  dialog de sugestao (aprovar/rejeitar).

### #35 — Portal aplica em vagas sem reupload

- `GET /v1/public/me/{token}/jobs` — vagas ativas da empresa, com
  indicador `already_applied` e `my_application_stage`.
- `GET /v1/public/me/{token}/applications` — candidaturas do candidato
  com `fit_score` / `fit_recommendation`.
- `POST /v1/public/me/{token}/apply/{job_slug}` — aplicar usando o
  perfil + Document existente. Dedup por (candidato, vaga).
- Frontend: componente `PortalJobsSection` com abas
  "Vagas abertas" e "Minhas candidaturas" renderizado depois das
  skills no portal do candidato.

---

## 3. Acoes futuras registradas

Itens que fazem sentido, mas **nao** estao implementados ainda. Cada
um e um candidato natural a PR futuro.

### 3.1 Ja discutidas no chat

- [ ] **Envio automatico de emails transacionais**
  - SMTP / SendGrid / Resend
  - Casos de uso:
    - Enviar magic link gerado em #34 direto ao candidato (hoje o RH
      copia/cola manualmente)
    - Enviar confirmacao de candidatura em #33 e #35
    - Notificar candidato quando o RH muda o estagio da aplicacao
  - Precisa: templates por empresa (com branding), config SMTP em
    `settings.py` e `company.settings_json`, fila Celery dedicada,
    opt-out por candidato (LGPD).

- [ ] **Dashboard do RH com novas aplicacoes**
  - Contador de aplicacoes recebidas por vaga e por estagio
  - Timeline visual tipo Kanban (`received` → ... → `hired`)
  - Widget "Top 5 candidatos por fit" em cada vaga ativa
  - Base: reutilizar `JobApplication.stage` e `fit_score`

- [ ] **Comparador de candidatos para uma vaga**
  - Tela `/jobs/:id/compare` com N candidatos lado a lado
  - Destacar diferencas de skills, experiencia, fit score
  - Util quando o RH quer decidir entre finalistas

- [ ] **Conta real de candidato (login/senha)**
  - Opcao alternativa ao magic link
  - Permite ver historico completo de candidaturas em multiplas
    empresas
  - Alto custo: role nova, recuperacao de senha, etc.
  - Nao priorizar antes de validar o magic link em producao

### 3.2 Identificadas durante a revisao

- [ ] **Migracao leve das tabelas `jobs`, `job_applications` e
      `candidate_access_tokens`**
  - Hoje os modelos sao criados via `Base.metadata.create_all`, que
    so cria se a tabela ainda nao existe. Em bancos ja populados
    funciona porque sao tabelas novas.
  - Seguindo o padrao de #32, adicionar `ALTER TABLE ADD COLUMN IF
    NOT EXISTS` para futuras colunas destas tabelas no `init_db.py`.

- [ ] **Alembic / migracoes versionadas**
  - O sistema atual depende de `create_all()` + migracoes inline
    em `init_db.py`. Funciona para novas tabelas e `ADD COLUMN`,
    mas nao cobre `DROP`, renomear ou mudar FKs.
  - Migrar gradativamente para Alembic. Pode ser incremental
    (baseline do schema atual).

- [ ] **Rate limiting nos endpoints publicos**
  - `/v1/public/careers/*/apply` e `/v1/public/me/{token}/*`
    aceitam requests sem auth; hoje nao ha rate limit nem
    CAPTCHA.
  - Implementar via slowapi (middleware) com limites diferenciados
    por rota (p. ex. `apply`: 5/min/IP, `improve`: 20/hora/IP).

- [ ] **Fit analysis com rate limit / fila dedicada**
  - Cada candidatura publica dispara uma chamada LLM. Se o painel
    for viral, vira custo.
  - Adicionar `rate_limit_rpm` por company (ja existe em
    `ProviderConfig`), orcamento mensal por empresa
    (`max_monthly_ai_cost` ja esta no `Company`) e fila dedicada
    "low_priority" para retentativas.

- [ ] **Testes automatizados**
  - Nenhum teste foi adicionado nos 4 PRs. Priorizar:
    - `PhotoExtractionService` com fixtures PDF/DOCX sinteticos
    - `JobFitService.analyze_fit` com mocks do LLM
    - `CandidateAccessTokenService` (geracao / validacao / expiracao)
    - Rotas publicas `/public/careers/*` (auth nao exigida) e
      `/public/me/*` (token obrigatorio)

- [ ] **Observabilidade**
  - Metricas Prometheus ja existem via `prometheus_fastapi_instrumentator`.
    Adicionar contadores custom:
    - `jobs_applications_total{job_slug,stage}`
    - `fit_analysis_duration_seconds`
    - `ai_improvements_total{field}`
  - Logs estruturados: ja existem, mas verificar que chamadas de IA
    incluem `candidate_id`, `job_id`, `application_id` e `tokens_used`.

- [ ] **UX/UI pendencias**
  - `JobDetailPage` nao tem polling do fit_score — o usuario precisa
    recarregar para ver. Adicionar refetch a cada 10s enquanto existir
    candidatura com `fit_status=pending`.
  - Portal do candidato nao mostra link "Publicar perfil no banco de
    talentos" — pode ser util como alternativa a aplicar em vaga
    especifica.
  - Responsividade mobile: os dialogs de fit e de sugestao podem
    ser revisados em telas pequenas.

- [ ] **Seguranca**
  - Validar o `token` da URL contra timing attacks: substituir
    `CandidateAccessToken.query.filter(token == raw)` por
    `secrets.compare_digest` (ou hash do token no DB).
  - Magic link expoe candidato inteiro — considerar exigir confirmacao
    de email na primeira abertura (`pending_confirmation` state).

- [ ] **Cleanup / manutencao**
  - Rodar Celery Beat para purgar tokens expirados > 30 dias.
  - Limpar JobApplications muito antigas (> 1 ano) com consentimento
    expirado (LGPD).

### 3.3 Bugs/riscos concretos encontrados em auditoria automatica

Itens especificos levantados em revisao automatica dos 4 PRs:

- [ ] **`Job.slug` unique GLOBALMENTE (cross-company) — potencial bug**
  - `Job.slug = Column(String, unique=True, ...)` em
    `backend/app/db/models.py`.
  - Duas empresas tentando criar vaga "analista-dados" dao colisao.
  - Correto seria `unique=False, index=True` + indice composto
    `(company_id, slug)`.
  - Fix requer migration + ajustar `JobService.generate_unique_slug`
    para considerar `company_id`.

- [ ] **`JobService.find_or_create_candidate` nao normaliza email**
  - Aceita o email cru do form publico. `USER@foo.com` e
    `user@foo.com` viram 2 candidatos.
  - Correto: `email.strip().lower()` antes de buscar/inserir.

- [ ] **N+1 em `/v1/public/careers/{slug}`**
  - `list_public_jobs` retorna `Job[]`; cada serializacao acessa
    `.company`. Sem eager-load (`selectinload(Job.company)`), cada
    vaga vira uma query extra.
  - Critico porque este endpoint e 100% publico e pode receber
    carga nao autenticada.

- [ ] **Race condition em `CandidateProfile.version`**
  - Dois requests simultaneos do mesmo magic link podem criar
    versoes com o mesmo numero (ou pular) — nao ha lock otimista.
  - Correto: `UNIQUE (candidate_id, version)` + retry em
    `IntegrityError`, ou usar `SELECT FOR UPDATE`.

- [ ] **`analyze_application_fit_task` usa perfil mais recente**
  - Se o candidato edita o perfil no portal logo apos aplicar, a
    analise pode rodar contra um perfil diferente do "snapshot"
    da aplicacao.
  - Correto: salvar `candidate_profile_version_id` em
    `JobApplication` no momento da aplicacao e carregar exatamente
    essa versao na task.

- [ ] **Magic link sem rate limit**
  - Um token roubado permite chamadas ilimitadas em
    `/improve` (custo LLM) e `/apply-suggestion`. Combinar com o
    item de rate limiting em 3.2.

---

## 4. Testes manuais pos-merge

Antes de declarar "pronto para producao":

1. Reprocessar o PDF LinkedIn que motivou o #32 e confirmar nome,
   LinkedIn URL, headline, foto.
2. Criar uma vaga, copiar link publico, aplicar em aba anonima com um
   PDF real. Verificar que `fit_score` aparece na lista de aplicacoes
   dentro de ~1 minuto.
3. Gerar magic link para um candidato, acessar em aba anonima. Editar
   summary manualmente e com "Melhorar com IA" — confirmar que o
   CandidateProfile ganha uma nova versao em cada edicao.
4. Abrir vaga diretamente pelo portal do candidato (#35), aplicar e
   confirmar que nao sobe novo documento (reusa o existente).
5. Revogar o token e verificar que todos os endpoints
   `/v1/public/me/{token}/*` passam a retornar 404.

---

## 5. Como este documento e mantido

Este arquivo deve ser atualizado:
- Ao finalizar um PR desta cadeia (riscar o item correspondente em 3.x)
- Ao descobrir uma nova acao futura (adicionar em 3.2)
- Ao mudar a ordem de merge (atualizar tabela em 1)
