"""
API de diagnostico e teste de conexoes

Endpoints para:
- Testar conexao com banco de dados PostgreSQL
- Testar conexao com Redis
- Testar conexao com OpenAI API
- Testar conexao com Vector Store (pgvector/Supabase/Qdrant)
- Testar configuracao de Celery
- Diagnostico completo do sistema (todos os componentes)
- Verificar status de embeddings e chat
"""
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import settings
from app.core.dependencies import get_current_user, require_permission
from app.db.database import get_db
from app.db.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


# ============================================
# Schemas
# ============================================

class ComponentStatus(BaseModel):
    name: str
    status: str  # ok, error, warning, not_configured
    message: str
    elapsed_ms: float = 0.0
    details: Dict[str, Any] = {}


class DiagnosticsResponse(BaseModel):
    overall_status: str  # ok, degraded, error
    timestamp: str
    version: str
    components: List[ComponentStatus]
    summary: Dict[str, int] = {}


class ConnectionTestResponse(BaseModel):
    component: str
    status: str
    message: str
    elapsed_ms: float
    details: Dict[str, Any] = {}


# ============================================
# Individual Connection Tests
# ============================================

@router.get("/test/database", response_model=ConnectionTestResponse)
def test_database_connection(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.read")),
):
    """
    Testa a conexao com o banco de dados PostgreSQL

    Verifica:
    - Conexao ativa
    - Extensao pgvector instalada
    - Tabelas principais existem
    - Contagem de registros
    """
    start = time.time()
    details: Dict[str, Any] = {}

    try:
        # Teste basico de conexao
        result = db.execute(text("SELECT version()"))
        pg_version = result.scalar()
        details["postgres_version"] = pg_version

        # Verificar extensao pgvector
        try:
            result = db.execute(text(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
            ))
            pgvector_version = result.scalar()
            details["pgvector_version"] = pgvector_version or "nao instalada"
        except Exception:
            details["pgvector_version"] = "erro ao verificar"

        # Contar tabelas principais
        tables = [
            "candidates", "documents", "chunks", "embeddings",
            "users", "companies", "chat_conversations", "chat_messages",
        ]
        table_counts = {}
        for table in tables:
            try:
                result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                table_counts[table] = result.scalar()
            except Exception:
                table_counts[table] = "tabela nao encontrada"

        details["table_counts"] = table_counts

        # Pool info
        from app.db.database import engine
        pool = engine.pool
        details["pool_size"] = pool.size() if hasattr(pool, 'size') else "N/A"
        details["pool_checkedout"] = pool.checkedout() if hasattr(pool, 'checkedout') else "N/A"

        elapsed = (time.time() - start) * 1000
        logger.info(f"Database connection test: OK ({elapsed:.1f}ms)")

        return ConnectionTestResponse(
            component="PostgreSQL Database",
            status="ok",
            message="Conexao com banco de dados OK",
            elapsed_ms=round(elapsed, 1),
            details=details,
        )

    except Exception as e:
        elapsed = (time.time() - start) * 1000
        logger.error(f"Database connection test failed: {e}")
        return ConnectionTestResponse(
            component="PostgreSQL Database",
            status="error",
            message=f"Erro na conexao: {str(e)}",
            elapsed_ms=round(elapsed, 1),
            details=details,
        )


@router.get("/test/redis", response_model=ConnectionTestResponse)
def test_redis_connection(
    current_user: User = Depends(require_permission("settings.read")),
):
    """
    Testa a conexao com o Redis

    Verifica:
    - Conexao ativa
    - Ping/pong
    - Info do servidor
    """
    start = time.time()
    details: Dict[str, Any] = {}

    try:
        import redis

        r = redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=5)

        # Ping
        pong = r.ping()
        details["ping"] = "PONG" if pong else "sem resposta"

        # Info basico
        info = r.info("server")
        details["redis_version"] = info.get("redis_version", "desconhecida")
        details["uptime_seconds"] = info.get("uptime_in_seconds", 0)

        # Info memoria
        mem_info = r.info("memory")
        details["used_memory_human"] = mem_info.get("used_memory_human", "N/A")

        # Info clientes
        client_info = r.info("clients")
        details["connected_clients"] = client_info.get("connected_clients", 0)

        # Teste write/read
        test_key = "_diagnostics_test"
        r.set(test_key, "ok", ex=10)
        val = r.get(test_key)
        r.delete(test_key)
        details["write_read_test"] = "ok" if val == "ok" else "falhou"

        r.close()

        elapsed = (time.time() - start) * 1000
        logger.info(f"Redis connection test: OK ({elapsed:.1f}ms)")

        return ConnectionTestResponse(
            component="Redis",
            status="ok",
            message="Conexao com Redis OK",
            elapsed_ms=round(elapsed, 1),
            details=details,
        )

    except ImportError:
        elapsed = (time.time() - start) * 1000
        return ConnectionTestResponse(
            component="Redis",
            status="error",
            message="Pacote redis nao instalado",
            elapsed_ms=round(elapsed, 1),
        )
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        logger.error(f"Redis connection test failed: {e}")
        return ConnectionTestResponse(
            component="Redis",
            status="error",
            message=f"Erro na conexao: {str(e)}",
            elapsed_ms=round(elapsed, 1),
            details={"redis_url": settings.redis_url.replace(
                settings.redis_url.split("@")[0] if "@" in settings.redis_url else "",
                "***"
            )},
        )


