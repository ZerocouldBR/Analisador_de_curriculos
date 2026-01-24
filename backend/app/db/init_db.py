"""
Script para inicialização do banco de dados
Cria as tabelas e extensões necessárias
"""

from sqlalchemy import text
from app.db.database import engine, Base
from app.db.models import (
    User,
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


def init_db():
    """
    Inicializa o banco de dados:
    1. Cria extensão pgvector
    2. Cria todas as tabelas
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

    print("✓ Banco de dados inicializado com sucesso!")


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
