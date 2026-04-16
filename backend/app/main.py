import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from contextlib import asynccontextmanager
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.routes import api_router
from app.core.config import settings
from app.core.logging import configure_logging, RequestLoggingMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação
    """
    logger.info("=" * 60)
    logger.info(f"Iniciando {settings.app_name} v{settings.app_version}")
    logger.info("=" * 60)

    # Startup: Inicializar banco de dados
    try:
        from app.db.init_db import init_db
        init_db()
        logger.info("Banco de dados inicializado com sucesso")
    except Exception as e:
        logger.error(f"Erro ao inicializar banco de dados: {e}", exc_info=True)
        logger.warning("Execute manualmente: python -m app.db.init_db")

    # Startup: Carregar overrides de configuracao do banco de dados
    try:
        from app.db.database import SessionLocal
        from app.services.settings_service import SettingsService
        db_session = SessionLocal()
        try:
            overrides = SettingsService.get_system_config_overrides(db_session)
            if overrides:
                applied = []
                for key, value in overrides.items():
                    if hasattr(settings, key):
                        current_val = getattr(settings, key)
                        if hasattr(current_val, 'value') and isinstance(value, str):
                            enum_class = type(current_val)
                            try:
                                value = enum_class(value)
                            except ValueError:
                                pass
                        object.__setattr__(settings, key, value)
                        applied.append(key)
                if applied:
                    logger.info(f"Overrides de configuracao carregados do DB: {len(applied)} campos")
        finally:
            db_session.close()
    except Exception as e:
        logger.warning(f"Nao foi possivel carregar overrides de configuracao: {e}")

    # Startup: Inicializar vector store
    try:
        from app.vectorstore.factory import initialize_vector_store
        await initialize_vector_store()
        logger.info(f"Vector store inicializado: {settings.vector_db_provider.value}")
    except Exception as e:
        logger.error(f"Erro ao inicializar vector store: {e}", exc_info=True)
        logger.warning("O vector store sera inicializado sob demanda na primeira requisicao")

    # Log configuracao ativa
    logger.info(f"Embedding mode: {settings.embedding_mode.value}")
    logger.info(f"Vector DB provider: {settings.vector_db_provider.value}")
    logger.info(f"LLM Provider: {settings.llm_provider.value} | API key: {'configurada' if settings.active_llm_api_key else 'NAO CONFIGURADA'}")
    logger.info(f"LinkedIn API: {'habilitada' if settings.linkedin_api_enabled else 'desabilitada'}")
    logger.info(f"CORS origins: {settings.cors_origins}")

    yield

    # Shutdown
    logger.info("Aplicacao encerrada")


def create_app() -> FastAPI:
    configure_logging(settings.log_level)

    description = """
    ## Sistema de Análise de Currículos - API

    Sistema completo para RH on-premises com análise inteligente de currículos.

    ### Funcionalidades Principais:

    #### 🎯 Configuração de Prompts do Chat LLM
    - Personalize os prompts do assistente de RH
    - Configure temperatura e parâmetros do modelo
    - Restaure configurações padrão

    #### 📄 Gerenciamento de Currículos
    - Upload e análise de currículos (PDF, DOCX)
    - Extração estruturada de informações
    - Busca semântica com embeddings
    - **Remoção completa** de candidatos e currículos (LGPD-compliant)

    #### 💼 Análise de LinkedIn
    - Enriquecimento de perfis com dados do LinkedIn
    - Extração de skills, experiências e formação
    - Sincronização automática de informações

    #### 🔒 Segurança e Conformidade
    - Auditoria completa de todas as operações
    - Conformidade com LGPD
    - Separação de PII (Personally Identifiable Information)

    ---

    📚 **Documentação Completa:** `/docs/novas_funcionalidades.md`
    """

    # Enable OpenAPI docs by default, disable only in production with DEBUG=false
    docs_url = "/docs"
    redoc_url = "/redoc"

    application = FastAPI(
        title="Analisador de Currículos",
        version=settings.app_version,
        description=description,
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        contact={
            "name": "Equipe de Desenvolvimento",
            "url": "https://github.com/ZerocouldBR/Analisador_de_curriculos",
        },
        license_info={
            "name": "MIT",
        }
    )

    # Security headers middleware
    class SecurityHeadersMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            response: Response = await call_next(request)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
            if request.url.scheme == "https":
                response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            return response

    application.add_middleware(SecurityHeadersMiddleware)

    # Request logging middleware
    application.add_middleware(RequestLoggingMiddleware)

    # CORS middleware for frontend (configurable via CORS_ORIGINS env var)
    # Seguranca: nao permitir credentials com wildcard origin
    cors_allow_credentials = "*" not in settings.cors_origins
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=cors_allow_credentials,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # Prometheus instrumentation
    Instrumentator().instrument(application).expose(application, endpoint="/metrics")

    application.include_router(api_router, prefix="/api")

    return application


app = create_app()
