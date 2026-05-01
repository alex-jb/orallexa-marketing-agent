"""Tests for the Drafter → Critic → Rewriter supervisor loop."""
from __future__ import annotations


from marketing_agent.critic import CritiqueResult
from marketing_agent.supervisor import (
    SupervisorResult, heuristic_rewrite, supervise,
)
from marketing_agent.types import GenerationMode, Platform, Post, Project


def _project() -> Project:
    return Project(name="Orallexa", tagline="Multi-agent AI trading system",
                   github_url="https://github.com/x/y",
                   recent_changes=["v0.6 ships supervisor + multi-project + Docker"])


def test_heuristic_rewrite_strips_hype():
    p = Post(platform=Platform.X,
             body="Revolutionary game-changing cutting-edge AI to "
                  "supercharge your dev workflow today!").with_count()
    crit = CritiqueResult(score=2.0, reasons=[
        "hype words: revolutionary, game-changing, cutting-edge"
    ])
    out = heuristic_rewrite(p, crit)
    body_lower = out.body.lower()
    for word in ("revolutionary", "game-changing", "cutting-edge", "supercharge"):
        assert word not in body_lower, f"hype word '{word}' survived rewrite"


def test_heuristic_rewrite_trims_caps():
    p = Post(platform=Platform.X,
             body="THIS IS A VERY LOUD ANNOUNCEMENT EVERYONE LOOK").with_count()
    crit = CritiqueResult(score=3.0, reasons=["excessive caps"])
    out = heuristic_rewrite(p, crit)
    # After de-shout, fewer than 40% of letters should be uppercase
    letters = [c for c in out.body if c.isalpha()]
    upper = sum(1 for c in letters if c.isupper())
    assert upper / len(letters) < 0.4


def test_heuristic_rewrite_caps_hashtags():
    p = Post(platform=Platform.X,
             body="Cool thing #ai #ml #python #startup #dev #buildinpublic").with_count()
    crit = CritiqueResult(score=4.0, reasons=["hashtag spam (6)"])
    out = heuristic_rewrite(p, crit)
    hashtag_count = out.body.count("#")
    assert hashtag_count <= 3


def test_heuristic_rewrite_trims_overshoot():
    body = "x" * 400
    p = Post(platform=Platform.X, body=body).with_count()
    crit = CritiqueResult(score=2.0, reasons=["over x limit by 120 chars"])
    out = heuristic_rewrite(p, crit)
    assert len(out.body) <= 280


def test_supervise_returns_best_of_n(monkeypatch):
    """In template mode, supervisor cycles X variants and returns highest score."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = supervise(_project(), Platform.X,
                          mode=GenerationMode.TEMPLATE,
                          max_iterations=3, min_score=11.0,  # impossible → forces all iterations
                          use_llm_critic=False)
    assert isinstance(result, SupervisorResult)
    # At least max_iterations drafts were tried (rewrites may add more)
    assert result.iterations >= 3
    # best score is monotonic max over history
    history_scores = [c.score for _p, c in result.history]
    assert result.critique.score == max(history_scores)


def test_supervise_early_exits_on_high_score(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # min_score lowered to 0 → first iteration always wins
    result = supervise(_project(), Platform.X,
                          mode=GenerationMode.TEMPLATE,
                          max_iterations=5, min_score=0.0,
                          use_llm_critic=False)
    assert result.iterations == 1


def test_supervise_falls_back_to_template_without_llm(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = supervise(_project(), Platform.X,
                          mode=GenerationMode.HYBRID,
                          max_iterations=2, use_llm_critic=False)
    # Just confirm it doesn't crash and returns a valid post
    assert result.post.platform == Platform.X
    assert len(result.post.body) > 0


def test_self_consistency_returns_valid_post_for_short_form(monkeypatch):
    """use_self_consistency=True on X should still return a valid post —
    the template-mode samples vary but the picker logic must not crash."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = supervise(_project(), Platform.X,
                          mode=GenerationMode.TEMPLATE,
                          max_iterations=1, min_score=0.0,
                          use_llm_critic=False,
                          use_self_consistency=True)
    assert result.post.platform == Platform.X
    assert len(result.post.body) > 0
    # variant_key should be one of the X variants
    assert result.post.variant_key in (
        "x:emoji-led", "x:question-led", "x:stat-led",
    )


def test_self_consistency_off_for_long_form_platforms(monkeypatch):
    """Reddit / LinkedIn / Dev.to don't trigger self-consistency even when
    the flag is on (template mode has no variants for them)."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = supervise(_project(), Platform.LINKEDIN,
                          mode=GenerationMode.TEMPLATE,
                          max_iterations=1, min_score=0.0,
                          use_llm_critic=False,
                          use_self_consistency=True)
    assert result.post.platform == Platform.LINKEDIN
    assert len(result.post.body) > 0