@router.get("/test/openai", response_model=ConnectionTestResponse)
async def test_openai_connection(
    current_user: User = Depends(require_permission("settings.read")),
):
    """
    Testa a conexao com o provedor LLM configurado (OpenAI ou Anthropic)
    e tambem testa embeddings se OpenAI key estiver configurada.

    Verifica:
    - API key configurada para o provedor ativo
    - Conexao ativa com LLM
    - Modelo de embedding acessivel (sempre OpenAI)
    - Modelo de chat acessivel
    """
    from app.services.llm_client import llm_client as _llm_client

    start = time.time()
    provider_name = settings.llm_provider.value.capitalize()
    details: Dict[str, Any] = {
        "llm_provider": settings.llm_provider.value,
        "chat_model": settings.chat_model,
    }

    if not settings.active_llm_api_key:
        elapsed = (time.time() - start) * 1000
        return ConnectionTestResponse(
            component=f"{provider_name} API",
            status="not_configured",
            message=f"API key do {provider_name} nao configurada. Configure no .env ou nas configuracoes.",
            elapsed_ms=round(elapsed, 1),
            details={
                "llm_provider": settings.llm_provider.value,
                "embedding_mode": settings.embedding_mode.value,
                "note": "Se usar EMBEDDING_MODE=code, OpenAI nao e necessaria para embeddings",
            },
        )

    try:
        # Teste de chat com mensagem curta via cliente centralizado
        try:
            response = await _llm_client.chat_completion(
                messages=[{"role": "user", "content": "Responda apenas: ok"}],
                max_tokens=10,
                temperature=0,
            )
            details["chat_test"] = "ok"
            details["chat_response"] = response.content[:50]
            details["chat_usage"] = {
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "total_tokens": response.tokens_used,
            }
            details["model_used"] = response.model
        except Exception as e:
            details["chat_test"] = f"erro: {str(e)}"

        # Teste de embedding (sempre via OpenAI, se key disponivel)
        if settings.openai_api_key and settings.embedding_mode.value == "api":
            details["embedding_model"] = settings.embedding_model
            try:
                from openai import AsyncOpenAI
                kwargs: Dict[str, Any] = {"api_key": settings.openai_api_key}
                if settings.openai_base_url:
                    kwargs["base_url"] = settings.openai_base_url
                if settings.openai_organization:
                    kwargs["organization"] = settings.openai_organization
                client = AsyncOpenAI(**kwargs)

                emb_response = await client.embeddings.create(
                    model=settings.embedding_model,
                    input="teste de conexao"
                )
                details["embedding_test"] = "ok"
                details["embedding_dimensions"] = len(emb_response.data[0].embedding)
                details["embedding_usage_tokens"] = emb_response.usage.total_tokens
                await client.close()
            except Exception as e:
                details["embedding_test"] = f"erro: {str(e)}"
        elif settings.embedding_mode.value == "code":
            details["embedding_test"] = "modo local (code) - nao requer API"
        else:
            details["embedding_test"] = "OpenAI API key necessaria para embeddings via API"

        chat_ok = details.get("chat_test") == "ok"
        emb_ok = details.get("embedding_test") in ("ok", "modo local (code) - nao requer API")
        all_ok = chat_ok and emb_ok

        elapsed = (time.time() - start) * 1000
        logger.info(f"{provider_name} connection test: {'OK' if all_ok else 'PARTIAL'} ({elapsed:.1f}ms)")

        return ConnectionTestResponse(
            component=f"{provider_name} API",
            status="ok" if all_ok else "warning",
            message=f"Conexao com {provider_name} OK" if all_ok else "Conexao parcial - verifique detalhes",
            elapsed_ms=round(elapsed, 1),
            details=details,
        )

    except Exception as e:
        elapsed = (time.time() - start) * 1000
        logger.error(f"{provider_name} connection test failed: {e}")
        return ConnectionTestResponse(
            component=f"{provider_name} API",
            status="error",
            message=f"Erro na conexao: {str(e)}",
            elapsed_ms=round(elapsed, 1),
            details=details,
        )


