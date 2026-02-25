"""
Tests for the processing logging configuration.
Covers JSON format, text format, log levels, and the service label.
"""

from __future__ import annotations

import json
import logging
import os

import pytest

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.logging_config import configure_logging


class TestLoggingConfig:
    """Validate structured and plain-text logging behaviour."""

    # ── JSON format ─────────────────────────────────────────────────────

    def test_json_format_contains_service_field(self, capfd):
        """JSON log lines must include 'service': 'processing'."""
        print("\n[TEST] test_json_format_contains_service_field")

        os.environ["LOG_FORMAT"] = "json"
        os.environ.pop("LOG_LEVEL", None)
        logger = configure_logging("test.json_service")

        logger.info("json-service-check")

        captured = capfd.readouterr().err
        lines = [ln for ln in captured.strip().splitlines() if "json-service-check" in ln]
        assert len(lines) >= 1, "Expected at least one log line"
        print("  ✓ JSON log line emitted")

        parsed = json.loads(lines[0])
        assert parsed.get("service") == "processing"
        print("  ✓ 'service' field equals 'processing'")

    def test_json_format_contains_standard_fields(self, capfd):
        """JSON output should include timestamp, level, message, logger."""
        print("\n[TEST] test_json_format_contains_standard_fields")

        os.environ["LOG_FORMAT"] = "json"
        logger = configure_logging("test.json_fields")

        logger.warning("field-check-msg")

        captured = capfd.readouterr().err
        lines = [ln for ln in captured.strip().splitlines() if "field-check-msg" in ln]
        parsed = json.loads(lines[0])

        for key in ("timestamp", "level", "message", "logger"):
            assert key in parsed, f"Missing key: {key}"
            print(f"  ✓ JSON field '{key}' present")

        assert parsed["level"] == "WARNING"
        print("  ✓ Level is WARNING")

    # ── Text format ─────────────────────────────────────────────────────

    def test_text_format_output(self, capfd):
        """When LOG_FORMAT=text, output should NOT be JSON."""
        print("\n[TEST] test_text_format_output")

        os.environ["LOG_FORMAT"] = "text"
        logger = configure_logging("test.text_fmt")

        logger.info("text-format-check")

        captured = capfd.readouterr().err
        lines = [ln for ln in captured.strip().splitlines() if "text-format-check" in ln]
        assert len(lines) >= 1
        print("  ✓ Text log line emitted")

        with pytest.raises(json.JSONDecodeError):
            json.loads(lines[0])
        print("  ✓ Text log line is NOT valid JSON")

    # ── Log level ───────────────────────────────────────────────────────

    def test_log_level_from_env(self, capfd):
        """LOG_LEVEL env var should control the effective level."""
        print("\n[TEST] test_log_level_from_env")

        os.environ["LOG_FORMAT"] = "json"
        os.environ["LOG_LEVEL"] = "ERROR"
        logger = configure_logging("test.level_check")

        logger.warning("should-not-appear")
        logger.error("should-appear")

        captured = capfd.readouterr().err
        assert "should-not-appear" not in captured
        print("  ✓ WARNING message suppressed at ERROR level")
        assert "should-appear" in captured
        print("  ✓ ERROR message emitted at ERROR level")

    # ── Default level ───────────────────────────────────────────────────

    def test_default_level_is_info(self, capfd):
        """Without LOG_LEVEL, the default level should be INFO."""
        print("\n[TEST] test_default_level_is_info")

        os.environ["LOG_FORMAT"] = "json"
        os.environ.pop("LOG_LEVEL", None)
        logger = configure_logging("test.default_level")

        logger.debug("debug-msg")
        logger.info("info-msg")

        captured = capfd.readouterr().err
        assert "debug-msg" not in captured
        print("  ✓ DEBUG message suppressed at default INFO level")
        assert "info-msg" in captured
        print("  ✓ INFO message emitted at default INFO level")

    # ── Cleanup ─────────────────────────────────────────────────────────

    @pytest.fixture(autouse=True)
    def _cleanup_env(self):
        """Remove test env vars after each test."""
        yield
        os.environ.pop("LOG_FORMAT", None)
        os.environ.pop("LOG_LEVEL", None)
