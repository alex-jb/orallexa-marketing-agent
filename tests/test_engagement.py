"""Tests for EngagementTracker."""
from __future__ import annotations
from datetime import datetime, timezone

import pytest

from marketing_agent import Platform
from marketing_agent.engagement import EngagementTracker
from marketing_agent.types import Engagement


@pytest.fixture
def tracker(tmp_path):
    return EngagementTracker(db_path=tmp_path / "eng.db")


def test_record_and_total(tracker):
    tracker.record(Engagement(platform=Platform.X, post_id="abc",
                                metric="like", count=5))
    tracker.record(Engagement(platform=Platform.X, post_id="abc",
                                metric="reply", count=2))
    totals = tracker.total_engagement()
    assert totals.get("like") == 5
    assert totals.get("reply") == 2


def test_top_posts_by_metric(tracker):
    for i, count in enumerate([5, 50, 500]):
        tracker.record(Engagement(platform=Platform.X, post_id=f"p{i}",
                                    metric="like", count=count,
                                    timestamp=datetime(2026, 4, 28 - i,
                                                        tzinfo=timezone.utc)))
    top = tracker.top_posts(metric="like", limit=2)
    assert len(top) == 2
    assert top[0]["peak"] == 500
    assert top[1]["peak"] == 50
