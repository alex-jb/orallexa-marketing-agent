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


# ───────────────── JSONL sink for sfos-evolver ─────────────────


def test_record_writes_jsonl_with_evolver_schema(tmp_path):
    import json
    jpath = tmp_path / "reflections.jsonl"
    m = ReflexionMemory(db_path=tmp_path / "r.db", jsonl_path=jpath)
    m.record(project_name="orallexa", platform=Platform.X,
              score=3.0, reasons=["hype words: revolutionary"],
              body_preview="Revolutionary launch!")
    lines = jpath.read_text().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    # SFOS evolver requires these exact keys
    for k in ("ts", "agent", "task", "outcome", "verbatim_signal"):
        assert k in row
    assert row["agent"] == "marketing-agent"
    assert row["outcome"] == "FAILED"  # score 3.0 < 4.0
    assert "revolutionary" in row["verbatim_signal"]


def test_jsonl_outcome_thresholds(tmp_path):
    import json
    jpath = tmp_path / "reflections.jsonl"
    m = ReflexionMemory(db_path=tmp_path / "r.db", jsonl_path=jpath)
    m.record(project_name="p", platform=Platform.X, score=2.0,
              reasons=["bad"], body_preview="")
    m.record(project_name="p", platform=Platform.X, score=5.5,
              reasons=["meh"], body_preview="")
    m.record(project_name="p", platform=Platform.X, score=8.5,
              reasons=["good"], body_preview="")
    rows = [json.loads(line) for line in jpath.read_text().splitlines()]
    assert rows[0]["outcome"] == "FAILED"   # < 4
    assert rows[1]["outcome"] == "PARTIAL"  # 4 ≤ < 7
    assert rows[2]["outcome"] == "SUCCESS"  # ≥ 7


def test_jsonl_path_overridable_via_env(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKETING_AGENT_REFLECTIONS_JSONL",
                          str(tmp_path / "custom.jsonl"))
    m = ReflexionMemory(db_path=tmp_path / "r.db")
    m.record(project_name="p", platform=Platform.X, score=3.0,
              reasons=["x"], body_preview="")
    assert (tmp_path / "custom.jsonl").exists()


def test_jsonl_creates_parent_dir(tmp_path):
    nested = tmp_path / "nested" / "deeper" / "reflections.jsonl"
    m = ReflexionMemory(db_path=tmp_path / "r.db", jsonl_path=nested)
    m.record(project_name="p", platform=Platform.X, score=3.0,
              reasons=["x"], body_preview="")
    assert nested.exists()


def test_jsonl_disabled_when_globally_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKETING_AGENT_NO_REFLEXION", "1")
    jpath = tmp_path / "reflections.jsonl"
    m = ReflexionMemory(db_path=tmp_path / "r.db", jsonl_path=jpath)
    m.record(project_name="p", platform=Platform.X, score=3.0,
              reasons=["x"], body_preview="")
    assert not jpath.exists()


def test_export_jsonl_backfills_historical_rows(tmp_path):
    import json
    db = tmp_path / "r.db"
    # Phase 1: write to SQLite without jsonl_path (mimics pre-sink data)
    m1 = ReflexionMemory(db_path=db, jsonl_path=tmp_path / "throwaway.jsonl")
    m1.record(project_name="p", platform=Platform.X, score=3.0,
                reasons=["bad"], body_preview="")
    m1.record(project_name="p", platform=Platform.REDDIT, score=5.5,
                reasons=["meh"], body_preview="")
    # Phase 2: backfill into a fresh JSONL
    target = tmp_path / "fresh.jsonl"
    m2 = ReflexionMemory(db_path=db, jsonl_path=target)
    n = m2.export_jsonl()
    # m2's __init__ doesn't auto-export, so target started empty.
    # export_jsonl emits both SQLite rows.
    assert n == 2
    rows = [json.loads(line) for line in target.read_text().splitlines()]
    assert {r["platform"] for r in rows} == {"x", "reddit"}
