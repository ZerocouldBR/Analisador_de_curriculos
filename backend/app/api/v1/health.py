import logging
from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def healthcheck() -> dict:
    """
    Health check basico (sem autenticacao)

    Para diagnostico completo, use GET /api/v1/diagnostics/full (autenticado)
    """
    health: dict = {
        "status": "ok",
        "service": "analisador-curriculos-api",
        "version": settings.app_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Quick DB check
    try:
        from app.db.database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        health["database"] = "connected"
    except Exception as e:
        health["database"] = "error"
        health["database_error"] = str(e)
        health["status"] = "degraded"
        logger.error(f"Health check: database error: {e}")

    # Quick Redis check
    try:
        import redis
        r = redis.from_url(settings.redis_url, socket_timeout=2)
        r.ping()
        r.close()
        health["redis"] = "connected"
    except Exception as e:
        health["redis"] = "error"
        health["redis_error"] = str(e)
        health["status"] = "degraded"
        logger.error(f"Health check: redis error: {e}")

    # Config summary
    health["config"] = {
        "embedding_mode": settings.embedding_mode.value,
        "vector_db_provider": settings.vector_db_provider.value,
        "openai_configured": bool(settings.openai_api_key),
        "linkedin_enabled": settings.linkedin_api_enabled,
    }

    return health
