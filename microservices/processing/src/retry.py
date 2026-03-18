"""
Retry decorator for the processing microservice.

Reliability guarantee: transient failures (HDFS hiccups, network timeouts,
Spark executor loss) are automatically retried with exponential back-off
before the pipeline fails.

Usage
-----
    @retry(max_retries=3, backoff_sec=2.0)
    def read_from_hdfs(path):
        ...
"""

from __future__ import annotations

import functools
import logging
import time
from typing import Any, Callable, Tuple, Type

logger = logging.getLogger(__name__)

_DEFAULT_RETRYABLE: Tuple[Type[BaseException], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
    IOError,
)


def retry(
    max_retries: int = 3,
    backoff_sec: float = 1.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: Tuple[Type[BaseException], ...] = _DEFAULT_RETRYABLE,
) -> Callable:
    """Decorator that retries a function on transient failures.

    Parameters
    ----------
    max_retries : int
        Maximum number of retry attempts (0 = no retries).
    backoff_sec : float
        Initial wait time (seconds) between retries.
    backoff_factor : float
        Multiplier applied to *backoff_sec* after each retry.
    retryable_exceptions : tuple[type[BaseException], ...]
        Exception types that trigger a retry.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            delay = backoff_sec
            while True:
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as exc:
                    attempt += 1
                    if attempt > max_retries:
                        logger.error(
                            "[retry] %s FAILED after %d attempt(s): %s",
                            func.__name__,
                            attempt,
                            exc,
                        )
                        raise
                    logger.warning(
                        "[retry] %s attempt %d/%d failed (%s). "
                        "Retrying in %.1fs …",
                        func.__name__,
                        attempt,
                        max_retries,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
                    delay *= backoff_factor

        return wrapper

    return decorator
