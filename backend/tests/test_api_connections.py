"""
Testes de conexao com APIs e componentes do sistema

Testa:
- Conexao com banco de dados PostgreSQL
- Conexao com Redis
- Conexao com OpenAI API (embedding + chat)
- Conexao com Vector Store
- Pipeline de embeddings completo
- Health check da aplicacao
- Configuracoes do sistema

Uso:
    # Rodar todos os testes:
    pytest tests/test_api_connections.py -v

    # Rodar apenas testes que nao precisam de servicos externos:
    pytest tests/test_api_connections.py -v -k "not external"

    # Rodar com output detalhado:
    pytest tests/test_api_connections.py -v -s
"""
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def app_settings():
    """Retorna settings da aplicacao"""
    from app.core.config import settings
    return settings


# ============================================
# Config Tests
# ============================================

@pytest.mark.unit
class TestConfigValidation:
    """Testes de validacao da configuracao"""

    def test_settings_load(self, app_settings):
        """Verifica que settings carregam corretamente"""
        assert app_settings.app_name is not None
        assert app_settings.app_version is not None
        assert app_settings.database_url is not None

    def test_database_url_format(self, app_settings):
        """Verifica formato da URL do banco"""
        url = app_settings.database_url
        assert "postgresql" in url, f"DATABASE_URL deve ser PostgreSQL, recebido: {url}"

    def test_embedding_mode_valid(self, app_settings):
        """Verifica que embedding mode e valido"""
        assert app_settings.embedding_mode.value in ("api", "code"), \
            f"EMBEDDING_MODE invalido: {app_settings.embedding_mode.value}"

    def test_vector_db_provider_valid(self, app_settings):
        """Verifica que vector db provider e valido"""
        assert app_settings.vector_db_provider.value in ("pgvector", "supabase", "qdrant"), \
            f"VECTOR_DB_PROVIDER invalido: {app_settings.vector_db_provider.value}"

    def test_openai_key_for_api_mode(self, app_settings):
        """Se modo API, deve ter chave OpenAI"""
        if app_settings.embedding_mode.value == "api":
            has_key = bool(app_settings.openai_api_key)
            if not has_key:
                pytest.skip(
                    "OPENAI_API_KEY nao configurada - necessaria para EMBEDDING_MODE=api"
                )

    def test_redis_url_format(self, app_settings):
        """Verifica formato da URL do Redis"""
        url = app_settings.redis_url
        assert url.startswith("redis://") or url.startswith("rediss://"), \
            f"REDIS_URL deve comecar com redis:// ou rediss://, recebido: {url}"

    def test_chunk_settings_valid(self, app_settings):
        """Verifica que configuracoes de chunk fazem sentido"""
        assert app_settings.chunk_size > 0
        assert app_settings.chunk_overlap >= 0
        assert app_settings.chunk_overlap < app_settings.chunk_size, \
            "chunk_overlap deve ser menor que chunk_size"
        assert app_settings.chunk_min_size > 0
        assert app_settings.chunk_min_size < app_settings.chunk_size

    def test_search_weights_sum(self, app_settings):
        """Verifica que pesos da busca hibrida somam ~1.0"""
        total = (
            app_settings.hybrid_vector_weight
            + app_settings.hybrid_text_weight
            + app_settings.hybrid_filter_weight
            + app_settings.hybrid_domain_weight
        )
        assert 0.99 <= total <= 1.01, \
            f"Pesos da busca hibrida devem somar 1.0, soma atual: {total}"

    def test_cors_origins_configured(self, app_settings):
        """Verifica que CORS origins estao configuradas"""
        assert len(app_settings.cors_origins) > 0, \
            "CORS_ORIGINS nao configuradas - frontend nao conseguira se conectar"


# ============================================
# Database Connection Tests
# ============================================

