from fastapi import APIRouter

from app.api.v1 import health, settings, candidates, linkedin, auth, documents, search, websocket

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/v1")
api_router.include_router(settings.router, prefix="/v1")
api_router.include_router(candidates.router, prefix="/v1")
api_router.include_router(documents.router, prefix="/v1")
api_router.include_router(search.router, prefix="/v1")
api_router.include_router(linkedin.router, prefix="/v1")
api_router.include_router(websocket.router, prefix="/v1", tags=["websocket"])
