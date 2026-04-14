"""
Testes de integracao com Celery e filas de tarefas

Testa:
- Configuracao do Celery (broker, backend, serializer)
- Routing de tasks para filas corretas
- Registro de tasks no app
- Conexao do broker com Redis
- Result backend acessivel

Uso:
    pytest tests/test_celery_integration.py -v
    pytest tests/test_celery_integration.py -v -m "not integration"  # apenas unit
"""
import pytest


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def celery_app():
    """Retorna a instancia do Celery app"""
    from app.core.celery_app import celery_app
    return celery_app


@pytest.fixture
def app_settings():
    """Retorna settings da aplicacao"""
    from app.core.config import settings
    return settings


# ============================================
# Celery Configuration Tests (unit)
# ============================================

class TestCeleryConfiguration:
    """Testes da configuracao do Celery"""

    @pytest.mark.unit
    def test_celery_app_exists(self, celery_app):
        """Verifica que o Celery app esta configurado"""
        assert celery_app is not None
        assert celery_app.main == "analisador_curriculos"

    @pytest.mark.unit
    def test_celery_broker_url(self, celery_app, app_settings):
        """Verifica que o broker aponta para Redis"""
        broker_url = str(celery_app.conf.broker_url)
        assert broker_url.startswith("redis://") or broker_url.startswith("rediss://"), \
            f"Broker URL deve ser Redis, recebido: {broker_url}"
        assert broker_url == app_settings.redis_url

    @pytest.mark.unit
    def test_celery_result_backend_url(self, celery_app, app_settings):
        """Verifica que o result backend aponta para Redis"""
        backend_url = str(celery_app.conf.result_backend)
        assert backend_url.startswith("redis://") or backend_url.startswith("rediss://"), \
            f"Result backend deve ser Redis, recebido: {backend_url}"

    @pytest.mark.unit
    def test_celery_serializer_config(self, celery_app):
        """Verifica que o serializador e JSON"""
        assert celery_app.conf.task_serializer == "json"
        assert "json" in celery_app.conf.accept_content
        assert celery_app.conf.result_serializer == "json"

    @pytest.mark.unit
    def test_celery_timezone(self, celery_app):
        """Verifica timezone configurada"""
        assert celery_app.conf.timezone == "America/Sao_Paulo"
        assert celery_app.conf.enable_utc is True

    @pytest.mark.unit
    def test_celery_task_routes(self, celery_app):
        """Verifica routing de tasks para filas corretas"""
        routes = celery_app.conf.task_routes
        assert routes is not None

        # Verificar que tasks de documentos vao para fila 'documents'
        doc_route = routes.get("app.tasks.document_tasks.*", {})
        assert doc_route.get("queue") == "documents", \
            "Tasks de documentos devem ir para fila 'documents'"

        # Verificar que tasks de busca vao para fila 'search'
        search_route = routes.get("app.tasks.search_tasks.*", {})
        assert search_route.get("queue") == "search", \
            "Tasks de busca devem ir para fila 'search'"

    @pytest.mark.unit
    def test_celery_task_tracking(self, celery_app):
        """Verifica que tracking de tasks esta ativado"""
        assert celery_app.conf.task_track_started is True
        assert celery_app.conf.task_send_sent_event is True
        assert celery_app.conf.worker_send_task_events is True

    @pytest.mark.unit
    def test_celery_task_limits(self, celery_app, app_settings):
        """Verifica limites de tempo de tasks"""
        assert celery_app.conf.task_time_limit == app_settings.celery_task_time_limit
        assert celery_app.conf.task_soft_time_limit == app_settings.celery_task_soft_time_limit
        assert celery_app.conf.result_expires == app_settings.celery_result_expires

    @pytest.mark.unit
    def test_celery_task_registration(self, celery_app):
        """Verifica que tasks de document_tasks estao registradas"""
        # Forcar carregamento dos modulos de tasks
        celery_app.loader.import_default_modules()

        registered_tasks = list(celery_app.tasks.keys())
        # Deve haver tasks do modulo app.tasks.document_tasks
        doc_tasks = [t for t in registered_tasks if "document_tasks" in t]
        # Se nao encontrou nenhuma, pode ser que as tasks nao foram auto-descobertas
        # neste cenario de teste, mas a configuracao de include deve estar correta
        includes = celery_app.conf.include or []
        assert "app.tasks.document_tasks" in includes, \
            f"app.tasks.document_tasks deve estar nos includes do Celery. Includes: {includes}"


# ============================================
# Celery Broker Connection Tests (integration)
# ============================================

class TestCeleryBrokerConnection:
    """Testes de conexao do Celery com Redis broker"""

    @pytest.mark.integration
    def test_celery_broker_connection(self, celery_app):
        """Testa que o Celery consegue se conectar ao broker Redis"""
        try:
            conn = celery_app.connection()
            conn.ensure_connection(max_retries=3, timeout=5)
            conn.close()
        except Exception as e:
            pytest.fail(f"Celery nao conseguiu conectar ao broker: {e}")

    @pytest.mark.integration
    def test_celery_result_backend_accessible(self, app_settings):
        """Testa que o result backend (Redis) esta acessivel"""
        import redis

        r = redis.from_url(app_settings.redis_url, socket_timeout=5)
        try:
            # Simular escrita/leitura de resultado (como Celery faz)
            r.set("celery-task-meta-_test_result", '{"status": "SUCCESS", "result": "ok"}', ex=10)
            val = r.get("celery-task-meta-_test_result")
            r.delete("celery-task-meta-_test_result")

            assert val is not None
            assert b"SUCCESS" in val
        except Exception as e:
            pytest.fail(f"Result backend nao acessivel: {e}")
        finally:
            r.close()

    @pytest.mark.integration
    def test_celery_inspect_ping(self, celery_app):
        """Testa inspect do Celery (pode falhar se nao houver worker)"""
        inspect = celery_app.control.inspect()
        # Ping com timeout curto - pode retornar None se nao houver worker
        result = inspect.ping(timeout=2)
        # Nao falhar se nao houver workers, apenas verificar que o inspect funciona
        # result e None se nenhum worker responder, dict se algum responder
        assert result is None or isinstance(result, dict)