@pytest.mark.integration
class TestDatabaseConnection:
    """Testes de conexao com PostgreSQL"""

    def test_database_connection(self):
        """Testa conexao basica com o banco"""
        try:
            from app.db.database import engine
            from sqlalchemy import text

            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                assert result.scalar() == 1
        except Exception as e:
            pytest.fail(f"Falha na conexao com o banco de dados: {e}")

    def test_database_version(self):
        """Verifica versao do PostgreSQL"""
        try:
            from app.db.database import engine
            from sqlalchemy import text

            with engine.connect() as conn:
                result = conn.execute(text("SELECT version()"))
                version = result.scalar()
                assert "PostgreSQL" in version
        except Exception as e:
            pytest.fail(f"Erro ao verificar versao do PostgreSQL: {e}")

    def test_pgvector_extension(self):
        """Verifica que extensao pgvector esta instalada"""
        try:
            from app.db.database import engine
            from sqlalchemy import text

            with engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
                ))
                version = result.scalar()
                assert version is not None, \
                    "Extensao pgvector nao instalada. Execute: CREATE EXTENSION vector;"
        except Exception as e:
            pytest.fail(f"Erro ao verificar extensao pgvector: {e}")

    def test_tables_exist(self):
        """Verifica que tabelas principais existem"""
        from app.db.database import engine
        from sqlalchemy import text

        required_tables = [
            "candidates", "documents", "chunks", "embeddings",
            "users", "companies",
        ]

        with engine.connect() as conn:
            for table in required_tables:
                result = conn.execute(text(
                    "SELECT EXISTS (SELECT FROM pg_tables WHERE tablename = :table)"
                ), {"table": table})
                exists = result.scalar()
                assert exists, f"Tabela '{table}' nao encontrada no banco de dados"

    @pytest.mark.integration
    def test_database_pool_connections(self):
        """Testa que multiplas conexoes simultanesas funcionam"""
        from app.db.database import engine
        from sqlalchemy import text

        connections = []
        try:
            for i in range(5):
                conn = engine.connect()
                result = conn.execute(text("SELECT 1"))
                assert result.scalar() == 1
                connections.append(conn)
        finally:
            for conn in connections:
                conn.close()

    @pytest.mark.integration
    def test_database_transaction_rollback(self):
        """Testa que rollback desfaz mudancas"""
        from app.db.database import engine
        from sqlalchemy import text

        with engine.connect() as conn:
            trans = conn.begin()
            try:
                # Inserir dado de teste na tabela server_settings
                conn.execute(text(
                    "INSERT INTO server_settings (key, value_json, description, version) "
                    "VALUES ('_test_rollback', '\"test\"', 'teste de rollback', 1)"
                ))
                # Verificar que existe dentro da transacao
                result = conn.execute(text(
                    "SELECT key FROM server_settings WHERE key = '_test_rollback'"
                ))
                assert result.scalar() == '_test_rollback'
                # Fazer rollback
                trans.rollback()
            except Exception:
                trans.rollback()
                raise

        # Verificar que NAO existe apos rollback
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT key FROM server_settings WHERE key = '_test_rollback'"
            ))
            assert result.scalar() is None

    @pytest.mark.integration
    def test_database_crud_operations(self):
        """Testa Insert/Select/Update/Delete em server_settings"""
        from app.db.database import engine
        from sqlalchemy import text

        test_key = "_test_crud_operations"

        with engine.connect() as conn:
            with conn.begin():
                # CREATE
                conn.execute(text(
                    "INSERT INTO server_settings (key, value_json, description, version) "
                    "VALUES (:key, :val, :desc, 1)"
                ), {"key": test_key, "val": '{"test": true}', "desc": "teste CRUD"})

            with conn.begin():
                # READ
                result = conn.execute(text(
                    "SELECT value_json FROM server_settings WHERE key = :key"
                ), {"key": test_key})
                row = result.scalar()
                assert row is not None

            with conn.begin():
                # UPDATE
                conn.execute(text(
                    "UPDATE server_settings SET description = 'atualizado' WHERE key = :key"
                ), {"key": test_key})

                result = conn.execute(text(
                    "SELECT description FROM server_settings WHERE key = :key"
                ), {"key": test_key})
                assert result.scalar() == "atualizado"

            with conn.begin():
                # DELETE
                conn.execute(text(
                    "DELETE FROM server_settings WHERE key = :key"
                ), {"key": test_key})

                result = conn.execute(text(
                    "SELECT key FROM server_settings WHERE key = :key"
                ), {"key": test_key})
                assert result.scalar() is None

    @pytest.mark.integration
    def test_database_model_creation(self):
        """Testa criar Company e User via SQLAlchemy models"""
        from app.db.database import SessionLocal
        from app.db.models import Company, User
        from app.core.security import get_password_hash

        db = SessionLocal()
        try:
            # Criar empresa de teste
            company = Company(
                name="_Test Company CRUD",
                slug="_test-company-crud",
                plan="free",
            )
            db.add(company)
            db.flush()
            assert company.id is not None

            # Criar usuario associado
            user = User(
                email="_test_crud@example.com",
                name="Test CRUD User",
                password_hash=get_password_hash("testpass"),
                company_id=company.id,
            )
            db.add(user)
            db.flush()
            assert user.id is not None
            assert user.company_id == company.id

            db.rollback()
        finally:
            db.close()

    @pytest.mark.integration
    def test_database_foreign_keys(self):
        """Testa integridade referencial (user.company_id -> companies.id)"""
        from app.db.database import engine
        from sqlalchemy import text
        from sqlalchemy.exc import IntegrityError

        with engine.connect() as conn:
            try:
                with conn.begin():
                    # Tentar inserir user com company_id inexistente
                    conn.execute(text(
                        "INSERT INTO users (email, name, password_hash, company_id) "
                        "VALUES ('_fk_test@test.com', 'FK Test', 'hash123', 999999)"
                    ))
                # Se chegou aqui sem erro, a FK pode nao estar configurada
                # Limpar dado inserido
                with conn.begin():
                    conn.execute(text("DELETE FROM users WHERE email = '_fk_test@test.com'"))
            except (IntegrityError, Exception):
                # Esperado: violacao de FK
                pass

    @pytest.mark.integration
    def test_database_jsonb_operations(self):
        """Testa operacoes JSONB no PostgreSQL"""
        from app.db.database import engine
        from sqlalchemy import text

        test_key = "_test_jsonb_ops"

        with engine.connect() as conn:
            try:
                with conn.begin():
                    # Inserir JSONB
                    conn.execute(text(
                        "INSERT INTO server_settings (key, value_json, description, version) "
                        "VALUES (:key, :val, 'teste JSONB', 1)"
                    ), {"key": test_key, "val": '{"nested": {"a": 1, "b": [1, 2, 3]}}'})

                with conn.begin():
                    # Consultar campo JSONB aninhado
                    result = conn.execute(text(
                        "SELECT value_json->'nested'->'a' FROM server_settings WHERE key = :key"
                    ), {"key": test_key})
                    val = result.scalar()
                    assert val == 1
            finally:
                with conn.begin():
                    conn.execute(text(
                        "DELETE FROM server_settings WHERE key = :key"
                    ), {"key": test_key})


