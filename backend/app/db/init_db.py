"""
Script para inicializacao do banco de dados

Cria schemas, tabelas, extensoes e indices.
Todos os parametros vem de settings (nada hardcoded).

Suporta:
- PostgreSQL local com pgvector
- Supabase (PostgreSQL gerenciado)
- Qdrant (banco vetorial dedicado)
- Schemas customizados (DATABASE_SCHEMA)
- Multiplos provedores vetoriais simultaneos

Uso:
    python -m app.db.init_db                # Inicializar banco
    python -m app.db.init_db --drop         # Remover todas as tabelas
    python -m app.db.init_db --supabase-sql # Gerar SQL de setup do Supabase
"""

from sqlalchemy import text
from app.db.database import engine, Base
from app.core.config import settings
from app.db.models import (
    User,
    Role,
    Candidate,
    CandidateProfile,
    Document,
    Chunk,
    Embedding,
    Experience,
    Consent,
    ExternalEnrichment,
    ServerSettings,
    AuditLog,
    ChatConversation,
    ChatMessage,
    LinkedInSearch,
    EncryptedPII,
    CandidateSource,
    CandidateSnapshot,
    CandidateChangeLog,
    SourcingSyncRun,
    ProviderConfig,
)


def _schema_prefix() -> str:
    """Retorna o prefixo de schema para SQL (ex: 'meuschema.' ou '')"""
    return settings.database_schema_sql


def create_schema():
    """Cria o schema no PostgreSQL se nao for 'public'"""
    schema = settings.database_schema
    if not schema or schema == "public":
        return

    print(f"  Criando schema '{schema}'...")
    with engine.connect() as connection:
        try:
            connection.execute(text(
                f"CREATE SCHEMA IF NOT EXISTS {schema};"
            ))
            connection.commit()
            print(f"  Schema '{schema}' verificado/criado")
        except Exception as e:
            print(f"  Warning: Schema '{schema}': {e}")


def create_vector_extension():
    """Cria a extensao pgvector no PostgreSQL"""
    providers_that_need_pgvector = {"pgvector", "supabase"}
    enabled = set(settings.enabled_vector_providers)

    if not enabled.intersection(providers_that_need_pgvector):
        print("  pgvector extension not needed (provider does not use pgvector)")
        return

    with engine.connect() as connection:
        try:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            connection.commit()
            print("  pgvector extension verified")
        except Exception as e:
            print(f"  Warning: pgvector extension: {e}")
            print("  Certifique-se de que o pgvector esta instalado no PostgreSQL.")
            print("  Docker: use a imagem pgvector/pgvector:pg16")
            print("  Manual: https://github.com/pgvector/pgvector#installation")


def create_vector_indexes():
    """Cria indices vetoriais e full-text usando parametros de settings"""
    print("Criando indices...")
    sp = _schema_prefix()

    with engine.connect() as connection:
        # Indice HNSW para busca vetorial
        if settings.enable_hnsw_index:
            try:
                result = connection.execute(text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE indexname = 'idx_embeddings_vector_hnsw'"
                ))
                if result.fetchone() is None:
                    connection.execute(text(
                        f"CREATE INDEX idx_embeddings_vector_hnsw "
                        f"ON {sp}embeddings USING hnsw (vector {settings.pgvector_distance_ops}) "
                        f"WITH (m = {settings.pgvector_hnsw_m}, "
                        f"ef_construction = {settings.pgvector_hnsw_ef_construction});"
                    ))
                    connection.commit()
                    print(f"  HNSW index created (m={settings.pgvector_hnsw_m}, "
                          f"ef={settings.pgvector_hnsw_ef_construction}, "
                          f"metric={settings.pgvector_distance_metric})")
                else:
                    print("  HNSW index already exists")
            except Exception as e:
                print(f"  Warning: HNSW index: {e}")

        # Indice GIN para full-text search
        try:
            # Validar fts_language contra whitelist
            _VALID_FTS_LANGS = {
                "portuguese", "english", "spanish", "french", "german",
                "italian", "dutch", "russian", "simple",
            }
            fts_lang = settings.fts_language
            if fts_lang not in _VALID_FTS_LANGS:
                print(f"  Warning: fts_language invalido: {fts_lang}, usando 'portuguese'")
                fts_lang = "portuguese"

            result = connection.execute(text(
                "SELECT indexname FROM pg_indexes "
                "WHERE indexname = 'idx_chunks_content_fts'"
            ))
            if result.fetchone() is None:
                connection.execute(text(
                    f"CREATE INDEX idx_chunks_content_fts "
                    f"ON {sp}chunks USING GIN ("
                    f"to_tsvector('{fts_lang}', content));"
                ))
                connection.commit()
                print(f"  FTS index created (language={fts_lang})")
            else:
                print("  FTS index already exists")
        except Exception as e:
            print(f"  Warning: FTS index: {e}")

        # Indice GIN para meta_json
        try:
            result = connection.execute(text(
                "SELECT indexname FROM pg_indexes "
                "WHERE indexname = 'idx_chunks_meta_json'"
            ))
            if result.fetchone() is None:
                connection.execute(text(
                    f"CREATE INDEX idx_chunks_meta_json "
                    f"ON {sp}chunks USING GIN (meta_json jsonb_path_ops);"
                ))
                connection.commit()
                print("  JSON metadata index created")
            else:
                print("  JSON metadata index already exists")
        except Exception as e:
            print(f"  Warning: JSON index: {e}")

    print("  Indices configurados")


