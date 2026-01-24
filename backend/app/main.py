from fastapi import FastAPI
from contextlib import asynccontextmanager

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
        print(f"⚠ Erro ao inicializar banco de dados: {e}")
        print("  Execute manualmente: python -m app.db.init_db")

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

    application = FastAPI(
        title="Analisador de Currículos",
        version=settings.app_version,
        description=description,
        lifespan=lifespan,
        contact={
            "name": "Equipe de Desenvolvimento",
            "url": "https://github.com/ZerocouldBR/Analisador_de_curriculos",
        },
        license_info={
            "name": "MIT",
        }
    )

    application.include_router(api_router, prefix="/api")

    return application


app = create_app()
