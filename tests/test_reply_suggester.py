"""Tests for reply_suggester.

Strategy: every X-API path is mocked; LLM path either falls back when key
is unset or is mocked when set. No live network. The queue submission goes
through a real ApprovalQueue rooted in tmp_path.
"""
from __future__ import annotations
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from marketing_agent.queue import ApprovalQueue
from marketing_agent.reply_suggester import (
    Tweet, fetch_recent_tweets_from_handles, filter_relevant, llm_reply,
    suggest_replies_to_queue, template_reply,
)


def _tweet(text: str, *, tid: str = "1", handle: str = "alice",
            metrics: dict | None = None) -> Tweet:
    return Tweet(
        id=tid, author_id="42", author_handle=handle,
        text=text, created_at=datetime.now(timezone.utc),
        public_metrics=metrics or {"like_count": 10, "reply_count": 2},
    )


# ───────────────── filter_relevant ─────────────────


def test_filter_relevant_keyword_match_required():
    ts = [_tweet("LLM agents are cool"), _tweet("dinner plans")]
    out = filter_relevant(ts, keywords=["llm"])
    assert len(out) == 1
    assert out[0].text == "LLM agents are cool"


def test_filter_relevant_case_insensitive():
    ts = [_tweet("Building an Agent today")]
    out = filter_relevant(ts, keywords=["agent"])
    assert len(out) == 1


def test_filter_relevant_no_keywords_returns_all_passing_engagement():
    ts = [_tweet("a", metrics={"like_count": 0}),
            _tweet("b", metrics={"like_count": 100})]
    out = filter_relevant(ts, min_engagement=50)
    assert len(out) == 1
    assert out[0].text == "b"


def test_filter_relevant_engagement_floor_uses_sum_of_metrics():
    ts = [_tweet("x", metrics={"like_count": 3, "reply_count": 4, "retweet_count": 4})]
    # sum = 11, floor 10 → keep
    assert len(filter_relevant(ts, min_engagement=10)) == 1
    assert len(filter_relevant(ts, min_engagement=12)) == 0


def test_filter_relevant_keyword_AND_engagement_both_required():
    ts = [_tweet("LLM thing", metrics={"like_count": 1}),
            _tweet("LLM thing", metrics={"like_count": 100})]
    out = filter_relevant(ts, keywords=["llm"], min_engagement=50)
    assert len(out) == 1
    assert out[0].public_metrics["like_count"] == 100


# ───────────────── template_reply ─────────────────


def test_template_reply_includes_excerpt():
    t = _tweet("Just shipped a new feature", tid="abc")
    r = template_reply(t)
    assert "Just shipped" in r
    assert "draft" in r.lower()


def test_template_reply_deterministic_per_tweet_id():
    t = _tweet("same content", tid="42")
    r1 = template_reply(t)
    r2 = template_reply(t)
    assert r1 == r2  # opener picked by hash(id) — stable


def test_template_reply_truncates_long_tweets():
    t = _tweet("x" * 500, tid="xx")
    r = template_reply(t)
    # 60-char excerpt + opener + suffix; never balloon
    assert len(r) < 200


# ───────────────── llm_reply ─────────────────


def test_llm_reply_falls_back_to_template_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    t = _tweet("LLM is interesting today")
    r = llm_reply(t)
    # Same as what template_reply would produce
    assert r == template_reply(t)


def test_llm_reply_calls_anthropic_when_keyed(monkeypatch):
    """With key set + AnthropicClient mocked, llm_reply returns the mocked text.

    Mocks the anthropic_compat shim — works regardless of whether the real
    solo-founder-os is installed in the test env."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    fake_resp = MagicMock()  # opaque blob — extract_text reads it
    fake_client = MagicMock()
    fake_client.configured = True
    fake_client.messages_create.return_value = (fake_resp, None)

    import marketing_agent.llm.anthropic_compat as compat
    monkeypatch.setattr(compat, "AnthropicClient",
                          MagicMock(return_value=fake_client))
    monkeypatch.setattr(compat.AnthropicClient, "extract_text",
                          MagicMock(return_value="Sharp point. The bottleneck I keep hitting is X."))

    import marketing_agent.reply_suggester as rs
    t = _tweet("Agents are eating the world")
    r = rs.llm_reply(t)
    assert "Sharp point" in r
    assert fake_client.messages_create.called


# ───────────────── fetch_recent_tweets_from_handles ─────────────────


def test_fetch_returns_empty_without_x_creds(monkeypatch):
    for k in ("X_API_KEY", "X_API_KEY_SECRET",
                "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        monkeypatch.delenv(k, raising=False)
    out = fetch_recent_tweets_from_handles(["@alice"])
    assert out == []


# ───────────────── suggest_replies_to_queue end-to-end ─────────────────


def test_suggest_replies_returns_empty_when_no_x_creds(monkeypatch, tmp_path):
    for k in ("X_API_KEY", "X_API_KEY_SECRET",
                "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("MARKETING_AGENT_QUEUE", str(tmp_path / "queue"))
    paths = suggest_replies_to_queue(["@alice"])
    assert paths == []


def test_suggest_replies_writes_queue_files_with_context(monkeypatch, tmp_path):
    """When fetch returns tweets, drafts are written to queue/pending/ with
    the parent tweet id stored in `target`, plus an HTML-comment context block."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("MARKETING_AGENT_QUEUE", str(tmp_path / "queue"))

    fake_tweets = [
        _tweet("This LLM agent stuff is wild today",
                tid="1234567890", handle="someone"),
    ]
    monkeypatch.setattr(
        "marketing_agent.reply_suggester.fetch_recent_tweets_from_handles",
        lambda *a, **k: fake_tweets,
    )

    paths = suggest_replies_to_queue(
        ["@someone"], keywords=["llm"], min_engagement=0,
        project_name="test", use_llm=False,
    )
    assert len(paths) == 1
    body = open(paths[0]).read()
    assert "1234567890" in body
    assert "@someone" in body
    assert "This LLM agent stuff" in body
    assert "target: 1234567890" in body  # frontmatter — parent tweet id


def test_suggest_replies_skips_irrelevant_tweets(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("MARKETING_AGENT_QUEUE", str(tmp_path / "queue"))
    fake_tweets = [_tweet("dinner tonight"), _tweet("dog photos")]
    monkeypatch.setattr(
        "marketing_agent.reply_suggester.fetch_recent_tweets_from_handles",
        lambda *a, **k: fake_tweets,
    )
    paths = suggest_replies_to_queue(
        ["@x"], keywords=["llm", "agent"], min_engagement=0, use_llm=False,
    )
    assert paths == []
