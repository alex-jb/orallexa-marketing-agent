"""Tests for the heuristic + LLM critic."""
from __future__ import annotations


from marketing_agent.critic import (
    CritiqueResult, critique, heuristic_score, llm_score,
)
from marketing_agent.types import Platform, Post


def _post(body: str, platform: Platform = Platform.X, **kw) -> Post:
    return Post(platform=platform, body=body, **kw).with_count()


def test_clean_post_scores_high():
    p = _post("Shipped v0.4 of marketing-agent today: variant bandit + "
              "best-time analyzer + MCP server. 67 tests pass. "
              "https://github.com/x/y")
    r = heuristic_score(p)
    assert r.score >= 8.5
    assert not r.auto_reject


def test_hype_words_drop_score():
    p = _post("Revolutionary game-changing AI-powered solution to "
              "supercharge your workflow. Cutting-edge.")
    r = heuristic_score(p)
    assert r.score < 5
    assert r.auto_reject
    assert any("hype" in reason for reason in r.reasons)


def test_overshoot_x_limit_penalized():
    long_body = ("a " * 200).strip()  # 399 chars > 280 limit
    p = _post(long_body)
    r = heuristic_score(p)
    assert any("over x limit" in reason for reason in r.reasons)


def test_too_short_penalized():
    p = _post("short")
    r = heuristic_score(p)
    assert r.auto_reject


def test_excessive_caps_penalized():
    p = _post("THIS IS A VERY EXCITING ANNOUNCEMENT EVERYONE LOOK AT IT")
    r = heuristic_score(p)
    assert any("caps" in reason for reason in r.reasons)


def test_hashtag_spam_on_x_penalized():
    p = _post("Shipped a thing #ai #ml #python #startup #buildinpublic "
              "#dev https://example.com")
    r = heuristic_score(p)
    assert any("hashtag" in reason for reason in r.reasons)


def test_llm_score_returns_none_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    p = _post("Hello world.")
    assert llm_score(p) is None


def test_critique_falls_back_to_heuristic_without_llm(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    p = _post("Solid post about a real shipped thing. https://x.com/y")
    r = critique(p)
    assert isinstance(r, CritiqueResult)
    # Without LLM, score == heuristic
    assert r.score == heuristic_score(p).score


def test_critique_use_llm_false_skips_api():
    p = _post("Decent post body of moderate length describing a thing.")
    r = critique(p, use_llm=False)
    assert r.score == heuristic_score(p).score
