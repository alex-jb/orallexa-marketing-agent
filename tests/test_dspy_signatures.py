"""Tests for DSPy signatures — must work whether or not dspy is installed."""
from __future__ import annotations


from marketing_agent.dspy_signatures import (
    compile_if_keyed, get_signatures, is_dspy_available, list_signatures,
)


def test_list_signatures_always_works():
    """Returns the four declared signature names regardless of dspy presence."""
    names = list_signatures()
    assert "DraftPost" in names
    assert "CritiquePost" in names
    assert "RewritePost" in names
    assert "GenerateLaunchPlan" in names


def test_get_signatures_empty_without_dspy(monkeypatch):
    """Without dspy installed, get_signatures() returns {}."""
    import sys
    monkeypatch.setitem(sys.modules, "dspy", None)
    out = get_signatures()
    assert out == {}


def test_compile_if_keyed_returns_none_without_dspy(monkeypatch):
    """No dspy, no compile."""
    import sys
    monkeypatch.setitem(sys.modules, "dspy", None)
    assert compile_if_keyed("DraftPost") is None


def test_compile_if_keyed_returns_none_without_anthropic_key(monkeypatch):
    """Even with dspy, no key → no compile."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert compile_if_keyed("DraftPost") is None


def test_is_dspy_available_returns_bool():
    """Should never raise — returns True or False based on env."""
    assert is_dspy_available() in (True, False)
