"""Tests for VibeXForge integration client."""
from __future__ import annotations

from marketing_agent.integrations import VibeXForgeClient


def test_not_configured_without_token(monkeypatch):
    monkeypatch.delenv("VIBEXFORGE_API_TOKEN", raising=False)
    monkeypatch.delenv("VIBEXFORGE_API_URL", raising=False)
    c = VibeXForgeClient()
    assert c.is_configured() is False
    # Methods should no-op gracefully
    assert c.fetch_project("anything") is None
    assert c.push_post_event("p", platform="x", post_url="https://x.com/abc") is False


def test_explicit_token_makes_configured():
    c = VibeXForgeClient(base_url="https://example.com", token="t1")
    assert c.is_configured() is True
