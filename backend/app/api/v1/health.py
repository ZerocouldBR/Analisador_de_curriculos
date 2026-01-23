from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/health")
async def healthcheck() -> dict:
    return {
        "status": "ok",
        "service": "analisador-curriculos-api",
        "version": settings.app_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
