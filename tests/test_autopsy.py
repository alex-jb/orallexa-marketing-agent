"""Tests for failure post-mortem analyzer."""
from __future__ import annotations
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from marketing_agent.autopsy import (
    _engagement_for_post, _fetch_post_by_external_id, _platform_baseline,
    autopsy, render_markdown,
)
from marketing_agent.engagement import EngagementTracker
from marketing_agent.memory import PostMemory
from marketing_agent.types import Engagement, Platform, Post


def _seed(db: Path, *, ext_id: str, body: str, peak_likes: int,
            posted_at: datetime, platform: Platform = Platform.X) -> None:
    mem = PostMemory(db_path=db)
    p = Post(platform=platform, body=body).with_count()
    mem.record(p, project_name="t", external_id=ext_id)
    # Overwrite posted_at deterministically
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE post_history SET posted_at=? WHERE external_id=?",
                       (posted_at.isoformat(), ext_id))
    eng = EngagementTracker(db_path=db)
    eng.record(Engagement(
        platform=platform, post_id=ext_id,
        metric="like", count=peak_likes,
        timestamp=posted_at,
    ))


# ──────────────── helpers ────────────────


def test_fetch_post_returns_none_when_db_missing(tmp_path):
    assert _fetch_post_by_external_id("x", db_path=tmp_path / "nope.db") is None


def test_engagement_for_post_zero_when_db_missing(tmp_path):
    assert _engagement_for_post("x", db_path=tmp_path / "nope.db") == 0


def test_platform_baseline_empty_when_db_missing(tmp_path):
    out = _platform_baseline("x", db_path=tmp_path / "nope.db")
    assert out["n"] == 0
    assert out["median"] == 0.0


# ──────────────── autopsy() — main flow ────────────────


def test_autopsy_returns_helpful_diag_when_post_not_found(tmp_path):
    out = autopsy("nonexistent-id", db_path=tmp_path / "h.db")
    assert out["post"] is None
    assert any("not found" in d for d in out["diagnoses"])


def test_autopsy_finds_underperformance_vs_peers(tmp_path):
    db = tmp_path / "h.db"
    base_time = datetime(2026, 4, 28, 14, 0, tzinfo=timezone.utc)
    # 5 peer posts at 100 likes each
    for i in range(5):
        _seed(db, ext_id=f"peer{i}", body=f"peer post {i}",
                peak_likes=100, posted_at=base_time - timedelta(hours=i))
    # The dud — 5 likes
    _seed(db, ext_id="dud", body="dud post",
            peak_likes=5, posted_at=base_time + timedelta(hours=1))

    out = autopsy("dud", db_path=db, metric="like")
    assert out["post"] is not None
    assert out["engagement"] == 5
    assert out["baseline"]["n"] >= 5
    assert out["underperformance"] > 0.5
    # Should diagnose the underperformance
    assert any("below" in d.lower() for d in out["diagnoses"])
    # Should recommend bandit report
    assert any("bandit report" in r for r in out["recommendations"])


def test_autopsy_flags_hype_words_in_body(tmp_path):
    db = tmp_path / "h.db"
    _seed(db, ext_id="hype",
            body="Revolutionary game-changing AI to supercharge your workflow",
            peak_likes=10,
            posted_at=datetime(2026, 4, 28, 14, 0, tzinfo=timezone.utc))
    out = autopsy("hype", db_path=db)
    # Critic should flag
    assert out["critic"]["score"] < 5
    assert any("hype" in r.lower() for r in out["critic"]["reasons"])
    # Diagnoses should reference the structural issue
    assert any("structural" in d.lower() or "critic" in d.lower()
                for d in out["diagnoses"])


def test_autopsy_includes_short_body_diagnosis(tmp_path):
    db = tmp_path / "h.db"
    _seed(db, ext_id="short", body="too short",
            peak_likes=10,
            posted_at=datetime(2026, 4, 28, 14, 0, tzinfo=timezone.utc))
    out = autopsy("short", db_path=db)
    assert any("short" in d.lower() for d in out["diagnoses"])


# ──────────────── render_markdown ────────────────


def test_render_markdown_handles_missing_post(tmp_path):
    out = autopsy("missing", db_path=tmp_path / "h.db")
    md = render_markdown(out)
    assert "Post not found" in md


def test_render_markdown_full_report(tmp_path):
    db = tmp_path / "h.db"
    base = datetime(2026, 4, 28, 14, 0, tzinfo=timezone.utc)
    for i in range(5):
        _seed(db, ext_id=f"peer{i}", body=f"peer {i}", peak_likes=100,
                posted_at=base - timedelta(hours=i + 1))
    _seed(db, ext_id="target", body="🛠 Project X — solid build-in-public update",
            peak_likes=8, posted_at=base)
    out = autopsy("target", db_path=db)
    md = render_markdown(out)
    assert "Post-mortem" in md
    assert "target" in md
    assert "Diagnoses" in md
    assert "Recommendations" in md
