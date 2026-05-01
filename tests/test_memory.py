"""Tests for PostMemory dedup."""
from __future__ import annotations

import pytest

from marketing_agent import Platform, Post, PostMemory


@pytest.fixture
def mem(tmp_path):
    db = tmp_path / "history.db"
    return PostMemory(db_path=db)


def _post(platform: Platform = Platform.X, body: str = "hello") -> Post:
    return Post(platform=platform, body=body).with_count()


def test_has_posted_false_for_new(mem):
    assert mem.has_posted(_post()) is False


def test_record_and_dedupes(mem):
    p = _post(body="hello world")
    mem.record(p, project_name="demo", external_id="x_123")
    assert mem.has_posted(p) is True


def test_dedup_respects_platform(mem):
    body = "exactly the same body"
    p1 = _post(Platform.X, body=body)
    p2 = _post(Platform.LINKEDIN, body=body)
    mem.record(p1, project_name="demo")
    assert mem.has_posted(p1) is True
    assert mem.has_posted(p2) is False


def test_recent_filter_by_project(mem):
    mem.record(_post(body="A"), project_name="alpha")
    mem.record(_post(body="B"), project_name="beta")
    rows = mem.recent(project_name="alpha", limit=10)
    assert len(rows) == 1
    assert rows[0]["project_name"] == "alpha"


def test_stats(mem):
    mem.record(_post(Platform.X, body="X1"), project_name="a")
    mem.record(_post(Platform.X, body="X2"), project_name="a")
    mem.record(_post(Platform.LINKEDIN, body="L1"), project_name="a")
    stats = mem.stats()
    assert stats == {"x": 2, "linkedin": 1}
