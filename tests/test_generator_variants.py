"""Tests for the LLM-path variant_hint plumbing.

Background: until v0.18.2 the bandit only ever saw template-mode data
because `_generate_with_llm` produced posts without variant_key. With
LLM mode active in production (from v0.18.x onward) that meant 0
bandit feedback per cron run. This file verifies the fix:

  - When n_variants > 1 and platform has a variant pool, generate_posts
    pre-selects one variant via Thompson sampling, passes it as
    variant_hint to _generate_with_llm, and the returned Post has
    variant_key = "<platform>:<hint>".
  - The system prompt gets a one-sentence style clause appended for
    each known hint.
  - Unknown / None hints are no-ops.
"""
from __future__ import annotations
from unittest.mock import patch

import pytest

from marketing_agent.types import GenerationMode, Platform, Post, Project
from marketing_agent.content.generator import (
    _bandit_variant_hint,
    _post_for,
    _system_for,
    _variant_style_clause,
    generate_posts,
)


@pytest.fixture
def project():
    return Project(name="Demo", tagline="A demo project",
                     recent_changes=["feat: add foo"])


# ───────────────── _variant_style_clause ─────────────────


def test_variant_style_clause_known_hints():
    for hint in ("emoji-led", "question-led", "stat-led"):
        clause = _variant_style_clause(hint)
        assert clause.startswith(" Style:")
        assert len(clause) > 30


def test_variant_style_clause_unknown_hint_returns_empty():
    assert _variant_style_clause("nonsense") == ""


def test_variant_style_clause_none_returns_empty():
    assert _variant_style_clause(None) == ""


# ───────────────── _system_for ─────────────────


def test_system_for_x_includes_emoji_led_clause():
    s = _system_for(Platform.X, variant_hint="emoji-led")
    assert "single tweet" in s
    assert "open the post with a single relevant emoji" in s


def test_system_for_x_no_hint_omits_style_clause():
    s = _system_for(Platform.X)
    assert "single tweet" in s
    assert "open the post with" not in s
    assert "open with a question" not in s
    assert "open with one specific number" not in s


def test_system_for_question_led_clause_distinct_from_stat_led():
    s_q = _system_for(Platform.X, variant_hint="question-led")
    s_s = _system_for(Platform.X, variant_hint="stat-led")
    assert "question your target reader" in s_q
    assert "specific number" in s_s
    assert s_q != s_s


# ───────────────── _post_for ─────────────────


def test_post_for_sets_variant_key_when_hint_given():
    p = _post_for(Platform.X, "hello", Project(name="X", tagline="t"),
                    variant_hint="emoji-led")
    assert p.variant_key == "x:emoji-led"


def test_post_for_no_hint_leaves_variant_key_none():
    p = _post_for(Platform.X, "hello", Project(name="X", tagline="t"))
    assert p.variant_key is None


def test_post_for_reddit_with_hint_keeps_title_and_target():
    p = _post_for(Platform.REDDIT, "body", Project(name="P", tagline="t"),
                    subreddit="ML", variant_hint="question-led")
    assert p.variant_key == "reddit:question-led"
    assert p.target == "ML"
    assert p.title is not None


# ───────────────── _bandit_variant_hint ─────────────────


def test_bandit_variant_hint_returns_none_when_n_variants_one():
    assert _bandit_variant_hint(Platform.X, n_variants=1) is None
    assert _bandit_variant_hint(Platform.X, n_variants=0) is None


def test_bandit_variant_hint_returns_none_for_unsupported_platform():
    # LinkedIn isn't in _LLM_VARIANT_POOLS today.
    assert _bandit_variant_hint(Platform.LINKEDIN, n_variants=3) is None


def test_bandit_variant_hint_returns_pool_member_for_x():
    hint = _bandit_variant_hint(Platform.X, n_variants=3)
    assert hint in {"emoji-led", "question-led", "stat-led"}


def test_bandit_variant_hint_swallows_bandit_errors():
    """If the bandit somehow throws, we return None and the LLM call
    still runs (just without a style hint or variant_key)."""
    with patch(
        "marketing_agent.bandit.VariantBandit.choose",
        side_effect=RuntimeError("bandit blew up"),
    ):
        assert _bandit_variant_hint(Platform.X, n_variants=3) is None


# ───────────────── full generate_posts LLM path ─────────────────


