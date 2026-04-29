"""Tests for structured logging."""
from __future__ import annotations
import json
import logging

import pytest

from marketing_agent.logging import JsonFormatter


def test_json_formatter_emits_valid_json():
    rec = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="hello %s", args=("world",), exc_info=None,
    )
    out = JsonFormatter().format(rec)
    obj = json.loads(out)
    assert obj["level"] == "info"
    assert obj["msg"] == "hello world"
    assert obj["logger"] == "test"
    assert "ts" in obj


def test_json_formatter_includes_extra_fields():
    rec = logging.LogRecord(
        name="test", level=logging.WARNING, pathname=__file__, lineno=1,
        msg="x", args=(), exc_info=None,
    )
    rec.user_id = 42
    rec.action = "post"
    out = JsonFormatter().format(rec)
    obj = json.loads(out)
    assert obj["user_id"] == 42
    assert obj["action"] == "post"


def test_json_formatter_handles_unserializable():
    """Non-JSON values get repr()'d, never crash."""
    rec = logging.LogRecord(
        name="t", level=logging.ERROR, pathname=__file__, lineno=1,
        msg="fail", args=(), exc_info=None,
    )
    class Weird:
        def __repr__(self): return "<Weird>"
    rec.weird = Weird()
    out = JsonFormatter().format(rec)
    obj = json.loads(out)
    assert obj["weird"] == "<Weird>"


def test_get_logger_idempotent(monkeypatch):
    monkeypatch.delenv("MARKETING_AGENT_LOG", raising=False)
    monkeypatch.delenv("MARKETING_AGENT_LOG_LEVEL", raising=False)
    import marketing_agent.logging as ml
    monkeypatch.setattr(ml, "_CONFIGURED", False)
    log1 = ml.get_logger("test1")
    log2 = ml.get_logger("test1")
    assert log1 is log2
