import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)


def _validate_schema_name(schema: str) -> str:
    """Valida nome do schema contra padroes seguros"""
    import re
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]{0,62}$', schema):
        raise ValueError(
            f"Nome de schema invalido: '{schema}'. "
            "Use apenas letras, numeros e underscore."
        )
    return schema


def create_configured_engine(database_url: str, schema: str = None):
    """
    Cria um engine SQLAlchemy configurado com pool e schema.

    Usado pelo database.py principal e pelo pgvector_store.py para
    garantir que ambos usem a mesma configuracao de pool e schema.

    Args:
        database_url: URL de conexao com o banco
        schema: Schema PostgreSQL (default: settings.database_schema)

    Returns:
        Engine SQLAlchemy configurado
    """
    schema = schema or settings.database_schema

    connect_args = {}
    if schema and schema != "public":
        _validate_schema_name(schema)
        connect_args["options"] = f"-csearch_path={schema},public"

    new_engine = create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout,
        connect_args=connect_args,
    )

    if schema and schema != "public":
        logger.info(f"Engine criado com search_path: {schema},public")

    return new_engine


engine = create_configured_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency para obter sessao do banco de dados"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