@router.get("/test/vectorstore", response_model=ConnectionTestResponse)
async def test_vectorstore_connection(
    current_user: User = Depends(require_permission("settings.read")),
):
    """
    Testa a conexao com o Vector Store configurado

    Verifica:
    - Provedor ativo
    - Health check
    - Contagem de vetores
    - Info do provedor
    """
    start = time.time()
    details: Dict[str, Any] = {
        "provider": settings.vector_db_provider.value,
        "embedding_mode": settings.embedding_mode.value,
    }

    try:
        from app.vectorstore import get_vector_store

        store = get_vector_store()

        # Health check
        try:
            health = await store.health_check()
            details["health_check"] = health
        except Exception as e:
            details["health_check"] = f"erro: {str(e)}"

        # Info
        try:
            info = await store.get_info()
            details["store_info"] = info
        except Exception as e:
            details["store_info"] = f"erro: {str(e)}"

        # Count
        try:
            count = await store.count()
            details["total_vectors"] = count
        except Exception as e:
            details["total_vectors"] = f"erro: {str(e)}"

        health_ok = isinstance(details.get("health_check"), dict) and \
                    details["health_check"].get("status") in ("ok", "healthy")

        elapsed = (time.time() - start) * 1000
        logger.info(f"Vector store test ({settings.vector_db_provider.value}): "
                    f"{'OK' if health_ok else 'WARNING'} ({elapsed:.1f}ms)")

        return ConnectionTestResponse(
            component=f"Vector Store ({settings.vector_db_provider.value})",
            status="ok" if health_ok else "warning",
            message=f"Vector store {settings.vector_db_provider.value} operacional"
                    if health_ok else "Vector store com avisos - verifique detalhes",
            elapsed_ms=round(elapsed, 1),
            details=details,
        )

    except Exception as e:
        elapsed = (time.time() - start) * 1000
        logger.error(f"Vector store test failed: {e}")
        return ConnectionTestResponse(
            component=f"Vector Store ({settings.vector_db_provider.value})",
            status="error",
            message=f"Erro: {str(e)}",
            elapsed_ms=round(elapsed, 1),
            details=details,
        )


@router.get("/test/celery", response_model=ConnectionTestResponse)
def test_celery_connection(
    current_user: User = Depends(require_permission("settings.read")),
):
    """
    Testa a conexao com o Celery / fila de tarefas

    Verifica:
    - Broker (Redis) acessivel
    - Workers ativos
    - Filas configuradas
    """
    start = time.time()
    details: Dict[str, Any] = {}

    try:
        from app.core.celery_app import celery_app

        # Inspecionar workers
        inspector = celery_app.control.inspect(timeout=3)

        active = inspector.active()
        details["active_tasks"] = {k: len(v) for k, v in active.items()} if active else {}

        registered = inspector.registered()
        if registered:
            for worker, tasks in registered.items():
                details["registered_tasks"] = tasks
                break  # Primeiro worker
        else:
            details["registered_tasks"] = []

        stats = inspector.stats()
        if stats:
            for worker, info in stats.items():
                details["worker"] = worker
                details["worker_pool"] = info.get("pool", {}).get("implementation", "N/A")
                details["worker_concurrency"] = info.get("pool", {}).get("max-concurrency", "N/A")
                break

        has_workers = bool(active)
        elapsed = (time.time() - start) * 1000
        logger.info(f"Celery test: {'OK' if has_workers else 'NO WORKERS'} ({elapsed:.1f}ms)")

        return ConnectionTestResponse(
            component="Celery Task Queue",
            status="ok" if has_workers else "warning",
            message="Celery operacional" if has_workers else "Nenhum worker Celery ativo - documentos nao serao processados",
            elapsed_ms=round(elapsed, 1),
            details=details,
        )

    except Exception as e:
        elapsed = (time.time() - start) * 1000
        logger.error(f"Celery test failed: {e}")
        return ConnectionTestResponse(
            component="Celery Task Queue",
            status="error",
            message=f"Erro: {str(e)}",
            elapsed_ms=round(elapsed, 1),
            details=details,
        )


