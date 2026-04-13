from fastapi import APIRouter

from app.api.v1 import health, settings, candidates, linkedin, auth, documents, search, websocket, chat, vectordb, companies, diagnostics, batch_import

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/v1")
api_router.include_router(settings.router, prefix="/v1")
api_router.include_router(candidates.router, prefix="/v1")
api_router.include_router(documents.router, prefix="/v1")
api_router.include_router(search.router, prefix="/v1")
api_router.include_router(linkedin.router, prefix="/v1")
api_router.include_router(chat.router, prefix="/v1")
api_router.include_router(vectordb.router, prefix="/v1")
api_router.include_router(companies.router, prefix="/v1")
api_router.include_router(diagnostics.router, prefix="/v1")
api_router.include_router(batch_import.router, prefix="/v1")
api_router.include_router(websocket.router, prefix="/v1", tags=["websocket"])