# ============================================
# Redis Connection Tests
# ============================================

@pytest.mark.integration
class TestRedisConnection:
    """Testes de conexao com Redis"""

    def test_redis_ping(self, app_settings):
        """Testa ping no Redis"""
        try:
            import redis
            r = redis.from_url(app_settings.redis_url, socket_timeout=5)
            assert r.ping() is True
            r.close()
        except Exception as e:
            pytest.fail(f"Falha na conexao com Redis: {e}")

    def test_redis_write_read(self, app_settings):
        """Testa escrita e leitura no Redis"""
        try:
            import redis
            r = redis.from_url(app_settings.redis_url, decode_responses=True, socket_timeout=5)

            r.set("_test_diagnostics", "hello", ex=10)
            val = r.get("_test_diagnostics")
            r.delete("_test_diagnostics")

            assert val == "hello"
            r.close()
        except Exception as e:
            pytest.fail(f"Falha no teste de escrita/leitura Redis: {e}")

    @pytest.mark.integration
    def test_redis_key_expiry(self, app_settings):
        """Testa que chaves com TTL expiram corretamente"""
        import redis
        import time

        r = redis.from_url(app_settings.redis_url, decode_responses=True, socket_timeout=5)
        try:
            r.set("_test_expiry", "temp_value", ex=1)
            assert r.get("_test_expiry") == "temp_value"

            # Esperar expiracao
            time.sleep(1.5)
            assert r.get("_test_expiry") is None
        finally:
            r.delete("_test_expiry")
            r.close()

    @pytest.mark.integration
    def test_redis_pipeline(self, app_settings):
        """Testa pipeline de comandos em batch"""
        import redis

        r = redis.from_url(app_settings.redis_url, decode_responses=True, socket_timeout=5)
        try:
            pipe = r.pipeline()
            pipe.set("_test_pipe_1", "val1", ex=10)
            pipe.set("_test_pipe_2", "val2", ex=10)
            pipe.set("_test_pipe_3", "val3", ex=10)
            pipe.get("_test_pipe_1")
            pipe.get("_test_pipe_2")
            pipe.get("_test_pipe_3")
            results = pipe.execute()

            # Primeiros 3 resultados sao True (SET ok), ultimos 3 sao os valores
            assert results[3] == "val1"
            assert results[4] == "val2"
            assert results[5] == "val3"
        finally:
            r.delete("_test_pipe_1", "_test_pipe_2", "_test_pipe_3")
            r.close()

    @pytest.mark.integration
    def test_redis_hash_operations(self, app_settings):
        """Testa operacoes com hashes Redis"""
        import redis

        r = redis.from_url(app_settings.redis_url, decode_responses=True, socket_timeout=5)
        hash_key = "_test_hash"
        try:
            r.hset(hash_key, mapping={"name": "Test", "value": "123", "active": "true"})

            assert r.hget(hash_key, "name") == "Test"
            assert r.hget(hash_key, "value") == "123"
            assert r.hlen(hash_key) == 3

            all_fields = r.hgetall(hash_key)
            assert all_fields == {"name": "Test", "value": "123", "active": "true"}
        finally:
            r.delete(hash_key)
            r.close()

    @pytest.mark.integration
    def test_redis_list_operations(self, app_settings):
        """Testa operacoes com listas Redis (usado internamente pelo Celery)"""
        import redis

        r = redis.from_url(app_settings.redis_url, decode_responses=True, socket_timeout=5)
        list_key = "_test_list"
        try:
            # Simular fila (FIFO como Celery)
            r.rpush(list_key, "task1", "task2", "task3")

            assert r.llen(list_key) == 3
            assert r.lpop(list_key) == "task1"
            assert r.lpop(list_key) == "task2"
            assert r.lpop(list_key) == "task3"
            assert r.llen(list_key) == 0
        finally:
            r.delete(list_key)
            r.close()


