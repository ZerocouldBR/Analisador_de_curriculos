"""
Sistema de logging estruturado para o Analisador de Curriculos

Fornece:
- Logging estruturado com contexto (request_id, user_id, etc.)
- Rotacao de logs em arquivo
- Diferentes niveis por modulo
- Formatacao consistente para analise de problemas
"""
import logging
import logging.handlers
import os
import sys
import json
from datetime import datetime, timezone
from typing import Optional


LOG_DIR = os.environ.get("LOG_DIR", "./logs")


class StructuredFormatter(logging.Formatter):
    """Formatter que gera logs estruturados em JSON para facilitar analise"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Adicionar contexto extra se disponivel
        for attr in ("request_id", "user_id", "candidate_id", "document_id",
                      "operation", "duration_ms", "status_code", "error_type"):
            value = getattr(record, attr, None)
            if value is not None:
                log_entry[attr] = value

        # Incluir traceback se houver excecao
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
            log_entry["error_type"] = record.exc_info[0].__name__

        return json.dumps(log_entry, ensure_ascii=False, default=str)


class ConsoleFormatter(logging.Formatter):
    """Formatter legivel para console com cores"""

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        # Contexto extra
        extra_parts = []
        for attr in ("request_id", "user_id", "operation", "duration_ms"):
            value = getattr(record, attr, None)
            if value is not None:
                extra_parts.append(f"{attr}={value}")
        extra = f" [{', '.join(extra_parts)}]" if extra_parts else ""

        msg = f"{timestamp} | {color}{record.levelname:8s}{self.RESET} | {record.name:30s} | {record.getMessage()}{extra}"

        if record.exc_info and record.exc_info[0] is not None:
            msg += f"\n{self.formatException(record.exc_info)}"

        return msg


def configure_logging(level: str = "INFO") -> None:
    """
    Configura o sistema de logging da aplicacao

    Args:
        level: Nivel de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Limpar handlers existentes
    root_logger.handlers.clear()

    # Handler de console (formatacao legivel)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ConsoleFormatter())
    console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    root_logger.addHandler(console_handler)

    # Handler de arquivo JSON (rotacao diaria, max 30 dias)
    os.makedirs(LOG_DIR, exist_ok=True)

    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=os.path.join(LOG_DIR, "app.log"),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setFormatter(StructuredFormatter())
    file_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)

    # Arquivo separado para erros
    error_handler = logging.handlers.TimedRotatingFileHandler(
        filename=os.path.join(LOG_DIR, "errors.log"),
        when="midnight",
        interval=1,
        backupCount=60,
        encoding="utf-8",
    )
    error_handler.setFormatter(StructuredFormatter())
    error_handler.setLevel(logging.ERROR)
    root_logger.addHandler(error_handler)

    # Reduzir verbosidade de bibliotecas externas
    for noisy_logger in ("httpcore", "httpx", "urllib3", "sqlalchemy.engine",
                          "uvicorn.access", "celery.worker.strategy"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    # SQLAlchemy engine em INFO mostra queries - util para debug
    if level.upper() == "DEBUG":
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

    logging.getLogger(__name__).info(
        "Logging configurado",
        extra={"operation": "logging_setup", "level": level}
    )


def get_logger(name: str) -> logging.Logger:
    """Retorna logger com nome padronizado"""
    return logging.getLogger(f"app.{name}")