def test_generate_posts_llm_path_tags_variant_key_when_n_variants_gt_one(
    project, monkeypatch,
):
    """When generate_posts goes down the LLM path with n_variants > 1,
    the resulting Post should have a real variant_key (the bandit-
    selected one) — fixing the v0.18.x silent bandit-blind-spot."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-but-truthy")

    captured: dict = {}

    def fake_llm(proj, plat, *, subreddit=None, variant_hint=None):
        captured["variant_hint"] = variant_hint
        return Post(
            platform=plat, body="real LLM body",
            variant_key=(f"{plat.value}:{variant_hint}"
                              if variant_hint else None),
        ).with_count()

    with patch(
        "marketing_agent.content.generator._generate_with_llm",
        side_effect=fake_llm,
    ):
        posts = generate_posts(project, [Platform.X],
                                  mode=GenerationMode.HYBRID,
                                  n_variants=3)

    assert len(posts) == 1
    assert posts[0].variant_key in {
        "x:emoji-led", "x:question-led", "x:stat-led",
    }
    # And the hint actually flowed into _generate_with_llm
    assert captured["variant_hint"] in {
        "emoji-led", "question-led", "stat-led",
    }


def test_generate_posts_llm_path_n_variants_one_skips_hint(project, monkeypatch):
    """n_variants=1 (legacy callers) should NOT pass a variant_hint."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-but-truthy")

    captured: dict = {}

    def fake_llm(proj, plat, *, subreddit=None, variant_hint=None):
        captured["variant_hint"] = variant_hint
        return Post(platform=plat, body="x").with_count()

    with patch(
        "marketing_agent.content.generator._generate_with_llm",
        side_effect=fake_llm,
    ):
        generate_posts(project, [Platform.X],
                          mode=GenerationMode.HYBRID, n_variants=1)

    assert captured["variant_hint"] is None


def test_generate_posts_llm_path_unsupported_platform_skips_hint(
    project, monkeypatch,
):
    """LinkedIn doesn't have a variant pool yet — should pass no hint."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-but-truthy")

    captured: dict = {}

    def fake_llm(proj, plat, *, subreddit=None, variant_hint=None):
        captured["variant_hint"] = variant_hint
        return Post(platform=plat, body="x").with_count()

    with patch(
        "marketing_agent.content.generator._generate_with_llm",
        side_effect=fake_llm,
    ):
        generate_posts(project, [Platform.LINKEDIN],
                          mode=GenerationMode.HYBRID, n_variants=3)

    assert captured["variant_hint"] is None


# ───────────────── X 280-char hard cap (post-LLM safety) ─────────────────


def test_retry_shorter_returns_retry_when_under_cap():
    """When the retry comes back under cap, return that text verbatim."""
    from unittest.mock import MagicMock
    from marketing_agent.content.generator import _retry_shorter

    fake_resp = MagicMock()
    fake_resp.content = [MagicMock(type="text", text="Short rewrite OK")]
    fake_client = MagicMock()
    fake_client.messages_create.return_value = (fake_resp, None)

    out = _retry_shorter(fake_client, Platform.X, "sys", "user", cap=270,
                            current_text="x" * 320)
    assert out == "Short rewrite OK"
    assert len(out) <= 270


def test_retry_shorter_truncates_at_sentence_boundary():
    """When even the retry stays over cap, fall back to mechanical
    truncate at last sentence boundary."""
    from unittest.mock import MagicMock
    from marketing_agent.content.generator import _retry_shorter

    long_retry = ("First sentence here. "
                    "Second sentence with content. "
                    "Third sentence padding. " * 5)
    fake_resp = MagicMock()
    fake_resp.content = [MagicMock(type="text", text=long_retry)]
    fake_client = MagicMock()
    fake_client.messages_create.return_value = (fake_resp, None)

    out = _retry_shorter(fake_client, Platform.X, "sys", "user", cap=100,
                            current_text="z" * 320)
    assert len(out) <= 100
    # Should end at a sentence boundary (period/question/exclamation), not
    # mid-word.
    assert out.endswith(".") or out.endswith("?") or out.endswith("!")


def test_retry_shorter_falls_back_to_word_boundary_when_no_sentence():
    from unittest.mock import MagicMock
    from marketing_agent.content.generator import _retry_shorter

    no_sentence = "alpha beta gamma delta epsilon zeta eta theta iota kappa"
    fake_resp = MagicMock()
    fake_resp.content = [MagicMock(type="text", text=no_sentence)]
    fake_client = MagicMock()
    fake_client.messages_create.return_value = (fake_resp, None)

    out = _retry_shorter(fake_client, Platform.X, "sys", "user", cap=30,
                            current_text="z" * 100)
    assert len(out) <= 30
    # Last char shouldn't be in the middle of a word
    assert not out.endswith(("a", "b", "c", "d", "e")) or out.endswith(
        ("alpha", "beta", "gamma", "delta", "epsilon")
    )


def test_retry_shorter_keeps_original_when_retry_errors_and_under_cap_after_truncate():
    """If the retry call errors out, fall back to mechanical truncate of
    the ORIGINAL text."""
    from unittest.mock import MagicMock
    from marketing_agent.content.generator import _retry_shorter

    fake_client = MagicMock()
    fake_client.messages_create.return_value = (None, RuntimeError("api down"))

    long_orig = "First sentence. " + ("padding word " * 30)
    out = _retry_shorter(fake_client, Platform.X, "sys", "user", cap=80,
                            current_text=long_orig)
    assert len(out) <= 80
