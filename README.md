# Analisador de Currículos (On-Premises)

Este repositório inicia a implementação por etapas do sistema de RH on-premises para ingestão, normalização, indexação vetorial e busca conversacional em currículos.

## Entregas por etapa

1. **Etapa 1 (atual)**: Arquitetura, modelo de dados e fluxos do pipeline.
2. **Etapa 2 (iniciado)**: Scaffold do repositório + docker-compose.
3. Etapa 3: Ingestão + OCR + jobs + UI de progresso.
4. Etapa 4: Indexação vetorial + busca híbrida + filtros.
5. Etapa 5: Chat RAG + evidências + prompts configuráveis.
6. Etapa 6: RBAC + auditoria + LGPD + hardening + console admin + launcher Windows.

## Estrutura inicial

- `docs/`: documentação da arquitetura, modelo de dados e fluxos.
- `backend/`: API FastAPI inicial (saúde e configuração base).

## Executar backend (local)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Endpoint de saúde:

```
GET http://localhost:8000/api/health
```
