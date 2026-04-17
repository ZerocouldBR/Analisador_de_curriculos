# Etapa 1 — Fluxos e Pipeline

## Ingestão por arquivo (passo a passo)

1. **Hash (sha256)** do arquivo para deduplicação.
2. **Detecção de tipo** (pdf/docx/html/img).
3. **Extração de texto** (`TextExtractionService`)
   - PDF nativo: extrair texto diretamente com `pdfplumber`.
   - PDF/Imagem: OCR local (Tesseract) com multi-resolução (150/200/300 dpi),
     multi-PSM (1/3/4/6), preprocessamento (CLAHE, deskew, Otsu, denoise).
   - Métricas retornadas: `confidence`, `pages_with_ocr`, `pages_with_text`,
     `warnings`.
4. **Normalização** do texto (limpeza de ruído e cabeçalhos repetidos).
5. **Extração estruturada** em pipeline (`ResumeEnrichmentPipeline`):
   1. Regex (`ResumeParserService`) — dados pessoais com validadores
      brasileiros (CPF mod 11, email normalizado, telefone E.164,
      data de nascimento flexível, LinkedIn canônico preservando `/in/` vs `/pub/`).
   2. IA (`ResumeAIExtractionService`) — multi-pass (24k→16k→10k chars)
      com prompt anti-competência e cross-validation nome↔email.
   3. Validação (`ResumeValidationService`) — fuzzy match unicode-aware,
      alerta de OCR baixo (< 60%), alerta de CPF inválido,
      alerta quando o nome não bate com o prefixo do email.
   4. Scoring de confiança por campo + label geral (alta / media / baixa).
6. **Extração de foto** (`PhotoExtractionService`) — heurística de tamanho/
   proporção + Haar cascade (quando OpenCV disponível) → `candidates.photo_url`.
7. **Chunking por seção** (experiência, formação, skills, etc.).
8. **Embeddings (batch)** seguindo config do servidor.
9. **Persistência** (documents, chunks, embeddings, profiles, candidates).
10. **Indexação full-text** (tsvector em chunks).
11. **Disponibilização** para busca, chat, portal do candidato e análise de fit.

## Busca híbrida e ranking

- **Entrada**: termos obrigatórios + filtros + parâmetros de vaga.
- **Query**:
  - tsvector para termos obrigatórios
  - pgvector para similaridade semântica
  - filtros por metadados
- **Re-ranking**:
  - 40% vetor
  - 30% termos obrigatórios
  - 20% experiência no domínio
  - 10% bônus (certificações, concorrentes, sistemas)

## Chat RAG

1. Interpretar a pergunta e sugerir filtros.
2. Rodar retrieval (vetor + texto + filtros).
3. Responder com candidatos, scores e **evidências** (chunks). 
4. Aplicar mascaramento de PII se necessário.

## Fluxo de administração (Console)

- Gerenciar serviços (start/stop/restart).
- Configurar DB/Storage, IA/embeddings, RAG e prompts.
- Políticas LGPD (retenção, minimização, exclusão).
- Usuários/roles e auditoria.

## Painel público de vagas (PR #33)

Link aberto por empresa (`/careers/<company_slug>`), sem autenticação, com
branding customizado (`logo_url`, `brand_color` em `company.settings_json`).

1. RH cria vaga em `/jobs/new` (título, descrição, requisitos, skills,
   faixa salarial, nível de senioridade, modo de trabalho).
2. Slug público é gerado automaticamente (ex: `desenvolvedor-backend-py`).
3. Candidato abre `/careers/<company_slug>` e vê todas as vagas ativas.
4. Clica em uma vaga → `/careers/<company_slug>/<job_slug>` com detalhes.
5. Preenche formulário + faz upload do currículo + dá consentimento LGPD.
6. Backend:
   - Valida formato/tamanho do arquivo.
   - `find_or_create_candidate(email)` — dedup por email da empresa.
   - Faz dedup do documento por SHA256.
   - Cria `JobApplication` com `fit_status = "pending"` e
     `source = "public_form"`.
   - Enfileira `process_document_task` (extração) e em seguida
     `analyze_application_fit_task` (análise de fit).
