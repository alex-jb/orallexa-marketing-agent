"""Tests for CostTracker."""
from __future__ import annotations

import pytest

from marketing_agent import CostTracker


@pytest.fixture
def tracker(tmp_path):
    return CostTracker(db_path=tmp_path / "cost.db")


def test_log_claude_returns_cost(tracker):
    cost = tracker.log_claude(model="claude-sonnet-4-6",
                                input_tokens=1000, output_tokens=500,
                                project_name="demo")
    # 1000 in @ $3/M = $0.003 + 500 out @ $15/M = $0.0075 = $0.0105
    assert abs(cost - 0.0105) < 1e-6


def test_log_x_post(tracker):
    cost = tracker.log_x_post(project_name="demo")
    assert cost == 0.010


def test_total(tracker):
    tracker.log_claude(model="claude-haiku-4-5", input_tokens=100,
                        output_tokens=100, project_name="demo")
    tracker.log_x_post(project_name="demo")
    tracker.log_x_post(project_name="other")
    total = tracker.total()
    assert total > 0


def test_total_filtered_by_project(tracker):
    tracker.log_x_post(project_name="alpha")
    tracker.log_x_post(project_name="beta")
    tracker.log_x_post(project_name="alpha")
    assert abs(tracker.total(project_name="alpha") - 0.020) < 1e-6
    assert abs(tracker.total(project_name="beta") - 0.010) < 1e-6


def test_by_category(tracker):
    tracker.log_claude(model="claude-haiku-4-5", input_tokens=100,
                        output_tokens=100)
    tracker.log_x_post()
    cats = tracker.by_category()
    assert "llm" in cats
    assert "x_post" in cats
