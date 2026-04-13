"""
API de Diagnostico e Teste de Conexoes

Endpoints para:
- Testar conexao com cada API/servico individualmente
- Diagnostico completo end-to-end do sistema
- Validacao passo a passo de todo o pipeline
- Logs de problemas encontrados
"""
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text

from app.db.database import get_db
from app.core.config import settings, VectorDBProvider, EmbeddingMode
from app.core.dependencies import require_permission
from app.db.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


# ============================================
# Schemas
# ============================================

class ServiceTestResult(BaseModel):
    service: str
    status: str  # ok, error, warning, skipped
    message: str
    duration_ms: float = 0
    details: Dict[str, Any] = {}


class DiagnosticsResponse(BaseModel):
    overall_status: str  # healthy, degraded, unhealthy
    timestamp: str
    app_version: str
    tests: List[ServiceTestResult]
    summary: Dict[str, int]
    recommendations: List[str] = []


# ============================================
# Helper: run a test with timing
# ============================================

async def _run_test(name: str, test_fn) -> ServiceTestResult:
    start = time.monotonic()
    try:
        result = await test_fn()
        elapsed = (time.monotonic() - start) * 1000
        return ServiceTestResult(
            service=name,
            status=result.get("status", "ok"),
            message=result.get("message", "OK"),
            duration_ms=round(elapsed, 1),
            details=result.get("details", {}),
        )
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        logger.error(f"Diagnostico [{name}] falhou: {e}", exc_info=True)
        return ServiceTestResult(
            service=name,
            status="error",
            message=str(e),
            duration_ms=round(elapsed, 1),
            details={"error_type": type(e).__name__},
        )


# ============================================
# Individual Test Functions
# ============================================

async def _test_database(db: Session) -> Dict[str, Any]:
    """Testa conexao com PostgreSQL"""
    result = db.execute(sql_text("SELECT version(), current_database(), pg_size_pretty(pg_database_size(current_database()))"))
    row = result.fetchone()

    # Contar tabelas principais
    tables_result = db.execute(sql_text(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
    ))
    table_count = tables_result.scalar()

    # Contar registros chave
    counts = {}
    for table in ["candidates", "documents", "chunks", "embeddings", "users"]:
        try:
            r = db.execute(sql_text(f"SELECT COUNT(*) FROM {table}"))
            counts[table] = r.scalar()
        except Exception:
            counts[table] = -1

    return {
        "status": "ok",
        "message": f"PostgreSQL conectado: {row[1]}",
        "details": {
            "version": row[0][:60],
            "database": row[1],
            "size": row[2],
            "tables": table_count,
            "record_counts": counts,
        },
    }


async def _test_pgvector(db: Session) -> Dict[str, Any]:
    """Testa extensao pgvector"""
    result = db.execute(sql_text(
        "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
    ))
    row = result.fetchone()

    if not row:
        return {
            "status": "error",
            "message": "Extensao pgvector NAO instalada. Execute: CREATE EXTENSION vector;",
            "details": {"installed": False},
        }

    # Verificar indice HNSW
    idx_result = db.execute(sql_text(
        "SELECT indexname FROM pg_indexes WHERE indexname = 'idx_embeddings_vector_hnsw'"
    ))
    has_hnsw = idx_result.fetchone() is not None

    # Contar embeddings
    emb_result = db.execute(sql_text("SELECT COUNT(*) FROM embeddings"))
    emb_count = emb_result.scalar()

    return {
        "status": "ok",
        "message": f"pgvector v{row[0]} instalado, {emb_count} embeddings, HNSW={'sim' if has_hnsw else 'nao'}",
        "details": {
            "version": row[0],
            "embeddings_count": emb_count,
            "hnsw_index": has_hnsw,
            "distance_metric": settings.pgvector_distance_metric,
            "dimensions": settings.active_embedding_dimensions,
        },
    }


async def _test_redis() -> Dict[str, Any]:
    """Testa conexao com Redis"""
    import redis
    r = redis.from_url(settings.redis_url, socket_timeout=5)
    info = r.info("server")
    memory = r.info("memory")
    r.close()

    return {
        "status": "ok",
        "message": f"Redis v{info['redis_version']} conectado",
        "details": {
            "version": info["redis_version"],
            "uptime_days": info.get("uptime_in_days", 0),
            "used_memory": memory.get("used_memory_human", "N/A"),
            "connected_clients": info.get("connected_clients", 0),
        },
    }


