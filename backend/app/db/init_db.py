"""
Script para inicializacao do banco de dados

Cria tabelas, extensoes e indices.
Todos os parametros vem de settings (nada hardcoded).
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
)


def create_vector_indexes():
    """Cria indices vetoriais e full-text usando parametros de settings"""
    print("Criando indices...")

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
                        f"ON embeddings USING hnsw (vector {settings.pgvector_distance_ops}) "
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
            result = connection.execute(text(
                "SELECT indexname FROM pg_indexes "
                "WHERE indexname = 'idx_chunks_content_fts'"
            ))
            if result.fetchone() is None:
                connection.execute(text(
                    f"CREATE INDEX idx_chunks_content_fts "
                    f"ON chunks USING GIN ("
                    f"to_tsvector('{settings.fts_language}', content));"
                ))
                connection.commit()
                print(f"  FTS index created (language={settings.fts_language})")
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
                    "CREATE INDEX idx_chunks_meta_json "
                    "ON chunks USING GIN (meta_json jsonb_path_ops);"
                ))
                connection.commit()
                print("  JSON metadata index created")
            else:
                print("  JSON metadata index already exists")
        except Exception as e:
            print(f"  Warning: JSON index: {e}")

    print("  Indices configurados")


def init_db():
    """
    Inicializa o banco de dados:
    1. Cria extensao pgvector
    2. Cria todas as tabelas
    3. Cria indices
    """
    print(f"Initializing database...")
    print(f"  Provider: {settings.vector_db_provider.value}")
    print(f"  Embedding model: {settings.embedding_model}")
    print(f"  Embedding dimensions: {settings.embedding_dimensions}")

    # Criar extensao pgvector (se usando pgvector ou supabase)
    if settings.vector_db_provider.value in ("pgvector", "supabase"):
        with engine.connect() as connection:
            try:
                connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                connection.commit()
                print("  pgvector extension verified")
            except Exception as e:
                print(f"  Warning: pgvector extension: {e}")

    # Criar tabelas
    try:
        Base.metadata.create_all(bind=engine)
        print("  Tables created")
    except Exception as e:
        print(f"  Error creating tables: {e}")
        raise

    # Criar indices (se usando pgvector)
    if settings.vector_db_provider.value in ("pgvector",):
        create_vector_indexes()

    print("  Database initialized successfully")
    print(f"\n  Vector DB: {settings.vector_db_provider.value}")
    print(f"  To init roles: python -m app.db.init_roles")


def drop_all_tables():
    """Remove todas as tabelas"""
    print("WARNING: Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    print("All tables dropped")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--drop":
        confirm = input("Are you sure? (yes/no): ")
        if confirm.lower() == "yes":
            drop_all_tables()
        else:
            print("Cancelled")
    else:
        init_db()
