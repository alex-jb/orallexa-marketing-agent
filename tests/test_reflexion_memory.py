"""Tests for ReflexionMemory."""
from __future__ import annotations

import pytest

from marketing_agent.reflexion_memory import ReflexionMemory
from marketing_agent.types import Platform


@pytest.fixture
def mem(tmp_path):
    return ReflexionMemory(db_path=tmp_path / "reflect.db")


def test_record_and_recent(mem):
    rid = mem.record(project_name="orallexa", platform=Platform.X,
                       score=2.5, reasons=["hype words: revolutionary"],
                       body_preview="Revolutionary thing here")
    assert rid > 0
    rows = mem.recent_low_score(project_name="orallexa", platform=Platform.X)
    assert len(rows) == 1
    assert rows[0]["score"] == 2.5
    assert "revolutionary" in rows[0]["reasons"][0]


def test_recent_filters_by_max_score(mem):
    mem.record(project_name="p", platform=Platform.X, score=2.0,
                 reasons=["bad"], body_preview="x")
    mem.record(project_name="p", platform=Platform.X, score=8.0,
                 reasons=["fine"], body_preview="y")
    low = mem.recent_low_score(project_name="p", platform=Platform.X,
                                  max_score=6.0)
    assert len(low) == 1
    assert low[0]["score"] == 2.0


def test_steering_hint_returns_empty_when_no_history(mem):
    assert mem.steering_hint(project_name="never-used",
                                platform=Platform.X) == ""


def test_steering_hint_includes_recent_low_scores(mem):
    mem.record(project_name="p", platform=Platform.X, score=2.0,
                 reasons=["hype words"], body_preview="x")
    mem.record(project_name="p", platform=Platform.X, score=3.0,
                 reasons=["all caps"], body_preview="y")
    hint = mem.steering_hint(project_name="p", platform=Platform.X)
    assert "patterns to avoid" in hint.lower()
    assert "hype" in hint.lower()


def test_disabled_when_env_set(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKETING_AGENT_NO_REFLEXION", "1")
    m = ReflexionMemory(db_path=tmp_path / "r.db")
    assert m.record(project_name="p", platform=Platform.X, score=1.0,
                       reasons=["x"]) == 0
    assert m.recent_low_score(project_name="p", platform=Platform.X) == []
    assert m.steering_hint(project_name="p", platform=Platform.X) == ""


def test_stats_aggregates(mem):
    mem.record(project_name="p", platform=Platform.X, score=4.0,
                 reasons=["x"], body_preview="a")
    mem.record(project_name="p", platform=Platform.REDDIT, score=8.0,
                 reasons=["y"], body_preview="b")
    s = mem.stats()
    assert s["total"] == 2
    assert s["avg_score"] == 6.0
    assert s["by_platform"] == {"x": 1, "reddit": 1}