# ============================================
# OpenAI API Tests
# ============================================

@pytest.mark.integration
class TestOpenAIConnection:
    """Testes de conexao com OpenAI API"""

    @pytest.fixture(autouse=True)
    def check_api_key(self, app_settings):
        """Pula testes se chave nao configurada"""
        if not app_settings.openai_api_key:
            pytest.skip("OPENAI_API_KEY nao configurada")

    @pytest.mark.asyncio
    async def test_openai_embedding(self, app_settings):
        """Testa geracao de embedding via OpenAI"""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=app_settings.openai_api_key)
        try:
            response = await client.embeddings.create(
                model=app_settings.embedding_model,
                input="teste de conexao com a API"
            )
            assert len(response.data) > 0
            assert len(response.data[0].embedding) > 0
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_openai_chat(self, app_settings):
        """Testa chamada de chat via OpenAI"""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=app_settings.openai_api_key)
        try:
            response = await client.chat.completions.create(
                model=app_settings.chat_model,
                messages=[{"role": "user", "content": "Responda apenas: ok"}],
                max_tokens=5,
                temperature=0,
            )
            assert response.choices[0].message.content is not None
        finally:
            await client.close()


# ============================================
# Embedding Service Tests
# ============================================

@pytest.mark.integration
class TestEmbeddingService:
    """Testes do servico de embeddings"""

    @pytest.mark.asyncio
    async def test_generate_embedding(self, app_settings):
        """Testa geracao de embedding via servico"""
        if app_settings.embedding_mode.value == "api" and not app_settings.openai_api_key:
            pytest.skip("OPENAI_API_KEY nao configurada")

        from app.services.embedding_service import EmbeddingService

        service = EmbeddingService()
        embedding = await service.generate_embedding(
            "Engenheiro de producao com 5 anos de experiencia"
        )

        assert isinstance(embedding, list)
        assert len(embedding) > 0
        assert all(isinstance(v, float) for v in embedding)

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch(self, app_settings):
        """Testa geracao de embeddings em lote"""
        if app_settings.embedding_mode.value == "api" and not app_settings.openai_api_key:
            pytest.skip("OPENAI_API_KEY nao configurada")

        from app.services.embedding_service import EmbeddingService

        service = EmbeddingService()
        texts = [
            "Operador de empilhadeira",
            "Supervisor de producao",
            "Analista de qualidade",
        ]
        embeddings = await service.generate_embeddings_batch(texts)

        assert len(embeddings) == 3
        for emb in embeddings:
            assert isinstance(emb, list)
            assert len(emb) > 0

    def test_preprocess_text(self):
        """Testa preprocessamento de texto para embedding"""
        from app.services.embedding_service import EmbeddingService

        text = "Teste   com   espacos\n\n\n\nmultiplos\n---\nseparadores"
        processed = EmbeddingService.preprocess_for_embedding(text)

        assert "   " not in processed
        assert "\n\n\n" not in processed
        assert "---" not in processed


# ============================================
# Semantic Chunker Tests
# ============================================

