"""Tests for strategy / launch plan generator."""
from __future__ import annotations
import os

import pytest

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
