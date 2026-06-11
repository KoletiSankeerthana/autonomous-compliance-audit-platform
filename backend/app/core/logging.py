"""
Structured logging configuration.
In production (LOG_FORMAT=json), emits JSON lines compatible with
Datadog, ELK, and Google Cloud Logging.
In development (LOG_FORMAT=text), emits human-readable coloured output.
"""

import logging
import sys
from typing import Any

from app.core.config import settings


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime, timezone

        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        # Attach any extra fields passed via extra={} kwarg
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
            }:
                try:
                    json.dumps(value)   # Confirm serialisable
                    log_obj[key] = value
                except (TypeError, ValueError):
                    log_obj[key] = str(value)

        return json.dumps(log_obj, default=str)


def configure_logging() -> None:
    """
    Apply logging configuration to the root logger.
    Call once at application startup before any logging occurs.
    """
    level = getattr(logging, settings.LOG_LEVEL, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)

    if settings.LOG_FORMAT == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Suppress noisy third-party loggers unless in DEBUG
    if level > logging.DEBUG:
        for noisy in ("uvicorn.access", "sqlalchemy.engine", "chromadb"):
            logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Use at module level: logger = get_logger(__name__)"""
    return logging.getLogger(name)