def generate_supabase_setup_sql() -> str:
    """
    Gera o SQL necessario para configurar o Supabase como vector store.

    Usa as dimensoes e configuracoes atuais do settings.
    O SQL gerado deve ser executado no SQL Editor do Supabase.

    Returns:
        String com o SQL completo para setup do Supabase
    """
    dims = settings.active_embedding_dimensions
    table = settings.supabase_table_name
    func = settings.supabase_function_name

    sql = f"""-- ============================================================
-- Supabase Vector Store Setup
-- Gerado automaticamente pelo Analisador de Curriculos
-- Dimensoes: {dims} ({settings.embedding_mode.value} mode)
-- ============================================================

-- 1. Habilitar extensao pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Criar tabela de embeddings
CREATE TABLE IF NOT EXISTS {table} (
    id bigserial PRIMARY KEY,
    chunk_id text NOT NULL UNIQUE,
    content text,
    metadata jsonb DEFAULT '{{}}'::jsonb,
    vector vector({dims}),
    created_at timestamptz DEFAULT now()
);

-- 3. Criar indice HNSW para busca vetorial
CREATE INDEX IF NOT EXISTS idx_{table}_vector_hnsw
    ON {table} USING hnsw (vector {settings.pgvector_distance_ops})
    WITH (m = {settings.pgvector_hnsw_m}, ef_construction = {settings.pgvector_hnsw_ef_construction});

-- 4. Criar indice para chunk_id (buscas e upserts)
CREATE INDEX IF NOT EXISTS idx_{table}_chunk_id ON {table} (chunk_id);

-- 5. Criar indice GIN para filtros de metadados
CREATE INDEX IF NOT EXISTS idx_{table}_metadata ON {table} USING GIN (metadata jsonb_path_ops);

-- 6. Criar funcao RPC para busca vetorial
CREATE OR REPLACE FUNCTION {func}(
    query_embedding vector({dims}),
    match_threshold float DEFAULT 0.3,
    match_count int DEFAULT 10,
    filter_metadata jsonb DEFAULT '{{}}'
)
RETURNS TABLE (
    id bigint,
    chunk_id text,
    content text,
    metadata jsonb,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.id,
        e.chunk_id,
        e.content,
        e.metadata,
        (1 - (e.vector <=> query_embedding))::float AS similarity
    FROM {table} e
    WHERE (1 - (e.vector <=> query_embedding)) >= match_threshold
      AND (filter_metadata = '{{}}' OR e.metadata @> filter_metadata)
    ORDER BY e.vector <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ============================================================
-- Setup concluido!
-- Configure no .env:
--   SUPABASE_ENABLED=true
--   SUPABASE_URL=https://seu-projeto.supabase.co
--   SUPABASE_KEY=sua-chave-anon-ou-service
--   SUPABASE_TABLE_NAME={table}
--   SUPABASE_FUNCTION_NAME={func}
-- ============================================================
"""
    return sql


