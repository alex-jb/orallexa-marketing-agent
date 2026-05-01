"""Tests for TrendMemory — per-(project, trend URL) cooldown."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone

import pytest

from marketing_agent.trend_memory import TrendMemory
from marketing_agent.trends import TrendItem


@pytest.fixture
def mem(tmp_path):
    return TrendMemory(db_path=tmp_path / "trend.db")


# ───────────────── core memory ─────────────────


def test_was_drafted_recently_false_when_empty(mem):
    assert mem.was_drafted_recently("https://x.com/foo", "Alpha") is False


def test_mark_then_recently_returns_true(mem):
    mem.mark_drafted("https://x.com/foo", "Alpha")
    assert mem.was_drafted_recently("https://x.com/foo", "Alpha") is True


def test_recently_is_per_project(mem):
    mem.mark_drafted("https://x.com/foo", "Alpha")
    assert mem.was_drafted_recently("https://x.com/foo", "Beta") is False


def test_recently_respects_cooldown_window(mem):
    long_ago = datetime.now(timezone.utc) - timedelta(days=14)
    mem.mark_drafted("https://x.com/foo", "Alpha", now=long_ago)
    # 7-day window: 14 days ago is stale
    assert mem.was_drafted_recently("https://x.com/foo", "Alpha", days=7) is False
    # 30-day window: 14 days ago is fresh
    assert mem.was_drafted_recently("https://x.com/foo", "Alpha", days=30) is True


def test_empty_url_short_circuits(mem):
    assert mem.was_drafted_recently("", "Alpha") is False
    # mark_drafted with empty URL is no-op
    mem.mark_drafted("", "Alpha")


def test_re_marking_refreshes_timestamp(mem):
    long_ago = datetime.now(timezone.utc) - timedelta(days=14)
    mem.mark_drafted("https://x.com/foo", "Alpha", now=long_ago)
    assert mem.was_drafted_recently(
        "https://x.com/foo", "Alpha", days=7) is False
    # Re-mark today
    mem.mark_drafted("https://x.com/foo", "Alpha")
    assert mem.was_drafted_recently(
        "https://x.com/foo", "Alpha", days=7) is True


# ───────────────── filter_fresh ─────────────────


def test_filter_fresh_drops_recently_drafted(mem):
    items = [
        TrendItem(source="hn", title="t1", url="https://news.ycombinator.com/1", score=100),
        TrendItem(source="hn", title="t2", url="https://news.ycombinator.com/2", score=90),
        TrendItem(source="hn", title="t3", url="https://news.ycombinator.com/3", score=80),
    ]
    mem.mark_drafted("https://news.ycombinator.com/2", "Alpha")
    fresh = mem.filter_fresh(items, "Alpha")
    titles = [it.title for it in fresh]
    assert "t1" in titles
    assert "t3" in titles
    assert "t2" not in titles


def test_filter_fresh_is_per_project(mem):
    items = [
        TrendItem(source="hn", title="t1", url="https://news.ycombinator.com/1",
                    score=100),
    ]
    mem.mark_drafted("https://news.ycombinator.com/1", "Alpha")
    # Beta hasn't drafted it yet — should pass through
    assert mem.filter_fresh(items, "Beta") == items


def test_filter_fresh_preserves_order(mem):
    items = [
        TrendItem(source="hn", title=f"t{i}",
                    url=f"https://news.ycombinator.com/{i}", score=100 - i)
        for i in range(5)
    ]
    fresh = mem.filter_fresh(items, "Alpha")
    assert [it.title for it in fresh] == ["t0", "t1", "t2", "t3", "t4"]


def test_filter_fresh_passes_through_items_without_url(mem):
    items = [TrendItem(source="hn", title="t1", url="", score=100)]
    assert mem.filter_fresh(items, "Alpha") == items


# ───────────────── purge ─────────────────


def test_purge_older_than(mem):
    very_old = datetime.now(timezone.utc) - timedelta(days=200)
    recent = datetime.now(timezone.utc) - timedelta(days=5)
    mem.mark_drafted("https://x.com/old", "Alpha", now=very_old)
    mem.mark_drafted("https://x.com/recent", "Alpha", now=recent)
    deleted = mem.purge_older_than(days=90)
    assert deleted == 1
    assert mem.was_drafted_recently("https://x.com/old", "Alpha", days=365) is False
    assert mem.was_drafted_recently("https://x.com/recent", "Alpha", days=10) is True


# ───────────────── mark_many ─────────────────


def test_mark_many_records_all_non_empty(mem):
    n = mem.mark_many(["a", "", "b", "c"], "Alpha")
    assert n == 3