async def _test_celery() -> Dict[str, Any]:
    """Testa conexao com Celery workers"""
    try:
        from app.core.celery_app import celery_app
        inspector = celery_app.control.inspect(timeout=3)
        active = inspector.active()

        if active is None:
            return {
                "status": "warning",
                "message": "Nenhum worker Celery respondeu. Verifique se o worker esta rodando.",
                "details": {"workers_found": 0},
            }

        worker_names = list(active.keys())
        total_tasks = sum(len(tasks) for tasks in active.values())

        return {
            "status": "ok",
            "message": f"{len(worker_names)} worker(s) ativo(s), {total_tasks} task(s) em execucao",
            "details": {
                "workers": worker_names,
                "active_tasks": total_tasks,
            },
        }
    except Exception as e:
        return {
            "status": "warning",
            "message": f"Celery nao acessivel: {e}. Uploads podem nao ser processados.",
            "details": {"error": str(e)},
        }


async def _test_openai() -> Dict[str, Any]:
    """Testa conexao com API OpenAI"""
    if not settings.openai_api_key:
        return {
            "status": "error",
            "message": "OPENAI_API_KEY nao configurada. Defina no .env",
            "details": {"configured": False},
        }

    from openai import AsyncOpenAI

    kwargs = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    if settings.openai_organization:
        kwargs["organization"] = settings.openai_organization

    client = AsyncOpenAI(**kwargs)

    # Testar geracao de embedding
    response = await client.embeddings.create(
        model=settings.embedding_model,
        input="teste de conexao"
    )
    dim = len(response.data[0].embedding)

    # Testar chat model listando modelos
    models = await client.models.list()
    model_ids = [m.id for m in models.data[:10]]

    chat_model_available = settings.chat_model in [m.id for m in models.data]

    return {
        "status": "ok" if chat_model_available else "warning",
        "message": f"OpenAI conectada. Embedding: {settings.embedding_model} ({dim}d). Chat: {settings.chat_model} ({'disponivel' if chat_model_available else 'NAO encontrado'})",
        "details": {
            "embedding_model": settings.embedding_model,
            "embedding_dimensions": dim,
            "chat_model": settings.chat_model,
            "chat_model_available": chat_model_available,
            "base_url": settings.openai_base_url or "api.openai.com",
            "some_models": model_ids,
        },
    }


async def _test_openai_chat() -> Dict[str, Any]:
    """Testa chat completion da OpenAI"""
    if not settings.openai_api_key:
        return {
            "status": "skipped",
            "message": "Pulado - OPENAI_API_KEY nao configurada",
        }

    from openai import AsyncOpenAI

    kwargs = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url

    client = AsyncOpenAI(**kwargs)

    response = await client.chat.completions.create(
        model=settings.chat_model,
        messages=[{"role": "user", "content": "Responda apenas: OK"}],
        max_tokens=10,
        temperature=0,
    )

    content = response.choices[0].message.content
    tokens = response.usage.total_tokens if response.usage else 0

    return {
        "status": "ok",
        "message": f"Chat LLM respondeu com sucesso ({tokens} tokens)",
        "details": {
            "model": settings.chat_model,
            "response": content,
            "tokens_used": tokens,
        },
    }


async def _test_vector_store() -> Dict[str, Any]:
    """Testa o vector store configurado"""
    from app.vectorstore import get_vector_store

    store = get_vector_store()
    health = await store.health_check()

    if health.get("status") == "healthy":
        return {
            "status": "ok",
            "message": f"Vector store ({settings.vector_db_provider.value}) saudavel",
            "details": health,
        }

    return {
        "status": "error",
        "message": f"Vector store com problemas: {health.get('error', 'desconhecido')}",
        "details": health,
    }


async def _test_embedding_pipeline(db: Session) -> Dict[str, Any]:
    """Testa pipeline completo: texto -> embedding -> busca vetorial"""
    if not settings.openai_api_key and settings.embedding_mode == EmbeddingMode.API:
        return {
            "status": "skipped",
            "message": "Pulado - modo API sem OPENAI_API_KEY",
        }

    from app.services.embedding_service import embedding_service

    # Gerar embedding de teste
    test_text = "Profissional com experiencia em producao industrial e logistica"
    vector = await embedding_service.generate_embedding(test_text)

    if not vector or len(vector) == 0:
        return {
            "status": "error",
            "message": "Embedding gerado vazio",
        }

    # Testar busca
    results = await embedding_service.search_vectors(
        query=test_text, limit=3, threshold=0.0
    )

    return {
        "status": "ok",
        "message": f"Pipeline OK: embedding ({len(vector)}d) gerado, busca retornou {len(results)} resultados",
        "details": {
            "embedding_dimensions": len(vector),
            "mode": settings.embedding_mode.value,
            "model": embedding_service.active_model_name,
            "search_results": len(results),
            "top_score": round(results[0]["score"], 3) if results else 0,
        },
    }


