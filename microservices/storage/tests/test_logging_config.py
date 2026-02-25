"""Tests for :mod:`microservices.storage.src.logging_config`.

Covers maintainability guarantee:
  - Structured JSON logging in production
  - Human-readable logging in development
  - Configurable via environment variables
"""

from __future__ import annotations

import json
import logging
import sys
from io import StringIO
from pathlib import Path

import pytest

_project_root = str(Path(__file__).resolve().parents[3])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from microservices.storage.src.logging_config import configure_logging


class TestLoggingConfig:
    """Verify logging configuration."""

    def _capture_log(self, monkeypatch: pytest.MonkeyPatch,
                     fmt: str, level: str = "INFO") -> str:
        """Helper: configure logging, emit a message, return captured output."""
        monkeypatch.setenv("LOG_FORMAT", fmt)
        monkeypatch.setenv("LOG_LEVEL", level)
        configure_logging()

        # Capture output
        buf = StringIO()
        root = logging.getLogger()
        for handler in root.handlers:
            handler.stream = buf

        test_logger = logging.getLogger("test.storage")
        test_logger.info("healthcheck passed")
        return buf.getvalue()

    def test_json_format(self, monkeypatch: pytest.MonkeyPatch) -> None:
        print("\n[TEST] JSON log format (production mode)")
        output = self._capture_log(monkeypatch, "json")
        print(f"  Raw output: {output.strip()}")
        record = json.loads(output.strip())
        print(f"  Parsed keys: {sorted(record.keys())}")
        assert record["service"] == "storage"
        assert record["message"] == "healthcheck passed"
        assert "timestamp" in record
        assert "level" in record
        print("  ✓ JSON log contains service, message, timestamp, level")

    def test_text_format(self, monkeypatch: pytest.MonkeyPatch) -> None:
        print("\n[TEST] Text log format (development mode)")
        output = self._capture_log(monkeypatch, "text")
        print(f"  Output: {output.strip()}")
        assert "healthcheck passed" in output
        assert "INFO" in output
        print("  ✓ Human-readable log format")

    def test_log_level_respected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        print("\n[TEST] Log level filtering (WARNING level)")
        monkeypatch.setenv("LOG_FORMAT", "text")
        monkeypatch.setenv("LOG_LEVEL", "WARNING")
        configure_logging()

        buf = StringIO()
        root = logging.getLogger()
        for handler in root.handlers:
            handler.stream = buf

        test_logger = logging.getLogger("test.level")
        test_logger.info("should be suppressed")
        test_logger.warning("should appear")
        output = buf.getvalue()
        print(f"  Output: {output.strip()}")
        assert "should be suppressed" not in output
        assert "should appear" in output
        print("  ✓ INFO suppressed, WARNING visible at WARNING level")

    def test_noisy_loggers_suppressed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        print("\n[TEST] Noisy third-party loggers are suppressed")
        monkeypatch.setenv("LOG_FORMAT", "text")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        configure_logging()

        urllib3_logger = logging.getLogger("urllib3")
        requests_logger = logging.getLogger("requests")
        print(f"  urllib3 level:  {urllib3_logger.level} (WARNING = {logging.WARNING})")
        print(f"  requests level: {requests_logger.level} (WARNING = {logging.WARNING})")
        assert urllib3_logger.level >= logging.WARNING
        assert requests_logger.level >= logging.WARNING
        print("  ✓ urllib3 and requests loggers set to WARNING+")
