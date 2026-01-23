# Etapa 1 — Fluxos e Pipeline

## Ingestão por arquivo (passo a passo)

1. **Hash (sha256)** do arquivo para deduplicação.
2. **Detecção de tipo** (pdf/docx/html/img).
3. **Extração de texto**
   - PDF nativo: extrair texto diretamente.
   - PDF/Imagem: OCR local (Tesseract) com progresso.
4. **Normalização** do texto (limpeza de ruído e cabeçalhos repetidos).
5. **Extração estruturada (JSON)** conforme schema e política LGPD.
6. **Chunking por seção** (experiência, formação, skills, etc.).
7. **Embeddings (batch)** seguindo config do servidor.
8. **Persistência** (documents, chunks, embeddings, profiles).
9. **Indexação full-text** (tsvector em chunks).
10. **Disponibilização** para busca e chat.

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
