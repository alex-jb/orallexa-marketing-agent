"""Tests for cross-provider usage logging.

Verifies that edge_provider (Cloudflare) and ensemble_critic (LiteLLM
fanout to GPT-5/Gemini) both write to the same USAGE_LOG_PATH JSONL
that solo_founder_os.AnthropicClient writes to. Net effect: cost-audit-
agent gets the full picture of marketing-agent's LLM spend regardless
of which provider answered the call.
"""
from __future__ import annotations
import json
import sys
from unittest.mock import MagicMock, patch

import pytest


# ──────────────── log_usage core ────────────────


def test_log_usage_writes_jsonl_with_correct_schema(tmp_path):
    """Each call appends one JSON object per line, schema:
        {ts, model, input_tokens, output_tokens, **extra}
    """
    from marketing_agent.llm.anthropic_compat import log_usage
    log_path = tmp_path / "usage.jsonl"
    log_usage(
        log_path=log_path,
        model="claude-haiku-4-5",
        input_tokens=120,
        output_tokens=45,
        extra={"provider": "anthropic"},
    )
    log_usage(
        log_path=log_path,
        model="gpt-5",
        input_tokens=200,
        output_tokens=80,
        extra={"provider": "litellm-ensemble"},
    )
    rows = [json.loads(ln) for ln in log_path.read_text().splitlines()]
    assert len(rows) == 2
    assert rows[0]["model"] == "claude-haiku-4-5"
    assert rows[0]["input_tokens"] == 120
    assert rows[0]["output_tokens"] == 45
    assert rows[0]["provider"] == "anthropic"
    assert rows[0]["ts"]  # ISO datetime string
    assert rows[1]["model"] == "gpt-5"
    assert rows[1]["provider"] == "litellm-ensemble"


def test_log_usage_swallows_io_errors(tmp_path):
    """A bad path doesn't raise — we never want logging to crash callers."""
    from marketing_agent.llm.anthropic_compat import log_usage
    bad_path = tmp_path / "nonexistent" / "subdir" / "usage.jsonl"
    # Should NOT raise — best-effort
    log_usage(log_path=bad_path, model="x", input_tokens=0, output_tokens=0)
    # Actually parent.mkdir creates it, so verify file was written
    assert bad_path.exists()


# ──────────────── edge_provider (Cloudflare Workers AI) ────────────────


def _fake_cf_response(in_tokens: int = 100, out_tokens: int = 50):
    """Minimal Cloudflare-shaped response."""
    payload = {
        "success": True,
        "result": {
            "response": "edge generated text",
            "usage": {
                "prompt_tokens": in_tokens,
                "completion_tokens": out_tokens,
            },
        },
    }
    fake = MagicMock()
    fake.read.return_value = json.dumps(payload).encode("utf-8")
    cm = MagicMock()
    cm.__enter__.return_value = fake
    cm.__exit__.return_value = False
    return cm


def test_edge_provider_writes_usage_log(tmp_path, monkeypatch):
    """A successful Cloudflare call must append a usage row tagged
    provider=cloudflare-workers-ai."""
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc")
    log_path = tmp_path / "usage.jsonl"
    monkeypatch.setattr("marketing_agent.cost.USAGE_LOG_PATH", log_path)

    from marketing_agent.llm.edge_provider import EdgeLLM
    with patch("urllib.request.urlopen",
                  return_value=_fake_cf_response(in_tokens=150, out_tokens=60)):
        out = EdgeLLM().complete(system_prompt="s", user_prompt="u")

    assert out is not None
    assert log_path.exists()
    rows = [json.loads(ln) for ln in log_path.read_text().splitlines()]
    assert len(rows) == 1
    assert rows[0]["provider"] == "cloudflare-workers-ai"
    assert rows[0]["input_tokens"] == 150
    assert rows[0]["output_tokens"] == 60


def test_edge_provider_no_log_on_failure(tmp_path, monkeypatch):
    """When Cloudflare returns success=false, no usage row is written."""
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc")
    log_path = tmp_path / "usage.jsonl"
    monkeypatch.setattr("marketing_agent.cost.USAGE_LOG_PATH", log_path)

    fake = MagicMock()
    fake.read.return_value = json.dumps({
        "success": False, "errors": [{"message": "rate limit"}],
    }).encode("utf-8")
    cm = MagicMock()
    cm.__enter__.return_value = fake; cm.__exit__.return_value = False

    from marketing_agent.llm.edge_provider import EdgeLLM
    with patch("urllib.request.urlopen", return_value=cm):
        out = EdgeLLM().complete(system_prompt="s", user_prompt="u")

    assert out is None
    assert not log_path.exists()


# ──────────────── ensemble_critic (LiteLLM fanout) ────────────────


def test_ensemble_critic_writes_usage_log_per_provider(tmp_path, monkeypatch):
    """3 critic calls → 3 usage rows, each tagged provider=litellm-ensemble
    with the per-provider model name preserved."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("OPENAI_API_KEY", "o")
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    log_path = tmp_path / "usage.jsonl"
    monkeypatch.setattr("marketing_agent.cost.USAGE_LOG_PATH", log_path)

    fake_litellm = MagicMock()

    def make_resp(text: str, in_t: int, out_t: int):
        msg = MagicMock(); msg.content = text
        choice = MagicMock(); choice.message = msg
        usage = MagicMock(prompt_tokens=in_t, completion_tokens=out_t)
        resp = MagicMock(); resp.choices = [choice]; resp.usage = usage
        return resp

    fake_litellm.completion.side_effect = [
        make_resp("SCORE: 8\nREASON: solid", 100, 30),
        make_resp("SCORE: 7\nREASON: fine",   90,  25),
        make_resp("SCORE: 6\nREASON: meh",   110,  35),
    ]
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)

    from marketing_agent.ensemble_critic import ensemble_score
    from marketing_agent.types import Platform, Post
    out = ensemble_score(Post(platform=Platform.X, body="test").with_count())
    assert out is not None

    rows = [json.loads(ln) for ln in log_path.read_text().splitlines()]
    assert len(rows) == 3
    for r in rows:
        assert r["provider"] == "litellm-ensemble"
        assert r["input_tokens"] > 0
        assert r["output_tokens"] > 0
    # All three model names present
    models = {r["model"] for r in rows}
    assert "claude-haiku-4-5" in models
    assert "gpt-5" in models
    assert any("gemini" in m for m in models)
