"""Tests for v0.20.0 `generate_variants()` — JEPA-flavored multi-pick.

Where `generate_posts(project, [X, R, L])` returns 3 posts (one per platform),
`generate_variants(project, X, n=2)` returns 2 posts FOR THE SAME PLATFORM,
ranked by bandit-predicted engagement, each tagged with `predicted_mean` +
`predicted_n_pulls` for HITL display.
"""
from __future__ import annotations
from unittest.mock import patch

import pytest

from marketing_agent.content import generate_variants
from marketing_agent.content.generator import _sort_by_prediction
from marketing_agent.types import Platform, Post, Project


@pytest.fixture
def project():
    return Project(
        name="VibeXForge",
        tagline="Distribution amplifier for solo AI creators",
        github_url="https://github.com/alex-jb/vibex",
    )


# ─────────────────────────────────────────────────────────────────────
# happy path: pool has 3 variants, n=2 returns 2 ranked variants
# ─────────────────────────────────────────────────────────────────────


def test_generate_variants_returns_n_posts(project, monkeypatch, tmp_path):
    """When n=2 on a platform with a 3-variant pool, return 2 posts."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    bandit_db = tmp_path / "bandit.db"
    monkeypatch.setattr("marketing_agent.bandit._default_db_path",
                          lambda: bandit_db)

    fake_post = Post(platform=Platform.X, body="generated body",
                       variant_key="x:emoji-led")
    with patch(
        "marketing_agent.content.generator._generate_with_llm",
        return_value=fake_post,
    ) as mock_llm:
        out = generate_variants(project, Platform.X, n=2)
    assert len(out) == 2
    assert mock_llm.call_count == 2
    assert all(p.platform == Platform.X for p in out)


def test_generate_variants_sorted_by_predicted_mean_desc(project, monkeypatch,
                                                              tmp_path):
    """Returned posts must be sorted by predicted_mean descending."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    bandit_db = tmp_path / "bandit.db"
    monkeypatch.setattr("marketing_agent.bandit._default_db_path",
                          lambda: bandit_db)

    # Train bandit so x:stat-led >> x:emoji-led >> x:question-led.
    from marketing_agent.bandit import VariantBandit
    b = VariantBandit()
    for _ in range(5):
        b.update("x:stat-led", reward=0.9)
    for _ in range(5):
        b.update("x:emoji-led", reward=0.5)
    for _ in range(5):
        b.update("x:question-led", reward=0.1)

    fake_post = Post(platform=Platform.X, body="x", variant_key="placeholder")
    with patch(
        "marketing_agent.content.generator._generate_with_llm",
        return_value=fake_post,
    ):
        out = generate_variants(project, Platform.X, n=3)
    assert [p.variant_key for p in out] == [
        "x:stat-led", "x:emoji-led", "x:question-led",
    ]
    means = [p.predicted_mean for p in out]
    assert means[0] > means[1] > means[2]


