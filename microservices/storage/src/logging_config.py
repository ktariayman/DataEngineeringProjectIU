"""
Structured logging configuration for the storage microservice.

Maintainability guarantee: all storage service logs are machine-parseable
JSON when running in production (``LOG_FORMAT=json``), enabling integration
with ELK / Loki / CloudWatch.  In development the default human-readable
format is preserved.

Usage
-----
Call :func:`configure_logging` once at startup.

    >>> from microservices.storage.src.logging_config import configure_logging
    >>> configure_logging()
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone


class _JSONFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        log_entry = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "service": "storage",
        }
        if record.exc_info and record.exc_info[1] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def configure_logging() -> None:
    """Set up the root logger based on environment variables.

    Environment variables
    ---------------------
    LOG_FORMAT : str
        ``"json"`` for structured JSON output (production).
        Anything else (or unset) for human-readable console output.
    LOG_LEVEL : str
        Standard Python log level name (default: ``"INFO"``).
    """
    log_format = os.environ.get("LOG_FORMAT", "text").lower()
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

    root = logging.getLogger()
    root.setLevel(log_level)

    # Remove existing handlers to avoid duplicate output
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    if log_format == "json":
        handler.setFormatter(_JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
            )
        )

    root.addHandler(handler)

    # Silence overly chatty Hadoop/HDFS loggers
    for noisy in ("urllib3", "requests", "hadoop"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