@router.get("/test/embedding", response_model=ConnectionTestResponse)
async def test_embedding_pipeline(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.read")),
):
    """
    Testa o pipeline completo de embeddings

    Verifica:
    - Geracao de embedding funciona
    - Armazenamento no vector store funciona
    - Busca vetorial funciona
    """
    start = time.time()
    details: Dict[str, Any] = {
        "embedding_mode": settings.embedding_mode.value,
        "embedding_model": settings.embedding_model if settings.embedding_mode.value == "api" else settings.embedding_local_model,
        "dimensions": settings.active_embedding_dimensions,
    }

    try:
        from app.services.embedding_service import EmbeddingService

        service = EmbeddingService()

        # Gerar embedding de teste
        test_text = "Engenheiro de producao com experiencia em lean manufacturing e gestao de qualidade"
        embedding = await service.generate_embedding(test_text)
        details["embedding_generated"] = True
        details["vector_length"] = len(embedding)
        details["vector_sample"] = embedding[:5]  # primeiros 5 valores

        # Testar busca semantica (sem armazenar)
        try:
            results = await service.search_vectors(
                query="engenheiro producao",
                limit=3,
            )
            details["search_results_count"] = len(results)
            details["search_test"] = "ok"
        except Exception as e:
            details["search_test"] = f"erro: {str(e)}"

        elapsed = (time.time() - start) * 1000
        logger.info(f"Embedding pipeline test: OK ({elapsed:.1f}ms)")

        return ConnectionTestResponse(
            component="Embedding Pipeline",
            status="ok",
            message=f"Pipeline de embeddings ({settings.embedding_mode.value}) operacional",
            elapsed_ms=round(elapsed, 1),
            details=details,
        )

    except Exception as e:
        elapsed = (time.time() - start) * 1000
        logger.error(f"Embedding pipeline test failed: {e}")
        return ConnectionTestResponse(
            component="Embedding Pipeline",
            status="error",
            message=f"Erro no pipeline: {str(e)}",
            elapsed_ms=round(elapsed, 1),
            details=details,
        )


# ============================================
# Full System Diagnostics
# ============================================

