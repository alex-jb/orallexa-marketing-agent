"""Tests for best_time analyzer."""
from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from marketing_agent.best_time import optimal_post_time, report
from marketing_agent.engagement import EngagementTracker
from marketing_agent.memory import PostMemory
from marketing_agent.types import Engagement, Platform, Post


def _post(text: str, platform: Platform = Platform.X) -> Post:
    return Post(platform=platform, body=text)


@pytest.fixture
def db(tmp_path) -> Path:
    return tmp_path / "history.db"


def test_no_data_returns_industry_default(db):
    wd, h, src = optimal_post_time(Platform.X, db_path=db)
    assert src == "default"
    assert wd == 1 and h == 14  # Tue 14:00 UTC


def test_data_with_clear_winner(db):
    mem = PostMemory(db_path=db)
    eng = EngagementTracker(db_path=db)
    # 5 posts on Tue 10:00 UTC with high engagement, 5 on Sun 03:00 with low
    high_ts = datetime(2026, 4, 28, 10, tzinfo=timezone.utc)  # Tue
    low_ts = datetime(2026, 4, 26, 3, tzinfo=timezone.utc)    # Sun
    for i in range(5):
        p = _post(f"high-{i}")
        mem.record(p, project_name="orallexa", external_id=f"h{i}")
        # overwrite posted_at to deterministic value
        with sqlite3.connect(db) as conn:
            conn.execute("UPDATE post_history SET posted_at=? WHERE external_id=?",
                         (high_ts.isoformat(), f"h{i}"))
        eng.record(Engagement(platform=Platform.X, post_id=f"h{i}",
                                metric="like", count=100, timestamp=high_ts))
    for i in range(5):
        p = _post(f"low-{i}")
        mem.record(p, project_name="orallexa", external_id=f"l{i}")
        with sqlite3.connect(db) as conn:
            conn.execute("UPDATE post_history SET posted_at=? WHERE external_id=?",
                         (low_ts.isoformat(), f"l{i}"))
        eng.record(Engagement(platform=Platform.X, post_id=f"l{i}",
                                metric="like", count=2, timestamp=low_ts))
    wd, h, src = optimal_post_time(Platform.X, db_path=db, min_samples=5)
    assert src == "data"
    assert (wd, h) == (1, 10)  # Tuesday 10am UTC


def test_report_sorts_descending(db):
    mem = PostMemory(db_path=db)
    eng = EngagementTracker(db_path=db)
    for hour, count in [(10, 50), (3, 1), (14, 200)]:
        p = _post(f"p-{hour}")
        ext = f"e{hour}"
        mem.record(p, project_name="orallexa", external_id=ext)
        ts = datetime(2026, 4, 28, hour, tzinfo=timezone.utc)
        with sqlite3.connect(db) as conn:
            conn.execute("UPDATE post_history SET posted_at=? WHERE external_id=?",
                         (ts.isoformat(), ext))
        eng.record(Engagement(platform=Platform.X, post_id=ext,
                                metric="like", count=count, timestamp=ts))
    rows = report(Platform.X, db_path=db)
    assert len(rows) == 3
    assert rows[0]["mean_reward"] == 200
    assert rows[-1]["mean_reward"] == 1


def test_below_min_samples_falls_back_to_default(db):
    mem = PostMemory(db_path=db)
    eng = EngagementTracker(db_path=db)
    p = _post("only-one")
    mem.record(p, project_name="orallexa", external_id="x1")
    eng.record(Engagement(platform=Platform.X, post_id="x1",
                            metric="like", count=99,
                            timestamp=datetime(2026, 4, 28, 10, tzinfo=timezone.utc)))
    _wd, _h, src = optimal_post_time(Platform.X, db_path=db, min_samples=5)
    assert src == "default"