def test_generate_variants_attaches_n_pulls(project, monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    bandit_db = tmp_path / "bandit.db"
    monkeypatch.setattr("marketing_agent.bandit._default_db_path",
                          lambda: bandit_db)

    from marketing_agent.bandit import VariantBandit
    b = VariantBandit()
    for _ in range(7):
        b.update("x:stat-led", reward=0.7)
    b.update("x:emoji-led", reward=0.5)

    fake_post = Post(platform=Platform.X, body="x",
                       variant_key="placeholder")
    with patch(
        "marketing_agent.content.generator._generate_with_llm",
        return_value=fake_post,
    ):
        out = generate_variants(project, Platform.X, n=2)
    by_key = {p.variant_key: p for p in out}
    assert by_key["x:stat-led"].predicted_n_pulls == 7
    assert by_key["x:emoji-led"].predicted_n_pulls == 1


# ─────────────────────────────────────────────────────────────────────
# degenerate paths
# ─────────────────────────────────────────────────────────────────────


def test_generate_variants_n_one_falls_through_to_single(project,
                                                              monkeypatch,
                                                              tmp_path):
    """n=1 should not invoke the multi-variant path; just a single post."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    bandit_db = tmp_path / "bandit.db"
    monkeypatch.setattr("marketing_agent.bandit._default_db_path",
                          lambda: bandit_db)
    fake_post = Post(platform=Platform.X, body="x", variant_key="x:emoji-led")
    with patch(
        "marketing_agent.content.generator._generate_with_llm",
        return_value=fake_post,
    ):
        out = generate_variants(project, Platform.X, n=1)
    assert len(out) == 1


def test_generate_variants_unsupported_platform_returns_one(project,
                                                                monkeypatch,
                                                                tmp_path):
    """LinkedIn has no LLM variant pool. Even with n=3, return one post."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    bandit_db = tmp_path / "bandit.db"
    monkeypatch.setattr("marketing_agent.bandit._default_db_path",
                          lambda: bandit_db)
    fake_post = Post(platform=Platform.LINKEDIN, body="x")
    with patch(
        "marketing_agent.content.generator._generate_with_llm",
        return_value=fake_post,
    ):
        out = generate_variants(project, Platform.LINKEDIN, n=3)
    assert len(out) == 1
    assert out[0].platform == Platform.LINKEDIN


def test_generate_variants_n_capped_at_pool_size(project, monkeypatch,
                                                       tmp_path):
    """When n exceeds pool size, cap at pool size (don't invent variants)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    bandit_db = tmp_path / "bandit.db"
    monkeypatch.setattr("marketing_agent.bandit._default_db_path",
                          lambda: bandit_db)
    fake_post = Post(platform=Platform.X, body="x",
                       variant_key="placeholder")
    with patch(
        "marketing_agent.content.generator._generate_with_llm",
        return_value=fake_post,
    ) as mock_llm:
        out = generate_variants(project, Platform.X, n=10)
    # Pool size is 3, so 3 LLM calls + 3 posts max.
    assert len(out) == 3
    assert mock_llm.call_count == 3


# ─────────────────────────────────────────────────────────────────────
# template fallback
# ─────────────────────────────────────────────────────────────────────


def test_generate_variants_template_path_when_no_api_key(project,
                                                              monkeypatch,
                                                              tmp_path):
    """No ANTHROPIC_API_KEY: skip LLM, use template variants, still tag."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    bandit_db = tmp_path / "bandit.db"
    monkeypatch.setattr("marketing_agent.bandit._default_db_path",
                          lambda: bandit_db)
    out = generate_variants(project, Platform.X, n=2)
    assert len(out) == 2
    # Template variants should have variant_key set (templates handle this)
    assert all(p.platform == Platform.X for p in out)


# ─────────────────────────────────────────────────────────────────────
# _sort_by_prediction unit
# ─────────────────────────────────────────────────────────────────────


def test_sort_by_prediction_handles_none(project):
    """Posts with no predicted_mean should sort as 0.5 (uniform prior)."""
    posts = [
        Post(platform=Platform.X, body="a", predicted_mean=0.8,
             predicted_n_pulls=10),
        Post(platform=Platform.X, body="b"),  # no prediction
        Post(platform=Platform.X, body="c", predicted_mean=0.3,
             predicted_n_pulls=2),
    ]
    out = _sort_by_prediction(posts)
    assert out[0].body == "a"   # 0.8
    assert out[1].body == "b"   # 0.5 (default)
    assert out[2].body == "c"   # 0.3


def test_sort_by_prediction_ties_break_on_lower_pulls(project):
    """When predicted_means tie, lower n_pulls (less explored) ranks higher
    — promotes exploration over redundant exploitation."""
    posts = [
        Post(platform=Platform.X, body="explored", predicted_mean=0.6,
             predicted_n_pulls=20),
        Post(platform=Platform.X, body="fresh", predicted_mean=0.6,
             predicted_n_pulls=2),
    ]
    out = _sort_by_prediction(posts)
    assert out[0].body == "fresh"
    assert out[1].body == "explored"
