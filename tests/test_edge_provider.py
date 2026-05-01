"""Tests for the Cloudflare Workers AI edge provider."""
from __future__ import annotations
import json
from unittest.mock import MagicMock, patch


from marketing_agent.llm.edge_provider import (
    DEFAULT_MODEL, EdgeLLM, EdgeLLMResponse, complete_via_edge,
    is_edge_configured,
)


# ──────────────── is_edge_configured ────────────────


def test_is_edge_configured_false_without_envs(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    assert is_edge_configured() is False


def test_is_edge_configured_false_with_partial(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "x")
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    assert is_edge_configured() is False


def test_is_edge_configured_true_with_both(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "x")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "y")
    assert is_edge_configured() is True


# ──────────────── EdgeLLM.complete ────────────────


def test_complete_returns_none_without_creds(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    out = EdgeLLM().complete(system_prompt="s", user_prompt="u")
    assert out is None


def _fake_cf_response(text: str = "drafted post body",
                        success: bool = True,
                        in_tokens: int = 100,
                        out_tokens: int = 50) -> MagicMock:
    """Build a urllib response-like mock matching CF's wrapper shape."""
    payload = {
        "success": success,
        "result": {
            "response": text,
            "usage": {
                "prompt_tokens": in_tokens,
                "completion_tokens": out_tokens,
            },
        },
    }
    if not success:
        payload["errors"] = [{"message": "rate limit"}]
    fake = MagicMock()
    fake.read.return_value = json.dumps(payload).encode("utf-8")
    cm = MagicMock()
    cm.__enter__.return_value = fake
    cm.__exit__.return_value = False
    return cm


def test_complete_returns_response_on_success(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc")
    with patch("urllib.request.urlopen",
                  return_value=_fake_cf_response("hello world")):
        out = EdgeLLM().complete(system_prompt="s", user_prompt="u")
    assert isinstance(out, EdgeLLMResponse)
    assert out.text == "hello world"
    assert out.model == DEFAULT_MODEL
    assert out.usage_in_tokens == 100
    assert out.usage_out_tokens == 50


def test_complete_returns_none_on_unsuccessful_response(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc")
    with patch("urllib.request.urlopen",
                  return_value=_fake_cf_response("", success=False)):
        out = EdgeLLM().complete(system_prompt="s", user_prompt="u")
    assert out is None


def test_complete_returns_none_on_network_error(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc")
    with patch("urllib.request.urlopen",
                  side_effect=ConnectionError("dns fail")):
        out = EdgeLLM().complete(system_prompt="s", user_prompt="u")
    assert out is None


def test_complete_via_edge_returns_text_on_success(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc")
    with patch("urllib.request.urlopen",
                  return_value=_fake_cf_response("hi there")):
        text = complete_via_edge(system_prompt="s", user_prompt="u")
    assert text == "hi there"


def test_complete_via_edge_returns_none_when_not_configured(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    text = complete_via_edge(system_prompt="s", user_prompt="u")
    assert text is None


def test_complete_passes_correct_url_and_auth(monkeypatch):
    """Verify the URL includes account_id + model and auth header is set."""
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok-abc")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct-xyz")
    seen = {}

    def _capture(req, *a, **kw):
        seen["url"] = req.full_url
        seen["auth"] = req.get_header("Authorization")
        return _fake_cf_response("ok")

    with patch("urllib.request.urlopen", side_effect=_capture):
        EdgeLLM().complete(system_prompt="s", user_prompt="u")

    assert "acct-xyz" in seen["url"]
    assert "@cf/meta/llama-3.3-70b-instruct-fp8-fast" in seen["url"]
    assert seen["auth"] == "Bearer tok-abc"
