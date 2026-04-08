from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from contextlib import asynccontextmanager
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.routes import api_router
from app.core.config import settings
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação
    """
    # Startup: Inicializar banco de dados
    try:
        from app.db.init_db import init_db
        init_db()
    except Exception as e:
        print(f"Warning: Erro ao inicializar banco de dados: {e}")
        print("  Execute manualmente: python -m app.db.init_db")

    # Startup: Inicializar vector store
    try:
        from app.vectorstore.factory import initialize_vector_store
        await initialize_vector_store()
        print(f"  Vector store initialized: {settings.vector_db_provider.value}")
    except Exception as e:
        print(f"Warning: Erro ao inicializar vector store: {e}")
        print("  O vector store sera inicializado sob demanda na primeira requisicao")

    yield
    # Shutdown: Limpeza se necessário


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

    # Disable OpenAPI docs in production
    docs_url = "/docs" if settings.debug else None
    redoc_url = "/redoc" if settings.debug else None

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

    # CORS middleware for frontend (configurable via CORS_ORIGINS env var)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # Prometheus instrumentation
    Instrumentator().instrument(application).expose(application, endpoint="/metrics")

    application.include_router(api_router, prefix="/api")

    return application


app = create_app()