async def _test_storage() -> Dict[str, Any]:
    """Testa acesso ao storage de documentos"""
    import os
    from app.services.storage_service import storage_service

    base = storage_service.base_path
    exists = base.exists()
    writable = os.access(str(base), os.W_OK) if exists else False

    docs_dir = base / "documents"
    doc_count = 0
    if docs_dir.exists():
        doc_count = sum(1 for _ in docs_dir.rglob("*") if _.is_file())

    return {
        "status": "ok" if (exists and writable) else "error",
        "message": f"Storage {'acessivel' if writable else 'NAO acessivel'}: {base} ({doc_count} arquivos)",
        "details": {
            "path": str(base),
            "exists": exists,
            "writable": writable,
            "files_count": doc_count,
        },
    }


async def _test_linkedin() -> Dict[str, Any]:
    """Testa configuracao do LinkedIn"""
    if not settings.linkedin_api_enabled:
        return {
            "status": "warning",
            "message": "LinkedIn API desabilitada (LINKEDIN_API_ENABLED=false)",
            "details": {
                "enabled": False,
                "client_id_set": bool(settings.linkedin_client_id),
                "client_secret_set": bool(settings.linkedin_client_secret),
                "redirect_uri": settings.linkedin_redirect_uri or "nao configurado",
            },
        }

    configured = bool(settings.linkedin_client_id and settings.linkedin_client_secret)

    return {
        "status": "ok" if configured else "warning",
        "message": f"LinkedIn API habilitada, credenciais {'configuradas' if configured else 'FALTANDO'}",
        "details": {
            "enabled": True,
            "client_id_set": bool(settings.linkedin_client_id),
            "client_secret_set": bool(settings.linkedin_client_secret),
            "redirect_uri": settings.linkedin_redirect_uri or "nao configurado",
        },
    }


# ============================================
# Endpoints
# ============================================

@router.get("/full", response_model=DiagnosticsResponse)
async def run_full_diagnostics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.read")),
):
    """
    Executa diagnostico completo do sistema

    Testa todos os servicos e conexoes:
    1. PostgreSQL (banco relacional)
    2. pgvector (extensao vetorial)
    3. Redis (cache/filas)
    4. Celery (workers)
    5. OpenAI API (embeddings)
    6. OpenAI Chat (LLM)
    7. Vector Store (busca)
    8. Pipeline de Embedding (end-to-end)
    9. Storage (arquivos)
    10. LinkedIn (integracao)

    **Requer permissao:** settings.read
    """
    logger.info("Iniciando diagnostico completo", extra={"operation": "full_diagnostics", "user_id": current_user.id})

    tests: List[ServiceTestResult] = []

    # 1. Database
    tests.append(await _run_test("PostgreSQL", lambda: _test_database(db)))

    # 2. pgvector
    tests.append(await _run_test("pgvector", lambda: _test_pgvector(db)))

    # 3. Redis
    tests.append(await _run_test("Redis", lambda: _test_redis()))

    # 4. Celery
    tests.append(await _run_test("Celery Workers", lambda: _test_celery()))

    # 5. OpenAI Embeddings
    tests.append(await _run_test("OpenAI API (Embeddings)", lambda: _test_openai()))

    # 6. OpenAI Chat
    tests.append(await _run_test("OpenAI Chat (LLM)", lambda: _test_openai_chat()))

    # 7. Vector Store
    tests.append(await _run_test("Vector Store", lambda: _test_vector_store()))

    # 8. Embedding Pipeline
    tests.append(await _run_test("Pipeline Embedding (E2E)", lambda: _test_embedding_pipeline(db)))

    # 9. Storage
    tests.append(await _run_test("Storage (Arquivos)", lambda: _test_storage()))

    # 10. LinkedIn
    tests.append(await _run_test("LinkedIn API", lambda: _test_linkedin()))

    # Summary
    status_counts = {"ok": 0, "warning": 0, "error": 0, "skipped": 0}
    for t in tests:
        status_counts[t.status] = status_counts.get(t.status, 0) + 1

    if status_counts["error"] > 0:
        overall = "unhealthy"
    elif status_counts["warning"] > 0:
        overall = "degraded"
    else:
        overall = "healthy"

    # Recommendations
    recommendations = []
    for t in tests:
        if t.status == "error":
            if "openai" in t.service.lower():
                recommendations.append(f"CRITICO: Configure OPENAI_API_KEY no .env para habilitar embeddings e chat")
            elif "postgres" in t.service.lower():
                recommendations.append(f"CRITICO: Verifique DATABASE_URL no .env e se o PostgreSQL esta rodando")
            elif "pgvector" in t.service.lower():
                recommendations.append(f"CRITICO: Instale pgvector: CREATE EXTENSION IF NOT EXISTS vector;")
            elif "redis" in t.service.lower():
                recommendations.append(f"CRITICO: Verifique REDIS_URL e se o Redis esta rodando")
            elif "storage" in t.service.lower():
                recommendations.append(f"CRITICO: Diretorio de storage nao acessivel. Verifique permissoes.")
            else:
                recommendations.append(f"Corrigir: {t.service} - {t.message}")
        elif t.status == "warning":
            if "celery" in t.service.lower():
                recommendations.append(f"AVISO: Inicie o worker Celery para processamento async de curriculos")
            elif "linkedin" in t.service.lower():
                recommendations.append(f"AVISO: Configure LinkedIn API para enriquecimento de perfis")
            else:
                recommendations.append(f"Verificar: {t.service} - {t.message}")

    logger.info(
        f"Diagnostico concluido: {overall} ({status_counts})",
        extra={"operation": "full_diagnostics", "status": overall}
    )

    return DiagnosticsResponse(
        overall_status=overall,
        timestamp=datetime.now(timezone.utc).isoformat(),
        app_version=settings.app_version,
        tests=tests,
        summary=status_counts,
        recommendations=recommendations,
    )


