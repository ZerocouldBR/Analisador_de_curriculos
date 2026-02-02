"""
Script para inicialização do banco de dados
Cria as tabelas, extensões e índices vetoriais necessários

Inclui:
- Extensão pgvector
- Índice HNSW para busca vetorial eficiente
- Índices de texto para full-text search
"""

from sqlalchemy import text
from app.db.database import engine, Base
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
    AuditLog
)


def create_vector_indexes():
    """
    Cria índices vetoriais HNSW para busca eficiente

    HNSW (Hierarchical Navigable Small World) oferece:
    - Busca aproximada muito rápida
    - Bom trade-off entre velocidade e precisão
    - Melhor performance para grandes volumes de dados
    """
    print("Criando índices vetoriais...")

    with engine.connect() as connection:
        # Índice HNSW para busca por similaridade de cosseno
        try:
            # Primeiro, verificar se o índice já existe
            result = connection.execute(text("""
                SELECT indexname FROM pg_indexes
                WHERE indexname = 'idx_embeddings_vector_hnsw'
            """))

            if result.fetchone() is None:
                # Criar índice HNSW com parâmetros otimizados
                # m: número de conexões por nó (16 é bom para 1536 dims)
                # ef_construction: qualidade da construção (maior = melhor mas mais lento)
                connection.execute(text("""
                    CREATE INDEX idx_embeddings_vector_hnsw
                    ON embeddings
                    USING hnsw (vector vector_cosine_ops)
                    WITH (m = 16, ef_construction = 64);
                """))
                connection.commit()
                print("✓ Índice HNSW criado para embeddings")
            else:
                print("✓ Índice HNSW já existe")

        except Exception as e:
            print(f"⚠ Erro ao criar índice HNSW: {e}")
            print("  O índice pode já existir ou a versão do pgvector não suporta HNSW")

        # Criar índice GIN para busca full-text em português
        try:
            result = connection.execute(text("""
                SELECT indexname FROM pg_indexes
                WHERE indexname = 'idx_chunks_content_fts'
            """))

            if result.fetchone() is None:
                connection.execute(text("""
                    CREATE INDEX idx_chunks_content_fts
                    ON chunks
                    USING GIN (to_tsvector('portuguese', content));
                """))
                connection.commit()
                print("✓ Índice GIN para full-text search criado")
            else:
                print("✓ Índice GIN já existe")

        except Exception as e:
            print(f"⚠ Erro ao criar índice GIN: {e}")

        # Criar índice para meta_json (keywords)
        try:
            result = connection.execute(text("""
                SELECT indexname FROM pg_indexes
                WHERE indexname = 'idx_chunks_meta_json'
            """))

            if result.fetchone() is None:
                connection.execute(text("""
                    CREATE INDEX idx_chunks_meta_json
                    ON chunks
                    USING GIN (meta_json jsonb_path_ops);
                """))
                connection.commit()
                print("✓ Índice GIN para metadados JSON criado")
            else:
                print("✓ Índice GIN para JSON já existe")

        except Exception as e:
            print(f"⚠ Erro ao criar índice GIN para JSON: {e}")

    print("✓ Índices vetoriais configurados")


def init_db():
    """
    Inicializa o banco de dados:
    1. Cria extensão pgvector
    2. Cria todas as tabelas
    3. Cria índices vetoriais HNSW
    4. Inicializa roles padrão (opcional)
    """
    print("Inicializando banco de dados...")

    # Criar extensão pgvector
    with engine.connect() as connection:
        try:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            connection.commit()
            print("✓ Extensão pgvector criada/verificada")
        except Exception as e:
            print(f"⚠ Erro ao criar extensão pgvector: {e}")
            print("  Certifique-se de que a extensão pgvector está instalada no PostgreSQL")

    # Criar todas as tabelas
    try:
        Base.metadata.create_all(bind=engine)
        print("✓ Tabelas criadas com sucesso")
    except Exception as e:
        print(f"✗ Erro ao criar tabelas: {e}")
        raise

    # Criar índices vetoriais
    create_vector_indexes()

    print("✓ Banco de dados inicializado com sucesso!")
    print("\nPara inicializar roles e superuser padrão, execute:")
    print("  python -m app.db.init_roles")


def drop_all_tables():
    """
    Remove todas as tabelas (usar com cuidado!)
    """
    print("⚠ ATENÇÃO: Removendo todas as tabelas...")
    Base.metadata.drop_all(bind=engine)
    print("✓ Todas as tabelas foram removidas")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--drop":
        confirm = input("Tem certeza que deseja remover todas as tabelas? (yes/no): ")
        if confirm.lower() == "yes":
            drop_all_tables()
        else:
            print("Operação cancelada")
    else:
        init_db()
