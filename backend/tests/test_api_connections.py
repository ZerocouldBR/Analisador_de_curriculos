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


# ============================================
# Redis Connection Tests
# ============================================

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


# ============================================
# OpenAI API Tests
# ============================================

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