def init_db():
    """
    Inicializa o banco de dados:
    1. Cria schema (se nao for public)
    2. Cria extensao pgvector
    3. Cria todas as tabelas
    4. Cria indices vetoriais e full-text

    Suporta todos os provedores vetoriais:
    - pgvector: indices criados no PostgreSQL local
    - supabase: indices criados se usando mesmo PostgreSQL, senao gera SQL
    - qdrant: sem indices locais (colecao criada pelo factory)
    """
    schema = settings.database_schema
    providers = settings.enabled_vector_providers

    print(f"Initializing database...")
    print(f"  Schema: {schema}")
    print(f"  Vector providers: {', '.join(providers)}")
    print(f"  Primary provider: {settings.vector_db_primary}")
    print(f"  Embedding mode: {settings.embedding_mode.value}")
    print(f"  Embedding dimensions: {settings.active_embedding_dimensions}")

    # 1. Criar schema se nao for public
    create_schema()

    # 2. Criar extensao pgvector
    create_vector_extension()

    # 3. Criar tabelas
    try:
        Base.metadata.create_all(bind=engine)
        print("  Tables created")
    except Exception as e:
        print(f"  Error creating tables: {e}")
        raise

    # 3b. Migracao leve: adicionar colunas novas em tabelas existentes
    try:
        apply_lightweight_migrations()
    except Exception as e:
        print(f"  Lightweight migration warning: {e}")

    # 4. Criar indices vetoriais (para provedores que usam PostgreSQL local)
    # pgvector sempre cria indices no PostgreSQL local
    # supabase cria indices se usar o mesmo PostgreSQL (pgvector_database_url == database_url)
    providers_needing_local_indexes = {"pgvector"}

    # Se supabase esta habilitado e usa o mesmo banco, tambem criar indices
    if "supabase" in providers and not settings.supabase_url:
        providers_needing_local_indexes.add("supabase")

    if providers_needing_local_indexes.intersection(set(providers)):
        create_vector_indexes()
    else:
        print("  Vector indexes: skipped (provider manages its own indexes)")

    # 5. Informar sobre setup externo se necessario
    if "supabase" in providers and settings.supabase_url:
        print(f"\n  [SUPABASE] O Supabase usa indices gerenciados remotamente.")
        print(f"  Execute o SQL de setup no Supabase SQL Editor:")
        print(f"    python -m app.db.init_db --supabase-sql")

    if "qdrant" in providers:
        print(f"\n  [QDRANT] Colecao sera criada automaticamente no startup da aplicacao.")
        print(f"  Certifique-se de que o Qdrant esta rodando em: {settings.qdrant_url}")

    print("\n  Database initialized successfully!")
    print(f"  Vector DB providers: {', '.join(providers)}")
    print(f"  To init roles: python -m app.db.init_roles")


def apply_lightweight_migrations():
    """
    Aplica migracoes leves adicionando colunas novas em tabelas ja existentes.

    Usa ALTER TABLE ADD COLUMN IF NOT EXISTS (Postgres 9.6+) para ser seguro
    em bancos pre-existentes. Nao substitui uma ferramenta de migracao completa,
    mas evita a necessidade de Alembic para adicoes simples.
    """
    schema_prefix = _schema_prefix()
    candidates_table = f"{schema_prefix}candidates"

    migrations = [
        f"ALTER TABLE {candidates_table} ADD COLUMN IF NOT EXISTS professional_title VARCHAR",
        f"ALTER TABLE {candidates_table} ADD COLUMN IF NOT EXISTS professional_summary TEXT",
        f"ALTER TABLE {candidates_table} ADD COLUMN IF NOT EXISTS linkedin_url VARCHAR",
        f"ALTER TABLE {candidates_table} ADD COLUMN IF NOT EXISTS photo_url VARCHAR",
    ]

    with engine.begin() as connection:
        for stmt in migrations:
            try:
                connection.execute(text(stmt))
            except Exception as e:
                print(f"  [migration] ignorada ({stmt[:60]}...): {e}")

    print("  Lightweight migrations applied (candidates: professional_title, professional_summary, linkedin_url, photo_url)")


def drop_all_tables():
    """Remove todas as tabelas"""
    print("WARNING: Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    print("All tables dropped")

    schema = settings.database_schema
    if schema and schema != "public":
        print(f"  Schema '{schema}' mantido (remova manualmente se desejar)")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--drop":
        confirm = input("Are you sure? (yes/no): ")
        if confirm.lower() == "yes":
            drop_all_tables()
        else:
            print("Cancelled")
    elif len(sys.argv) > 1 and sys.argv[1] == "--supabase-sql":
        print(generate_supabase_setup_sql())
    else:
        init_db()