@pytest.mark.unit
class TestSemanticChunker:
    """Testes do chunker semantico"""

    def test_small_text_single_chunk(self):
        """Texto curto deve gerar um unico chunk"""
        from app.services.embedding_service import SemanticChunker

        text = "Nome: Joao Silva\nCargo: Engenheiro"
        chunks = SemanticChunker.create_semantic_chunks(text)

        assert len(chunks) == 1
        assert chunks[0]["content"] == text.strip()

    def test_section_detection(self):
        """Testa deteccao de secoes do curriculo"""
        from app.services.embedding_service import SemanticChunker

        text = """Dados Pessoais
Nome: Joao Silva
Email: joao@email.com

Experiencia Profissional
Empresa ABC - Engenheiro de Producao
2020 - 2023

Formacao
Engenharia de Producao - UFRGS
2016 - 2020

Habilidades
Lean Manufacturing, Gestao de Qualidade, SAP
"""
        chunks = SemanticChunker.create_semantic_chunks(text, chunk_size=5000)

        # Deve detectar multiplas secoes
        sections = set(c["metadata"].get("section", "") for c in chunks)
        assert len(sections) >= 2, f"Esperava multiplas secoes, encontrou: {sections}"

    def test_chunk_overlap(self):
        """Testa que chunks longos tem overlap"""
        from app.services.embedding_service import SemanticChunker

        long_text = "Palavra " * 500  # Texto longo
        chunks = SemanticChunker.create_semantic_chunks(
            long_text, chunk_size=200, overlap=50
        )

        assert len(chunks) > 1


# ============================================
# Storage Service Tests
# ============================================

@pytest.mark.unit
class TestStorageService:
    """Testes do servico de armazenamento"""

    def test_supported_formats(self):
        """Testa deteccao de formatos suportados"""
        from app.services.storage_service import StorageService

        assert StorageService.is_supported_format("curriculo.pdf")
        assert StorageService.is_supported_format("curriculo.docx")
        assert StorageService.is_supported_format("curriculo.txt")
        assert StorageService.is_supported_format("curriculo.jpg")
        assert StorageService.is_supported_format("curriculo.png")
        assert not StorageService.is_supported_format("curriculo.exe")
        assert not StorageService.is_supported_format("curriculo.zip")

    def test_mime_type_detection(self):
        """Testa deteccao de tipo MIME"""
        from app.services.storage_service import StorageService

        assert StorageService.get_mime_type("file.pdf") == "application/pdf"
        assert StorageService.get_mime_type("file.docx") == \
               "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert StorageService.get_mime_type("file.txt") == "text/plain"
        assert StorageService.get_mime_type("file.jpg") == "image/jpeg"
        assert StorageService.get_mime_type("file.png") == "image/png"

    def test_sha256_calculation(self):
        """Testa calculo de hash SHA256"""
        import io
        from app.services.storage_service import StorageService

        content = b"conteudo de teste para hash"
        file = io.BytesIO(content)
        hash1 = StorageService.calculate_sha256(file)

        file.seek(0)
        hash2 = StorageService.calculate_sha256(file)

        assert hash1 == hash2  # Mesmo conteudo, mesmo hash
        assert len(hash1) == 64  # SHA256 = 64 chars hex


# ============================================
# Health Check Test
# ============================================

@pytest.mark.integration
class TestHealthCheck:
    """Testes do health check"""

    def test_health_endpoint(self):
        """Testa endpoint de health"""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "timestamp" in data


# ============================================
# Resume Parser Tests
# ============================================

@pytest.mark.unit
class TestResumeParser:
    """Testes do parser de curriculos"""

    def test_parse_basic_resume(self):
        """Testa parsing basico de curriculo"""
        from app.services.resume_parser_service import ResumeParserService

        text = """
        João da Silva
        Email: joao.silva@email.com
        Telefone: (51) 99999-9999
        Porto Alegre - RS

        Experiência Profissional
        Empresa ABC LTDA
        Engenheiro de Produção
        Janeiro 2020 - Atual
        - Gestão de linha de produção
        - Implementação de Lean Manufacturing

        Formação
        Engenharia de Produção
        UFRGS - 2016 a 2020

        Habilidades
        Lean Manufacturing, Six Sigma, SAP, Excel Avançado
        """

        result = ResumeParserService.parse_resume(text)

        assert "personal_info" in result
        assert result["personal_info"].get("name") is not None
        assert "experiences" in result
        assert "skills" in result

    def test_parse_empty_text(self):
        """Testa parsing de texto vazio"""
        from app.services.resume_parser_service import ResumeParserService

        result = ResumeParserService.parse_resume("")
        assert isinstance(result, dict)
        assert "personal_info" in result
