"""Tests for the multi-LLM ensemble critic.

Strategy: mock litellm.completion. Verify the fanout / majority-vote logic
without touching real APIs. Also verify graceful degradation when:
  - litellm not installed
  - 0 / 1 providers configured
  - All API calls fail
"""
from __future__ import annotations
import sys
from unittest.mock import MagicMock, patch

import pytest

from marketing_agent.ensemble_critic import (
    _configured_providers, ensemble_score,
)
from marketing_agent.types import Platform, Post


def _post(text: str = "A solid build-in-public post about marketing-agent") -> Post:
    return Post(platform=Platform.X, body=text).with_count()


# ──────────────── _configured_providers ────────────────


def test_configured_providers_returns_set_keys(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "y")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    out = _configured_providers()
    envs = [e for e, _m in out]
    assert "ANTHROPIC_API_KEY" in envs
    assert "OPENAI_API_KEY" in envs
    assert "GEMINI_API_KEY" not in envs


def test_configured_providers_empty_without_keys(monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert _configured_providers() == []


# ──────────────── ensemble_score graceful degradation ────────────────


def test_ensemble_returns_none_without_litellm(monkeypatch):
    monkeypatch.setitem(sys.modules, "litellm", None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "y")
    out = ensemble_score(_post())
    assert out is None


def test_ensemble_returns_none_when_zero_providers(monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    out = ensemble_score(_post())
    assert out is None


# ──────────────── ensemble_score behavior with mocked litellm ────────────────


def _fake_litellm_response(text: str) -> MagicMock:
    """Build a minimal MagicMock that mimics litellm.completion's return shape."""
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def test_ensemble_majority_vote_rejects_when_2_of_3_say_reject(monkeypatch):
    """2/3 critics say SCORE: 2 → reject; 1 says SCORE: 8."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("OPENAI_API_KEY", "o")
    monkeypatch.setenv("GEMINI_API_KEY", "g")

    # Fake module so the import inside _ask_one finds something
    fake_litellm = MagicMock()
    # The 3 critics return different scores
    fake_litellm.completion.side_effect = [
        _fake_litellm_response("SCORE: 2\nREASON: hype-laden"),
        _fake_litellm_response("SCORE: 8\nREASON: solid post"),
        _fake_litellm_response("SCORE: 3\nREASON: generic platitudes"),
    ]
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)

    out = ensemble_score(_post())
    assert out is not None
    # Min score wins (harshest critic) → 2.0
    assert out.score == 2.0
    # Majority (2/3) said < min_score → auto_reject
    assert out.auto_reject is True
    # All 3 reasons collected
    assert len(out.reasons) == 3


def test_ensemble_passes_when_majority_say_pass(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("OPENAI_API_KEY", "o")
    monkeypatch.setenv("GEMINI_API_KEY", "g")

    fake_litellm = MagicMock()
    fake_litellm.completion.side_effect = [
        _fake_litellm_response("SCORE: 8\nREASON: solid"),
        _fake_litellm_response("SCORE: 9\nREASON: ship it"),
        _fake_litellm_response("SCORE: 2\nREASON: outlier hates it"),
    ]
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)

    out = ensemble_score(_post())
    assert out is not None
    # Min wins for score (the harsh outlier)
    assert out.score == 2.0
    # But majority say pass → no auto_reject
    assert out.auto_reject is False


def test_ensemble_skips_failed_provider(monkeypatch):
    """If 1 of 3 calls raises, ensemble continues with the surviving 2."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("OPENAI_API_KEY", "o")
    monkeypatch.setenv("GEMINI_API_KEY", "g")

    fake_litellm = MagicMock()
    fake_litellm.completion.side_effect = [
        _fake_litellm_response("SCORE: 8\nREASON: solid"),
        Exception("rate limit"),
        _fake_litellm_response("SCORE: 7\nREASON: fine"),
    ]
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)

    out = ensemble_score(_post())
    assert out is not None
    assert len(out.reasons) == 2  # Only 2 critics responded
    assert out.score == 7.0       # min of (8, 7)


def test_ensemble_returns_none_when_all_fail(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("OPENAI_API_KEY", "o")
    fake_litellm = MagicMock()
    fake_litellm.completion.side_effect = Exception("everything is broken")
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)
    out = ensemble_score(_post())
    assert out is None
