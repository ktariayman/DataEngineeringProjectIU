"""
Structured logging configuration for the processing microservice.

Maintainability guarantee: all processing service logs are machine-parseable
JSON when running in production (``LOG_FORMAT=json``), enabling integration
with ELK / Loki / CloudWatch.  In development the default human-readable
format is preserved.

Usage
-----
Call :func:`configure_logging` once at startup.

    >>> from microservices.processing.src.logging_config import configure_logging
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
            "service": "processing",
        }
        if record.exc_info and record.exc_info[1] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def configure_logging(logger_name: str | None = None) -> logging.Logger:
    """Set up the root logger based on environment variables.

    Parameters
    ----------
    logger_name : str, optional
        If provided, return a named child logger.  Otherwise return the
        root logger after configuration.

    Environment variables
    ---------------------
    LOG_FORMAT : str
        ``"json"`` for structured JSON output (production).
        Anything else (or unset) for human-readable console output.
    LOG_LEVEL : str
        Standard Python log level name (default: ``"INFO"``).

    Returns
    -------
    logging.Logger
        Configured logger instance.
    """
    log_format = os.environ.get("LOG_FORMAT", "text").lower()
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

    root = logging.getLogger()
    root.setLevel(log_level)

    # Remove existing handlers to avoid duplicate output
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
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

    return logging.getLogger(logger_name) if logger_name else root

    # Silence overly chatty Spark / Py4J / Hadoop loggers
    for noisy in ("py4j", "org.apache.spark", "org.sparkproject", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
