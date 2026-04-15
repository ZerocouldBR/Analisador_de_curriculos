# Sourcing Hibrido de Candidatos

## Visao Geral

O modulo de sourcing hibrido permite ingerir candidatos de multiplas fontes,
consolidar em um perfil canonico, versionar snapshots, detectar mudancas e
deduplicar automaticamente.

## Arquitetura

```
                    ┌─────────────────┐
                    │  ProviderRegistry│
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │            │       │       │             │
   ┌────┴────┐ ┌────┴────┐ ┌┴──────┐ ┌────┴────┐ ┌┴──────────┐
   │LinkedIn │ │CSV/XLSX │ │Manual │ │Webhook │ │External   │
   │Provider │ │Provider │ │Entry  │ │Provider│ │Partner    │
   └────┬────┘ └────┬────┘ └──┬───┘ └────┬───┘ └────┬──────┘
        │           │         │          │           │
        └───────────┴─────┬───┴──────────┴───────────┘
                          │
                ┌─────────┴──────────┐
                │ CandidateNormalizer │
                └─────────┬──────────┘
                          │
                ┌─────────┴──────────┐
                │ DeduplicationService│
                └─────────┬──────────┘
                          │
              ┌───────────┴────────────┐
              │     SyncService        │
              │  (orquestrador central)│
              └───────────┬────────────┘
                          │
         ┌────────────────┼────────────────┐
         │                │                │
   ┌─────┴──────┐ ┌──────┴──────┐ ┌──────┴──────┐
   │  Candidate  │ │  Snapshot   │ │   Merge     │
   │  (DB model) │ │  Service    │ │   Service   │
   └─────────────┘ └─────────────┘ └─────────────┘
```

## Fluxo de Dados

1. **Ingestao**: Provider busca candidatos na fonte (API, arquivo, webhook)
2. **Normalizacao**: CandidateNormalizer converte para perfil canonico
3. **Deduplicacao**: DeduplicationService verifica se ja existe no banco
4. **Persistencia**: Cria ou atualiza Candidate + CandidateSource
5. **Snapshot**: SnapshotService gera snapshot versionado com hash
6. **Diff**: Se snapshot mudou, registra no CandidateChangeLog
7. **Metricas**: SourcingSyncRun registra contadores da execucao

## Modelos de Dados

### candidate_sources
Registra cada fonte de dados de um candidato:
- `provider_name`: nome do provider (linkedin, csv_import, manual, etc.)
- `provider_type`: tipo (api, file, manual, webhook)
- `external_id`: ID do candidato no sistema externo
- `source_confidence`: confianca da fonte (0.0-1.0)
- `consent_status`: status do consentimento (pending, granted, revoked)

### candidate_snapshots
Snapshots versionados do perfil canonico:
- `canonical_json`: dados normalizados do candidato
- `snapshot_hash`: SHA-256 para deteccao de mudancas
- `extracted_text`: texto searchavel para embeddings

### candidate_change_logs
Diferencas entre snapshots consecutivos:
- `changed_fields_json`: campos que mudaram com valores antigo/novo
- `diff_summary`: resumo textual das mudancas

### sourcing_sync_runs
Registro de cada execucao de sincronizacao:
- Contadores: scanned, created, updated, unchanged, failed
- Status: pending, running, completed, failed

### provider_configs
Configuracao por tenant/provider:
- `config_json_encrypted`: credenciais encriptadas
- `schedule_cron`: expressao cron para sincronizacao
- `rate_limit_rpm/daily`: limites de taxa

## Providers Disponiveis

### LinkedIn (`linkedin`)
- Tipo: API
- Delega para LinkedInService existente (Proxycurl/RapidAPI/Official)
- Normaliza resposta para perfil canonico
- Confianca: 0.8 (Proxycurl), 0.4 (scraping)

### CSV Import (`csv_import`)
- Tipo: FILE
- Le CSV com mapeamento de colunas configuravel
- Colunas padrao: nome, email, telefone, cidade, estado, cargo, empresa, skills, linkedin
- Confianca: 0.6

### XLSX Import (`xlsx_import`)
- Tipo: FILE
- Le Excel (.xlsx) via openpyxl
- Mesmo mapeamento de colunas do CSV

### Manual (`manual`)
- Tipo: MANUAL
- Para candidatos inseridos manualmente
- Confianca: 1.0

### Webhook (`webhook`)
- Tipo: WEBHOOK
- Recebe payloads via push
- Valida assinatura HMAC-SHA256
- Formato esperado: `{"candidate": {...}, "source_id": "..."}`

### External Partner (`external_partner`)
- Tipo: API
- Adapter HTTP generico configuravel
- Config: base_url, auth_header, auth_value, response_mapping
- Permite conectar a qualquer ATS/plataforma de recrutamento

## Como Adicionar Novos Providers

1. Criar arquivo `backend/app/services/sourcing/meu_provider.py`
2. Implementar a classe herdando `SourceProvider`:

