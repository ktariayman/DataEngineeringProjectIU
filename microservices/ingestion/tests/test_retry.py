"""Tests for :mod:`microservices.ingestion.src.retry`."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

# Add project root to path for direct execution
_project_root = str(Path(__file__).resolve().parents[3])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from microservices.ingestion.src.retry import retry


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
        print(f"  ✓ No retries needed")
        assert result == "ok"
        assert call_count == 1

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
        print(f"  ✓ Recovered after 2 failures")
        assert result == "recovered"
        assert call_count == 3  # 1 initial + 2 retries

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
        print(f"  ✓ Exception propagated after max retries")
        # 1 initial + 2 retries = 3 attempts
        assert call_count == 3

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
        print(f"  ✓ No retry for non-retryable exception")
        assert call_count == 1  # no retry

    def test_exponential_backoff_timing(self) -> None:
        """Rough check that backoff delay is applied."""
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

        # Expected: ~0.05 + ~0.10 = ~0.15s minimum
        assert elapsed >= 0.10

    def test_preserves_function_metadata(self) -> None:
        @retry(max_retries=1, backoff_sec=0.01)
        def my_func() -> None:
            """Docstring."""

        assert my_func.__name__ == "my_func"
        assert my_func.__doc__ == "Docstring."
