"""Tests for :mod:`microservices.ingestion.src.logging_config`."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import pytest

# Add project root to path for direct execution
_project_root = str(Path(__file__).resolve().parents[3])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from microservices.ingestion.src.logging_config import configure_logging


class TestConfigureLogging:
    """Ensure configure_logging sets up handlers correctly."""

    def _reset_root(self) -> None:
        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(logging.WARNING)

    def test_text_format_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        print("\n[TEST] Default text format logging")
        self._reset_root()
        monkeypatch.delenv("LOG_FORMAT", raising=False)
        monkeypatch.delenv("LOG_LEVEL", raising=False)

        configure_logging()
        print("  Configured with default settings")

        root = logging.getLogger()
        print(f"  Log level: {logging.getLevelName(root.level)}")
        print(f"  Handlers: {len(root.handlers)}")
        assert root.level == logging.INFO
        assert len(root.handlers) == 1
        # Text formatter should NOT produce JSON
        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "hello", (), None
        )
        output = root.handlers[0].format(record)
        print(f"  Sample output: {output[:60]}...")
        assert "hello" in output
        print(f"  ✓ Text format (not JSON)")
        # Should not be valid JSON (text format)
        with pytest.raises(json.JSONDecodeError):
            json.loads(output)

    def test_json_format(self, monkeypatch: pytest.MonkeyPatch) -> None:
        print("\n[TEST] JSON format logging")
        self._reset_root()
        monkeypatch.setenv("LOG_FORMAT", "json")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        configure_logging()
        print("  Configured with LOG_FORMAT=json, LOG_LEVEL=DEBUG")

        root = logging.getLogger()
        print(f"  Log level: {logging.getLevelName(root.level)}")
        assert root.level == logging.DEBUG
        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "hello", (), None
        )
        output = root.handlers[0].format(record)
        print(f"  Sample output: {output[:80]}...")
        parsed = json.loads(output)
        print(f"  Parsed fields: {list(parsed.keys())}")
        print(f"  Message: {parsed['message']}")
        print(f"  Level: {parsed['level']}")
        print(f"  ✓ Valid JSON with correct structure")
        assert parsed["message"] == "hello"
        assert parsed["level"] == "INFO"
        assert "timestamp" in parsed

    def test_clears_previous_handlers(self) -> None:
        self._reset_root()
        root = logging.getLogger()
        root.addHandler(logging.StreamHandler())
        root.addHandler(logging.StreamHandler())
        assert len(root.handlers) == 2

        configure_logging()
        assert len(root.handlers) == 1

    def test_custom_log_level(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._reset_root()
        monkeypatch.setenv("LOG_LEVEL", "ERROR")

        configure_logging()

        assert logging.getLogger().level == logging.ERROR
