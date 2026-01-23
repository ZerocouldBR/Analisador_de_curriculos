from fastapi import FastAPI

from app.api.routes import api_router
from app.core.config import settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging(settings.log_level)
    application = FastAPI(
        title="Analisador de Currículos",
        version=settings.app_version,
        description="API do sistema de RH on-premises para ingestão e busca de currículos.",
    )
    application.include_router(api_router, prefix="/api")
    return application


app = create_app()
