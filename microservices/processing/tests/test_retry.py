"""
Tests for the retry utility decorator.
Covers successful call, retried call, exhausted retries,
and non-retryable exception propagation.
"""

from __future__ import annotations

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pytest

from src.retry import retry


class TestRetryDecorator:
    """Validate the @retry decorator behaviour."""

    # ── Successful call (no retry needed) ───────────────────────────────

    def test_successful_call_no_retry(self):
        """A function that succeeds on first attempt should return normally."""
        print("\n[TEST] test_successful_call_no_retry")

        call_count = {"n": 0}

        @retry(max_retries=3, backoff_sec=0.01)
        def always_ok():
            call_count["n"] += 1
            return "ok"

        result = always_ok()
        assert result == "ok"
        print("  ✓ returned 'ok'")
        assert call_count["n"] == 1
        print("  ✓ function called exactly once")

    # ── Succeeds after transient failures ───────────────────────────────

    def test_retried_then_success(self):
        """Function should succeed after transient ConnectionError retries."""
        print("\n[TEST] test_retried_then_success")

        call_count = {"n": 0}

        @retry(max_retries=5, backoff_sec=0.01)
        def fail_twice():
            call_count["n"] += 1
            if call_count["n"] <= 2:
                raise ConnectionError("transient")
            return "recovered"

        result = fail_twice()
        assert result == "recovered"
        print("  ✓ returned 'recovered' after retries")
        assert call_count["n"] == 3
        print("  ✓ function called 3 times (2 failures + 1 success)")

    # ── Exhausted retries ───────────────────────────────────────────────

    def test_exhausted_retries_raises(self):
        """If all retries are used, the original exception should propagate."""
        print("\n[TEST] test_exhausted_retries_raises")

        call_count = {"n": 0}

        @retry(max_retries=2, backoff_sec=0.01)
        def always_fail():
            call_count["n"] += 1
            raise ConnectionError("permanent")

        with pytest.raises(ConnectionError, match="permanent"):
            always_fail()

        print("  ✓ ConnectionError raised after retries exhausted")
        # Initial call + 2 retries = 3 total
        assert call_count["n"] == 3
        print("  ✓ function called 3 times total")

    # ── Non-retryable exception ─────────────────────────────────────────

    def test_non_retryable_exception_propagates_immediately(self):
        """ValueError is not retryable and should propagate on first failure."""
        print("\n[TEST] test_non_retryable_exception_propagates_immediately")

        call_count = {"n": 0}

        @retry(max_retries=5, backoff_sec=0.01)
        def raise_value_error():
            call_count["n"] += 1
            raise ValueError("bad input")

        with pytest.raises(ValueError, match="bad input"):
            raise_value_error()

        print("  ✓ ValueError propagated immediately")
        assert call_count["n"] == 1
        print("  ✓ function called exactly once (no retry)")

    # ── Custom retryable exceptions ─────────────────────────────────────

    def test_custom_retryable_exceptions(self):
        """The decorator should accept custom retryable exception types."""
        print("\n[TEST] test_custom_retryable_exceptions")

        call_count = {"n": 0}

        @retry(max_retries=3, backoff_sec=0.01, retryable_exceptions=(RuntimeError,))
        def custom_fail():
            call_count["n"] += 1
            if call_count["n"] <= 1:
                raise RuntimeError("recoverable")
            return "done"

        result = custom_fail()
        assert result == "done"
        print("  ✓ succeeded after RuntimeError retry")
        assert call_count["n"] == 2
        print("  ✓ called twice (1 failure + 1 success)")

    # ── Exponential backoff factor ──────────────────────────────────────

    def test_backoff_factor_increases_delay(self):
        """With backoff_factor > 1, later retries should take longer (smoke test)."""
        print("\n[TEST] test_backoff_factor_increases_delay")

        import time

        call_count = {"n": 0}

        @retry(max_retries=2, backoff_sec=0.05, backoff_factor=2.0)
        def fail_once():
            call_count["n"] += 1
            if call_count["n"] <= 1:
                raise ConnectionError("oops")
            return "ok"

        t0 = time.monotonic()
        result = fail_once()
        elapsed = time.monotonic() - t0

        assert result == "ok"
        print("  ✓ returned 'ok'")
        # With backoff_sec=0.05 and factor=2.0, first retry sleeps ~0.05 s
        assert elapsed >= 0.04  # allow small tolerance
        print(f"  ✓ elapsed {elapsed:.3f}s >= 0.04s (backoff observed)")