```python
from app.services.sourcing.provider_base import (
    SourceProvider, ProviderType, CandidateCanonicalProfile, ProviderHealthStatus
)
from app.services.sourcing.provider_registry import ProviderRegistry

class MeuProvider(SourceProvider):
    @property
    def provider_name(self) -> str:
        return "meu_provider"

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.API

    async def health_check(self, config):
        return ProviderHealthStatus(healthy=True, message="OK")

    async def search_candidates(self, config, criteria, limit=50):
        # Buscar candidatos na fonte externa
        return [CandidateCanonicalProfile(full_name="...")]

    async def fetch_candidate_by_external_id(self, config, external_id):
        return None

# Auto-registrar
ProviderRegistry.register(MeuProvider())
```

3. Importar no `__init__.py`:
```python
from app.services.sourcing import meu_provider  # noqa: F401
```

## Configuracao

### Variaveis de Ambiente (backend/.env)

```env
SOURCING_ENABLED=true
SOURCING_SYNC_INTERVAL_DAYS=5
SOURCING_DEDUP_THRESHOLD=0.7
SOURCING_DEDUP_EMAIL_WEIGHT=0.4
SOURCING_DEDUP_PHONE_WEIGHT=0.2
SOURCING_DEDUP_NAME_WEIGHT=0.25
SOURCING_DEDUP_LINKEDIN_WEIGHT=0.15
SOURCING_DEDUP_NAME_FUZZY_THRESHOLD=0.85
SOURCING_MAX_SYNC_CANDIDATES=500
SOURCING_SNAPSHOT_RETENTION_DAYS=365
SOURCING_EXTERNAL_REQUEST_TIMEOUT=30
SOURCING_MERGE_PRIORITY_ORDER=["linkedin","manual","csv_import","xlsx_import","webhook","external_partner"]
```

### Configuracao por Tenant (via API)

```bash
# Configurar provider LinkedIn
curl -X POST /api/v1/sourcing/providers/config \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "provider_name": "linkedin",
    "is_enabled": true,
    "config_json": {
      "proxycurl_api_key": "...",
      "search_country": "BR"
    },
    "schedule_cron": "0 2 */5 * *",
    "rate_limit_rpm": 30
  }'
```

## Sincronizacao Automatica

O sistema usa Celery Beat para agendar sincronizacoes:

1. **Healthcheck noturno** (3 AM): `nightly_source_healthcheck_task`
   - Verifica todos os providers habilitados
   - Dispara sync para providers que ultrapassaram o intervalo configurado

2. **Sync manual**: Via API ou botao no frontend
   - `POST /api/v1/sourcing/providers/{name}/sync`

3. **Intervalo padrao**: 5 dias (configuravel por tenant)

## Deduplicacao

O sistema detecta duplicatas usando scoring ponderado:

| Campo        | Peso   | Tipo de Match     |
|-------------|--------|-------------------|
| Email       | 40%    | Exato (lowercase) |
| Nome        | 25%    | Fuzzy (>85%, configuravel via SOURCING_DEDUP_NAME_FUZZY_THRESHOLD) |
| Telefone    | 20%    | Digitos           |
| LinkedIn URL| 15%    | Slug normalizado  |

Threshold padrao: 0.7 (70% de similaridade)

## Merge de Candidatos

Quando multiplas fontes trazem dados do mesmo candidato:

1. **Campos simples** (nome, email, etc.): usa valor da fonte com maior prioridade
2. **Campos de lista** (skills, experiencias): uniao de todas as fontes
3. **Prioridade padrao**: linkedin > manual > csv > xlsx > webhook > external

## API Endpoints

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| GET    | /sourcing/providers | Listar providers |
| GET    | /sourcing/providers/{name}/status | Health check |
| POST   | /sourcing/providers/config | Configurar provider |
| POST   | /sourcing/providers/{name}/test | Testar conexao |
| POST   | /sourcing/providers/{name}/sync | Sincronizar |
| GET    | /sourcing/runs | Listar sync runs |
| GET    | /sourcing/runs/{id} | Detalhes de sync run |
| GET    | /sourcing/candidates/{id}/sources | Fontes do candidato |
| GET    | /sourcing/candidates/{id}/snapshots | Snapshots |
| GET    | /sourcing/candidates/{id}/snapshots/diff | Diff entre snapshots |
| POST   | /sourcing/search | Busca hibrida |
| GET    | /sourcing/merge-suggestions | Sugestoes de merge |
| POST   | /sourcing/merge | Executar merge |

## Celery Beat

O servico `celery-beat` deve ser adicionado ao docker-compose:

```yaml
celery-beat:
  build:
    context: ./backend
  command: celery -A app.core.celery_app beat --loglevel=info
  env_file:
    - ./backend/.env
  depends_on:
    db:
      condition: service_healthy
    redis:
      condition: service_healthy
  restart: unless-stopped
```

## Troubleshooting

### Provider nao aparece na lista
- Verificar se o import esta no `__init__.py` do modulo sourcing
- Verificar logs do servidor para erros de registro

### Sync nao roda automaticamente
- Verificar se o servico `celery-beat` esta rodando
- Verificar se o provider esta habilitado (`is_enabled=true`)
- Verificar se o intervalo de sync ja passou

### Deduplicacao muito agressiva
- Aumentar o threshold: `SOURCING_DEDUP_THRESHOLD=0.8`
- Ajustar pesos individuais via env vars

### Config nao salva
- Verificar permissao `sourcing.config` no role do usuario
- Verificar se o usuario pertence a uma empresa (company_id)
