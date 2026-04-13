"""
Sistema de logging estruturado para o Analisador de Curriculos

Features:
- Logging estruturado com formato consistente
- Rotacao de arquivos de log
- Niveis de log configuraveis por modulo
- Log de requisicoes HTTP com timing
- Log de erros com stack trace
- Diagnostico de componentes do sistema
"""
import logging
import logging.handlers
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# Diretorio de logs
LOG_DIR = Path(os.environ.get("LOG_DIR", "./logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)


class StructuredFormatter(logging.Formatter):
    """Formatter que produz logs estruturados e legiveis"""

    LEVEL_COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        )[:-3]

        level = record.levelname
        if self.use_colors:
            color = self.LEVEL_COLORS.get(level, "")
            level = f"{color}{level:8s}{self.RESET}"
        else:
            level = f"{level:8s}"

        module = f"{record.name}:{record.lineno}" if record.lineno else record.name
        # Truncar nomes de modulo longos
        if len(module) > 40:
            module = "..." + module[-37:]

        msg = record.getMessage()

        # Adicionar info de excecao se houver
        if record.exc_info and record.exc_info[0] is not None:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)

        parts = [f"{timestamp} | {level} | {module:40s} | {msg}"]

        if record.exc_text:
            parts.append(record.exc_text)

        return "\n".join(parts)


def configure_logging(level: str = "INFO") -> None:
    """
    Configura o sistema de logging completo

    Args:
        level: Nivel de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Limpar handlers existentes
    root_logger.handlers.clear()

    # Console handler (com cores)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    console_handler.setFormatter(StructuredFormatter(use_colors=True))
    root_logger.addHandler(console_handler)

    # Arquivo de log geral (com rotacao)
    general_log = LOG_DIR / "app.log"
    file_handler = logging.handlers.RotatingFileHandler(
        general_log,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(StructuredFormatter(use_colors=False))
    root_logger.addHandler(file_handler)

    # Arquivo de erros separado
    error_log = LOG_DIR / "error.log"
    error_handler = logging.handlers.RotatingFileHandler(
        error_log,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=10,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(StructuredFormatter(use_colors=False))
    root_logger.addHandler(error_handler)

    # Reduzir verbosidade de loggers externos
    for noisy in [
        "httpcore", "httpx", "urllib3", "asyncio",
        "multipart", "uvicorn.access", "watchfiles",
    ]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # Uvicorn error logger permanece visivel
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    logger = logging.getLogger(__name__)
    logger.info(
        f"Logging configurado: level={level}, "
        f"console=stdout, file={general_log}, errors={error_log}"
    )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware que loga todas as requisicoes HTTP com timing

    Loga:
    - Metodo, path, status code
    - Tempo de resposta
    - IP do cliente
    - Erros com detalhes
    """

    def __init__(self, app, exclude_paths: Optional[list] = None):
        super().__init__(app)
        self.logger = logging.getLogger("http.access")
        self.exclude_paths = exclude_paths or [
            "/health", "/metrics", "/docs", "/redoc", "/openapi.json",
        ]

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip paths que nao precisam de log
        if any(request.url.path.startswith(p) for p in self.exclude_paths):
            return await call_next(request)

        start_time = time.time()
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path
        query = str(request.query_params) if request.query_params else ""

        try:
            response = await call_next(request)
            elapsed = (time.time() - start_time) * 1000  # ms

            status = response.status_code
            log_level = logging.INFO if status < 400 else logging.WARNING if status < 500 else logging.ERROR

            self.logger.log(
                log_level,
                f"{method} {path}"
                f"{' ?' + query if query else ''}"
                f" -> {status}"
                f" ({elapsed:.1f}ms)"
                f" [ip={client_ip}]"
            )

            return response

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            self.logger.error(
                f"{method} {path} -> EXCEPTION ({elapsed:.1f}ms) "
                f"[ip={client_ip}] {type(e).__name__}: {e}",
                exc_info=True,
            )
            raise


def get_component_logger(component: str) -> logging.Logger:
    """
    Retorna logger para um componente especifico do sistema

    Args:
        component: Nome do componente (ex: 'ocr', 'embedding', 'celery')

    Returns:
        Logger configurado
    """
    return logging.getLogger(f"app.{component}")
