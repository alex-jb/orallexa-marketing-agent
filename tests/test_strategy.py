"""Tests for strategy / launch plan generator."""
from __future__ import annotations


from marketing_agent import Project
from marketing_agent.strategy import default_plan, LaunchPlan, llm_plan, write_plan


def _project() -> Project:
    return Project(
        name="DemoBot",
        tagline="An AI assistant that does demo things",
        description="Local-first AI agent.",
        tags=["ai-agent", "rust"],
    )


def test_default_plan_returns_valid_pydantic():
    plan = default_plan(_project(), days=30)
    assert isinstance(plan, LaunchPlan)
    assert plan.project_name == "DemoBot"
    assert plan.duration_days == 30
    assert len(plan.actions) >= 8


def test_default_plan_no_action_outside_window():
    plan = default_plan(_project(), days=30)
    for a in plan.actions:
        assert 0 <= a.day < 30


def test_default_plan_to_markdown_renders():
    md = default_plan(_project()).to_markdown()
    assert "# Launch plan" in md
    assert "DemoBot" in md
    assert "## Day 0" in md


def test_llm_plan_falls_back_when_no_anthropic_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    plan = llm_plan(_project(), days=30)
    assert isinstance(plan, LaunchPlan)
    assert plan.project_name == "DemoBot"


def test_write_plan_creates_file(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = write_plan(_project(), out_dir=str(tmp_path), use_llm=False)
    from pathlib import Path
    assert Path(out).exists()
    assert "DemoBot" in Path(out).read_text()


def test_ph_launch_day_shifts_hn_action():
    """When PH launches on day 14, HN should be at day 14+10=24 (not 10)."""
    plan = default_plan(_project(), days=30, ph_launch_day=14)
    hn_actions = [a for a in plan.actions if a.platform.value == "hacker_news"]
    assert len(hn_actions) == 1
    assert hn_actions[0].day == 24  # 14 + 10
    assert plan.ph_launch_day == 14


def test_ph_launch_day_adds_pre_ph_teaser_posts():
    """ph_launch_day > 0 should add pre-PH teaser actions."""
    plan = default_plan(_project(), days=30, ph_launch_day=14)
    pre_ph = [a for a in plan.actions if a.day < 14]
    assert len(pre_ph) >= 2  # 1-week and 1-day-before teasers


def test_60_day_plan_includes_long_tail_actions():
    plan = default_plan(_project(), days=60)
    assert plan.duration_days == 60
    # Long-tail starts ~day 35
    long_tail = [a for a in plan.actions if a.day >= 30]
    assert len(long_tail) >= 3


def test_90_day_plan_includes_quarterly_actions():
    plan = default_plan(_project(), days=90)
    assert plan.duration_days == 90
    quarterly = [a for a in plan.actions if a.day >= 60]
    assert len(quarterly) >= 2


def test_markdown_includes_ph_relative_labels_when_ph_set():
    plan = default_plan(_project(), days=30, ph_launch_day=7)
    md = plan.to_markdown()
    assert "PH anchor day 7" in md
    # Day 7 should show as "Day 7 / PH+0"
    assert "PH+0" in md or "PH-0" in md
    # Day 0 (a teaser) should show as "Day 0 / PH-7"
    assert "PH-7" in md