@router.get("/test/{service_name}")
async def test_single_service(
    service_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.read")),
):
    """
    Testa um servico individual

    Servicos disponiveis:
    - database, pgvector, redis, celery
    - openai, openai_chat
    - vector_store, embedding_pipeline
    - storage, linkedin

    **Requer permissao:** settings.read
    """
    test_map = {
        "database": lambda: _test_database(db),
        "pgvector": lambda: _test_pgvector(db),
        "redis": _test_redis,
        "celery": _test_celery,
        "openai": _test_openai,
        "openai_chat": _test_openai_chat,
        "vector_store": _test_vector_store,
        "embedding_pipeline": lambda: _test_embedding_pipeline(db),
        "storage": _test_storage,
        "linkedin": _test_linkedin,
    }

    if service_name not in test_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Servico '{service_name}' nao encontrado. Disponiveis: {', '.join(test_map.keys())}",
        )

    result = await _run_test(service_name, test_map[service_name])
    return result


@router.get("/config-summary")
async def get_config_summary(
    current_user: User = Depends(require_permission("settings.read")),
):
    """
    Retorna resumo da configuracao atual do sistema (sem expor secrets)

    **Requer permissao:** settings.read
    """
    return {
        "app": {
            "version": settings.app_version,
            "debug": settings.debug,
            "log_level": settings.log_level,
        },
        "database": {
            "host": settings.database_url.split("@")[-1].split("/")[0] if "@" in settings.database_url else "configured",
            "database": settings.database_url.split("/")[-1].split("?")[0] if "/" in settings.database_url else "configured",
            "pool_size": settings.database_pool_size,
        },
        "vector_db": {
            "provider": settings.vector_db_provider.value,
            "distance_metric": settings.pgvector_distance_metric,
            "hnsw_enabled": settings.enable_hnsw_index,
        },
        "embeddings": {
            "mode": settings.embedding_mode.value,
            "model": settings.embedding_model if settings.embedding_mode == EmbeddingMode.API else settings.embedding_local_model,
            "dimensions": settings.active_embedding_dimensions,
            "batch_size": settings.embedding_batch_size,
        },
        "openai": {
            "api_key_configured": bool(settings.openai_api_key),
            "base_url": settings.openai_base_url or "default (api.openai.com)",
            "chat_model": settings.chat_model,
            "embedding_model": settings.embedding_model,
        },
        "redis": {
            "url": settings.redis_url.split("@")[-1] if "@" in settings.redis_url else settings.redis_url,
        },
        "linkedin": {
            "enabled": settings.linkedin_api_enabled,
            "client_id_configured": bool(settings.linkedin_client_id),
            "client_secret_configured": bool(settings.linkedin_client_secret),
        },
        "storage": {
            "backend": settings.storage_backend,
            "path": settings.storage_path,
            "max_upload_mb": settings.max_upload_size_mb,
        },
        "search": {
            "threshold": settings.vector_search_threshold,
            "limit": settings.vector_search_limit,
            "hybrid_weights": {
                "vector": settings.hybrid_vector_weight,
                "text": settings.hybrid_text_weight,
                "filter": settings.hybrid_filter_weight,
                "domain": settings.hybrid_domain_weight,
            },
        },
        "chat": {
            "model": settings.chat_model,
            "temperature": settings.chat_temperature,
            "max_tokens": settings.chat_max_tokens,
            "max_context_messages": settings.chat_max_context_messages,
        },
    }
