"""Retry decorator with exponential backoff + jitter — for platform adapters.

Why not tenacity? It's 130KB of dep weight for a feature we use in 6 places.
This is 30 lines, zero deps, identical semantics for our use case.

Usage:
    @retry_on_transient(attempts=3, base_delay=1.0)
    def post_to_x(...):
        ...

Retries on:
  - ConnectionError / Timeout (network)
  - 5xx HTTP status (server error)
  - X / Reddit / Bluesky rate-limit responses (429)

Does NOT retry on:
  - 4xx other than 429 (auth, malformed → won't fix itself)
  - NotConfigured (the user has to set creds; retrying won't help)
"""
from __future__ import annotations
import functools
import random
import time
from typing import Callable, TypeVar

from marketing_agent.logging import get_logger

T = TypeVar("T")
log = get_logger(__name__)


def _is_transient(exc: BaseException) -> bool:
    """Heuristic: should we retry this exception?"""
    msg = str(exc).lower()
    if any(s in msg for s in ("timeout", "connection", "temporarily",
                                "rate limit", "429", "503", "502", "504")):
        return True
    # tweepy.TooManyRequests, requests.ConnectionError, etc.
    cls = type(exc).__name__
    if cls in ("TooManyRequests", "ConnectionError", "Timeout",
                "ReadTimeoutError", "ConnectTimeout"):
        return True
    # HTTP status code attribute (requests, httpx)
    code = getattr(exc, "status_code", None) or getattr(
        getattr(exc, "response", None), "status_code", None)
    if isinstance(code, int) and (code == 429 or 500 <= code < 600):
        return True
    return False


def retry_on_transient(*, attempts: int = 3, base_delay: float = 1.0,
                        max_delay: float = 30.0,
                        retry_on: Callable[[BaseException], bool] = _is_transient
                        ) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Exponential backoff + 25% jitter. Final attempt re-raises."""
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapped(*args, **kwargs) -> T:
            for i in range(attempts):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    if i == attempts - 1 or not retry_on(e):
                        raise
                    delay = min(max_delay, base_delay * (2 ** i))
                    delay *= 1.0 + random.uniform(-0.25, 0.25)
                    log.warning(
                        "retrying %s after %.2fs (attempt %d/%d): %s",
                        fn.__name__, delay, i + 1, attempts, e,
                        extra={"fn": fn.__name__, "attempt": i + 1,
                                "delay": round(delay, 3),
                                "error_type": type(e).__name__},
                    )
                    time.sleep(delay)
            raise RuntimeError("unreachable")  # pragma: no cover
        return wrapped
    return decorator
