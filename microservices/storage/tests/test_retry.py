"""Tests for :mod:`microservices.storage.src.retry`.

Covers reliability guarantee:
  - Exponential back-off for transient HDFS failures
  - Non-retryable exceptions propagate immediately
  - Function metadata preserved
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

_project_root = str(Path(__file__).resolve().parents[3])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from microservices.storage.src.retry import retry


class TestRetryDecorator:
    """Verify exponential back-off retries and exception propagation."""

    def test_succeeds_first_try(self) -> None:
        print("\n[TEST] Function succeeds on first try")
        call_count = 0

        @retry(max_retries=3, backoff_sec=0.01)
        def always_ok() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        result = always_ok()
        print(f"  Result: {result}")
        print(f"  Call count: {call_count}")
        assert result == "ok"
        assert call_count == 1
        print("  ✓ No retries needed")

    def test_retries_then_succeeds(self) -> None:
        print("\n[TEST] Function retries then succeeds")
        call_count = 0

        @retry(max_retries=3, backoff_sec=0.01)
        def fail_twice() -> str:
            nonlocal call_count
            call_count += 1
            print(f"  Attempt {call_count}...")
            if call_count < 3:
                raise ConnectionError("transient")
            return "recovered"

        result = fail_twice()
        print(f"  Final result: {result}")
        print(f"  Total attempts: {call_count}")
        assert result == "recovered"
        assert call_count == 3
        print("  ✓ Recovered after 2 failures")

    def test_exhausts_retries_then_raises(self) -> None:
        print("\n[TEST] Exhausts retries then raises exception")
        call_count = 0

        @retry(max_retries=2, backoff_sec=0.01)
        def always_fail() -> None:
            nonlocal call_count
            call_count += 1
            print(f"  Attempt {call_count} - failing...")
            raise ConnectionError("persistent")

        with pytest.raises(ConnectionError, match="persistent"):
            always_fail()

        print(f"  Total attempts: {call_count} (1 initial + 2 retries)")
        assert call_count == 3
        print("  ✓ Exception propagated after max retries")

    def test_non_retryable_exception_not_retried(self) -> None:
        print("\n[TEST] Non-retryable exception not retried")
        call_count = 0

        @retry(
            max_retries=3,
            backoff_sec=0.01,
            retryable_exceptions=(ConnectionError,),
        )
        def raise_value_error() -> None:
            nonlocal call_count
            call_count += 1
            print(f"  Attempt {call_count} - raising ValueError...")
            raise ValueError("not retryable")

        with pytest.raises(ValueError, match="not retryable"):
            raise_value_error()

        print(f"  Call count: {call_count}")
        assert call_count == 1
        print("  ✓ No retry for non-retryable exception")

    def test_exponential_backoff_timing(self) -> None:
        print("\n[TEST] Exponential backoff timing")
        call_count = 0

        @retry(max_retries=2, backoff_sec=0.05, backoff_factor=2.0)
        def always_fail() -> None:
            nonlocal call_count
            call_count += 1
            raise OSError("disk")

        start = time.monotonic()
        with pytest.raises(OSError):
            always_fail()
        elapsed = time.monotonic() - start

        print(f"  Elapsed: {elapsed:.3f}s")
        print(f"  Expected minimum: ~0.15s (0.05 + 0.10)")
        # Allow some tolerance
        assert elapsed >= 0.10
        print("  ✓ Exponential back-off delay applied")

    def test_preserves_function_metadata(self) -> None:
        print("\n[TEST] Preserves function name and docstring")

        @retry(max_retries=1, backoff_sec=0.01)
        def my_func() -> None:
            """Docstring."""

        print(f"  __name__ = '{my_func.__name__}'")
        print(f"  __doc__  = '{my_func.__doc__}'")
        assert my_func.__name__ == "my_func"
        assert my_func.__doc__ == "Docstring."
        print("  ✓ Metadata preserved via @wraps")