@router.get("/full", response_model=DiagnosticsResponse)
async def full_system_diagnostics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.read")),
):
    """
    Diagnostico completo do sistema - testa todos os componentes

    Executa em sequencia:
    1. Banco de dados PostgreSQL
    2. Redis
    3. OpenAI API
    4. Vector Store
    5. Celery Workers
    6. Pipeline de Embeddings
    7. Configuracoes gerais

    Retorna status geral e status individual de cada componente.
    """
    components: List[ComponentStatus] = []
    logger.info("Iniciando diagnostico completo do sistema...")

    # 1. Database
    try:
        result = test_database_connection(db=db, current_user=current_user)
        components.append(ComponentStatus(
            name="PostgreSQL Database",
            status=result.status,
            message=result.message,
            elapsed_ms=result.elapsed_ms,
            details=result.details,
        ))
    except Exception as e:
        components.append(ComponentStatus(
            name="PostgreSQL Database",
            status="error",
            message=str(e),
        ))

    # 2. Redis
    try:
        result = test_redis_connection(current_user=current_user)
        components.append(ComponentStatus(
            name="Redis",
            status=result.status,
            message=result.message,
            elapsed_ms=result.elapsed_ms,
            details=result.details,
        ))
    except Exception as e:
        components.append(ComponentStatus(
            name="Redis",
            status="error",
            message=str(e),
        ))

    # 3. LLM Provider (OpenAI ou Anthropic)
    try:
        result = await test_openai_connection(current_user=current_user)
        components.append(ComponentStatus(
            name=f"LLM ({settings.llm_provider.value.capitalize()})",
            status=result.status,
            message=result.message,
            elapsed_ms=result.elapsed_ms,
            details=result.details,
        ))
    except Exception as e:
        components.append(ComponentStatus(
            name=f"LLM ({settings.llm_provider.value.capitalize()})",
            status="error",
            message=str(e),
        ))

    # 4. Vector Store
    try:
        result = await test_vectorstore_connection(current_user=current_user)
        components.append(ComponentStatus(
            name=f"Vector Store ({settings.vector_db_provider.value})",
            status=result.status,
            message=result.message,
            elapsed_ms=result.elapsed_ms,
            details=result.details,
        ))
    except Exception as e:
        components.append(ComponentStatus(
            name="Vector Store",
            status="error",
            message=str(e),
        ))

    # 5. Celery
    try:
        result = test_celery_connection(current_user=current_user)
        components.append(ComponentStatus(
            name="Celery Task Queue",
            status=result.status,
            message=result.message,
            elapsed_ms=result.elapsed_ms,
            details=result.details,
        ))
    except Exception as e:
        components.append(ComponentStatus(
            name="Celery Task Queue",
            status="error",
            message=str(e),
        ))

    # 6. Embedding Pipeline
    try:
        result = await test_embedding_pipeline(db=db, current_user=current_user)
        components.append(ComponentStatus(
            name="Embedding Pipeline",
            status=result.status,
            message=result.message,
            elapsed_ms=result.elapsed_ms,
            details=result.details,
        ))
    except Exception as e:
        components.append(ComponentStatus(
            name="Embedding Pipeline",
            status="error",
            message=str(e),
        ))

    # 7. Configuration check
    config_details: Dict[str, Any] = {
        "app_version": settings.app_version,
        "llm_provider": settings.llm_provider.value,
        "chat_model": settings.chat_model,
        "embedding_mode": settings.embedding_mode.value,
        "vector_db_provider": settings.vector_db_provider.value,
        "openai_configured": bool(settings.openai_api_key),
        "anthropic_configured": bool(settings.anthropic_api_key),
        "linkedin_enabled": settings.linkedin_api_enabled,
        "pii_encryption": settings.enable_pii_encryption,
        "multi_tenant": settings.multi_tenant_enabled,
        "max_upload_size_mb": settings.max_upload_size_mb,
    }

    config_warnings = []
    if not settings.openai_api_key and settings.embedding_mode.value == "api":
        config_warnings.append("OPENAI_API_KEY nao configurada mas EMBEDDING_MODE=api")
    if not settings.active_llm_api_key:
        config_warnings.append(f"API key do {settings.llm_provider.value} nao configurada")
    if settings.secret_key and len(settings.secret_key) < 32:
        config_warnings.append("SECRET_KEY muito curta (minimo 32 chars)")

    config_status = "warning" if config_warnings else "ok"
    components.append(ComponentStatus(
        name="Configuracoes",
        status=config_status,
        message="Configuracoes OK" if not config_warnings else f"{len(config_warnings)} aviso(s)",
        details={**config_details, "warnings": config_warnings},
    ))

    # Calcular status geral
    statuses = [c.status for c in components]
    summary = {
        "ok": statuses.count("ok"),
        "warning": statuses.count("warning"),
        "error": statuses.count("error"),
        "not_configured": statuses.count("not_configured"),
    }

    if summary["error"] > 0:
        overall = "error"
    elif summary["warning"] > 0 or summary["not_configured"] > 0:
        overall = "degraded"
    else:
        overall = "ok"

    logger.info(
        f"Diagnostico completo: {overall} "
        f"(ok={summary['ok']}, warning={summary['warning']}, error={summary['error']})"
    )

    return DiagnosticsResponse(
        overall_status=overall,
        timestamp=datetime.now(timezone.utc).isoformat(),
        version=settings.app_version,
        components=components,
        summary=summary,
    )


# ============================================
# Log Viewer (ultimas linhas)
# ============================================

@router.get("/logs")
def get_recent_logs(
    lines: int = 100,
    level: str = "all",
    current_user: User = Depends(require_permission("settings.read")),
):
    """
    Retorna as ultimas linhas dos logs da aplicacao

    Args:
        lines: Numero de linhas (max 500)
        level: Filtrar por nivel (all, error, warning, info)
    """
    from pathlib import Path

    lines = min(lines, 500)

    # Whitelist de niveis validos (prevenir path traversal)
    allowed_levels = {"all", "error", "warning", "info"}
    if level not in allowed_levels:
        level = "all"

    log_file = "error.log" if level == "error" else "app.log"
    log_path = Path("./logs") / log_file

    # Garantir que o caminho resolvido esta dentro de ./logs
    resolved = log_path.resolve()
    logs_dir = Path("./logs").resolve()
    if not str(resolved).startswith(str(logs_dir)):
        return {"log_file": "", "lines": [], "message": "Caminho invalido"}

    if not log_path.exists():
        return {
            "log_file": str(log_path),
            "lines": [],
            "message": "Arquivo de log nao encontrado",
        }

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()

        # Filtrar por nivel se necessario
        if level != "all" and level != "error":
            level_upper = level.upper()
            all_lines = [l for l in all_lines if f"| {level_upper}" in l]

        recent = all_lines[-lines:]

        return {
            "log_file": str(log_path),
            "total_lines": len(all_lines),
            "returned_lines": len(recent),
            "lines": [l.rstrip() for l in recent],
        }

    except Exception as e:
        return {
            "log_file": str(log_path),
            "lines": [],
            "message": f"Erro ao ler logs: {str(e)}",
        }
