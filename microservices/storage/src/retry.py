"""
Retry decorator for the storage microservice.

Reliability guarantee: HDFS operations (WebHDFS calls, NameNode health
checks) are automatically retried with exponential back-off before
propagating the error.

This avoids failures caused by short-lived NameNode unavailability,
DataNode registration delays, or transient network issues.
"""

from __future__ import annotations

import logging
import time
from functools import wraps
from typing import Callable, TypeVar, Any

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# Default settings
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_BACKOFF_SEC = 2.0
_DEFAULT_BACKOFF_FACTOR = 2.0

# Exceptions considered transient
_TRANSIENT_EXCEPTIONS: tuple[type[BaseException], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
    IOError,
)


def retry(
    max_retries: int = _DEFAULT_MAX_RETRIES,
    backoff_sec: float = _DEFAULT_BACKOFF_SEC,
    backoff_factor: float = _DEFAULT_BACKOFF_FACTOR,
    retryable_exceptions: tuple[type[BaseException], ...] = _TRANSIENT_EXCEPTIONS,
) -> Callable[[F], F]:
    """Decorator that retries a function on transient exceptions.

    Parameters
    ----------
    max_retries : int
        Maximum number of retry attempts (0 = no retries).
    backoff_sec : float
        Initial wait time in seconds between retries.
    backoff_factor : float
        Multiplier applied to ``backoff_sec`` after each retry.
    retryable_exceptions : tuple
        Exception types that trigger a retry.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: BaseException | None = None
            wait = backoff_sec

            for attempt in range(1, max_retries + 2):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as exc:
                    last_exc = exc
                    if attempt > max_retries:
                        logger.error(
                            "[retry] %s failed after %d attempt(s): %s",
                            func.__qualname__, attempt, exc,
                        )
                        raise
                    logger.warning(
                        "[retry] %s attempt %d/%d failed (%s). "
                        "Retrying in %.1fs …",
                        func.__qualname__, attempt, max_retries + 1,
                        exc, wait,
                    )
                    time.sleep(wait)
                    wait *= backoff_factor

            raise last_exc  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    return decorator
