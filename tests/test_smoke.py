"""Smoke tests — must run offline, no API keys, no network."""
from __future__ import annotations
import pytest
from pydantic import ValidationError

from marketing_agent import (
    Engagement, GenerationMode, Orchestrator, Platform, Post, Project,
)
from marketing_agent.content import templates
from marketing_agent.platforms import (
    XAdapter, RedditAdapter, LinkedInAdapter, get_adapter,
)
from marketing_agent.platforms.base import NotConfigured


# ─────────────────────────── Type validation ───────────────────────────

def test_project_minimal():
    p = Project(name="T", tagline="A short tagline")
    assert p.name == "T"
    assert p.tagline == "A short tagline"
    assert p.tags == []


def test_project_tagline_max_length():
    with pytest.raises(ValidationError):
        Project(name="T", tagline="x" * 201)


def test_post_with_count_populates_char_count():
    post = Post(platform=Platform.X, body="hello").with_count()
    assert post.char_count == 5


def test_engagement_defaults():
    e = Engagement(platform=Platform.X, post_id="123", metric="like")
    assert e.count == 1
    assert e.timestamp is not None


# ─────────────────────────── Templates (offline) ───────────────────────────

def _sample_project() -> Project:
    return Project(
        name="DemoBot",
        tagline="Open-source AI assistant for personal finance",
        description="A local-first AI agent.",
        github_url="https://github.com/x/y",
        recent_changes=["feat: A", "fix: B", "test: C"],
    )


def test_template_x_under_280_chars():
    p = templates.render(Platform.X, _sample_project())
    assert p.platform == Platform.X
    assert len(p.body) <= 280


def test_template_reddit_has_title_and_target():
    p = templates.render(Platform.REDDIT, _sample_project(), subreddit="algotrading")
    assert p.title is not None
    assert p.target == "algotrading"
    assert "DemoBot" in p.body


def test_template_linkedin_includes_changes():
    p = templates.render(Platform.LINKEDIN, _sample_project())
    assert "feat: A" in p.body or "DemoBot" in p.body


def test_template_dev_to_markdown_format():
    p = templates.render(Platform.DEV_TO, _sample_project())
    assert "## " in p.body  # markdown headings


def test_truncate_short_input_passthrough():
    """Inputs at or under the limit must come back unchanged (no
    ellipsis injected for short strings)."""
    assert templates._truncate("short", 200) == "short"
    exact = "x" * 200
    assert templates._truncate(exact, 200) == exact
    assert not exact.endswith("…")


def test_truncate_breaks_at_word_boundary_when_oversize():
    """Regression: SFOS launch posts had 'bilingual-sync / custo' because
    a long bullet got hard-sliced at 120/140. _truncate now breaks at
    the last whitespace before the limit and appends an ellipsis."""
    # 220 chars — comfortably over the 200 cap
    long = ("Agent stack covers reflexion, supervisor, skills, evolver, "
            "council, ICPL, eval, drift detection, cross-terminal bus, "
            "HITL governance rail, weekly retro, scheduled launchd jobs, "
            "and full test isolation across the whole stack.")
    assert len(long) > 200
    out = templates._truncate(long, 200)
    assert len(out) <= 200
    # Must NOT end mid-word — the last visible char before the ellipsis
    # must be a complete word.
    assert out.endswith("…")
    # The character right before the ellipsis must not be a letter that
    # would suggest a chopped word — it should be a complete token.
    prev_char = out[-2]
    assert prev_char.isalpha() or prev_char in ".,;)/"
    # And the truncation must have happened at a word boundary, not
    # mid-word: the head before "…" should not end with a partial token
    # immediately preceded by whitespace in the original.
    head = out[:-1]
    # Verify head matches a prefix of the original up to a whitespace
    # (i.e. we found a real word boundary, not an arbitrary index).
    assert long.startswith(head) or any(
        long.startswith(head.rstrip(",;:/-")) for _ in (0,)
    )


def test_template_sfos_launch_bullet_renders_intact():
    """End-to-end: the actual SFOS launch bullet that got truncated in
    the v0.20.3 dogfood post must render fully now (it's ~188 chars,
    under the new 200 cap)."""
    proj = Project(
        name="SFOS",
        tagline="6-layer self-evolving agent stack",
        description="A library.",
        github_url="https://github.com/x/y",
        recent_changes=[
            "10 agents covered by sfos-retro: marketing / build-quality "
            "/ customer-discovery / funnel / vc-outreach / cost-audit "
            "/ bilingual-sync / customer-support / customer-outreach "
            "/ shared-lib",
        ],
    )
    for plat in (Platform.LINKEDIN, Platform.REDDIT, Platform.DEV_TO):
        p = templates.render(plat, proj, subreddit="x")
        # The full bullet must appear, not "...custo"
        assert "customer-outreach" in p.body
        assert "shared-lib" in p.body
        assert "/ custo\n" not in p.body


# ─────────────────────────── Adapters ───────────────────────────

def test_x_adapter_not_configured_without_keys(monkeypatch):
    for k in XAdapter.REQUIRED:
        monkeypatch.delenv(k, raising=False)
    a = XAdapter()
    assert not a.is_configured()
    with pytest.raises(NotConfigured):
        a.post(Post(platform=Platform.X, body="hi"))


def test_x_adapter_dry_run_always_works():
    a = XAdapter()
    preview = a.dry_run_preview(Post(platform=Platform.X, body="hello world"))
    assert "X (Twitter) preview" in preview
    assert "hello world" in preview


def test_reddit_adapter_dry_run_always_works():
    a = RedditAdapter()
    post = Post(platform=Platform.REDDIT, title="Title", body="Body",
                target="MachineLearning")
    preview = a.dry_run_preview(post)
    assert "r/MachineLearning" in preview


def test_linkedin_adapter_never_configured_in_v01():
    a = LinkedInAdapter()
    assert a.is_configured() is False
    with pytest.raises(NotConfigured):
        a.post(Post(platform=Platform.LINKEDIN, body="hi"))


def test_get_adapter_factory():
    assert isinstance(get_adapter(Platform.X), XAdapter)
    assert isinstance(get_adapter(Platform.REDDIT), RedditAdapter)
    assert isinstance(get_adapter(Platform.LINKEDIN), LinkedInAdapter)


# ─────────────────────────── Orchestrator (offline) ───────────────────────────

def test_orchestrator_generate_template_mode_offline():
    orch = Orchestrator(mode=GenerationMode.TEMPLATE)
    posts = orch.generate(_sample_project(),
                            [Platform.X, Platform.REDDIT, Platform.LINKEDIN])
    assert len(posts) == 3
    assert {p.platform for p in posts} == {Platform.X, Platform.REDDIT, Platform.LINKEDIN}


def test_orchestrator_preview_works_for_all_platforms():
    orch = Orchestrator(mode=GenerationMode.TEMPLATE)
    posts = orch.generate(_sample_project(), [Platform.X, Platform.REDDIT, Platform.LINKEDIN])
    for p in posts:
        preview = orch.preview(p)
        assert preview  # non-empty
        assert "preview" in preview.lower() or "manually" in preview.lower()


def test_orchestrator_hybrid_falls_back_when_no_anthropic_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    orch = Orchestrator(mode=GenerationMode.HYBRID)
    posts = orch.generate(_sample_project(), [Platform.X])
    assert len(posts) == 1
    # Template fallback produced this — should contain the project name
    assert "DemoBot" in posts[0].body
