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
        |                                |                    +--> [Embeddings OpenAI]
        |                                |
        |                                +--> [PostgreSQL + pgvector + tsvector]
        |                                +--> [NAS/SMB ou MinIO]
        |
        +--> [Web UI RH] (abre browser apontando para UI)

[Console Admin] <--> [FastAPI] <--> [Serviços/Configurações/LGPD]
```

## Considerações de segurança e LGPD

- Separação de PII em colunas/tabelas específicas com permissão por role.
- Sanitização configurável antes de embeddings e LLM.
- Auditoria completa (quem fez o quê e quando).
- Retenção e exclusão com remoção de embeddings/chunks.
- Sem scraping de áreas autenticadas; apenas links públicos com consentimento.
