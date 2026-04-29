"""Tests for retry_on_transient decorator."""
from __future__ import annotations
import time

import pytest

from marketing_agent.retry import _is_transient, retry_on_transient


def test_is_transient_recognizes_429():
    class TooManyRequests(Exception):
        status_code = 429
    assert _is_transient(TooManyRequests("rate limit"))


def test_is_transient_recognizes_5xx():
    class ServerError(Exception):
        status_code = 503
    assert _is_transient(ServerError("upstream down"))


def test_is_transient_does_not_retry_404():
    class NotFound(Exception):
        status_code = 404
    assert not _is_transient(NotFound())


def test_retry_succeeds_after_transient_failures(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    calls = {"n": 0}

    @retry_on_transient(attempts=3, base_delay=0.01)
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("network blip")
        return "ok"

    assert flaky() == "ok"
    assert calls["n"] == 3


def test_retry_re_raises_after_exhausting_attempts(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _s: None)

    @retry_on_transient(attempts=2, base_delay=0.01)
    def always_fails():
        raise ConnectionError("never resolves")

    with pytest.raises(ConnectionError):
        always_fails()


def test_retry_does_not_retry_non_transient():
    calls = {"n": 0}

    @retry_on_transient(attempts=3, base_delay=0.01)
    def auth_error():
        calls["n"] += 1
        raise PermissionError("403 forbidden")

    with pytest.raises(PermissionError):
        auth_error()
    assert calls["n"] == 1  # No retry attempted


def test_retry_passes_args_through():
    @retry_on_transient(attempts=1, base_delay=0)
    def add(a, b, *, c):
        return a + b + c

    assert add(1, 2, c=3) == 6