7. `JobFitService` (LLM) compara o perfil enriquecido do candidato com a
   descrição/requisitos da vaga e devolve:
   - `score` 0–100
   - `recommendation` (`strong_match`, `good_match`, `weak_match`, `no_match`)
   - `strengths`, `gaps`, `matched_skills`, `missing_skills`,
     `experience_match`.
8. RH visualiza em `/jobs/<id>` a lista ordenada por score, com dialog
   mostrando análise completa, e pode mover a candidatura pelo pipeline
   (`received` → `screening` → `interview` → `technical` → `offer`
   → `hired` / `rejected`).

## Portal do candidato (Magic link, PR #34)

Permite ao candidato ver e ajustar o próprio perfil importado, com
sugestões de melhoria por IA que são sempre propostas (nunca aplicadas
automaticamente).

1. RH abre `/candidates/<id>` e clica "Link do candidato".
2. Backend gera `CandidateAccessToken` (`secrets.token_urlsafe(32)`,
   256 bits, expiração default 72h).
3. RH copia a URL (`<PUBLIC_BASE_URL>/me/<token>`) e envia por email/WhatsApp.
4. Candidato acessa sem login; branding da empresa aparece no header.
5. Pode editar inline: nome, contatos, LinkedIn, GitHub, portfolio,
   headline, resumo, descrição de cada experiência, skills.
6. Cada edição cria uma **nova versão** de `candidate_profiles` (histórico
   preservado).
7. Para cada campo importante (summary, headline, experience) o candidato
   pode clicar "Melhorar com IA":
   - `ProfileImprovementService` usa prompt dedicado ("não inventar fatos").
   - Dialog mostra `original` vs `suggestion` + `rationale`.
   - Candidato clica "Aprovar" → aplica via
     `/public/me/<token>/apply-suggestion`; ou "Rejeitar" → descarta.
8. RH pode revogar o token a qualquer momento
   (`DELETE /v1/candidates/<id>/access-tokens/<token_id>`).

## Portal do candidato aplica em vagas (PR #35)

Fecha o loop entre portal e painel de vagas:

1. Candidato acessa `/me/<token>` e vê aba "Vagas abertas" com as vagas
   ativas da empresa dele, incluindo chip "Aplicado (estágio)" nas que já
   aplicou.
2. Clica "Aplicar" em uma vaga → dialog com carta de apresentação opcional.
3. Backend cria `JobApplication` reusando o perfil + último `Document` do
   candidato (**sem reupload**).
4. Dedup: se já existe `JobApplication` para `(candidate_id, job_id)`,
   retorna a existente (`already_existed: true`).
5. Enfileira fit analysis com `wait_for_profile=5s` (perfil já existe).
6. Aba "Minhas candidaturas" mostra o score de fit, a recomendação e o
   estágio de cada candidatura.

## Alertas de qualidade na extração

O pipeline anexa um ou mais alertas ao `validation.alerts[]` em caso de:

- `address_as_name` / `competency_as_name` — nome é na verdade um endereço
  ou competência técnica ("Gestão de data center").
- `not_in_text` — nome extraído não aparece no texto bruto (fuzzy match
  unicode-aware, ignora acentos e preposições).
- `mismatch_with_email` — nome não bate com o prefixo do email
  (`name_email_match_ratio < 0.3`).
- `invalid_checksum` — CPF não passa no algoritmo mod 11.
- `low_ocr_confidence` — OCR com confiança < 60% em páginas digitalizadas.
- `invalid_format` — email, telefone ou LinkedIn com formato incomum.

A UI exibe estes alertas no topo do `CandidateDetailPage` com severidade
visual (`critical` → vermelho, `high`/`medium` → laranja, `low` → cinza).
