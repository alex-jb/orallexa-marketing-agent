"""Tests for scheduled posting (schedule.py)."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from marketing_agent.schedule import (
    filter_due, get_scheduled_for, is_due, next_occurrence_of_hour,
    parse_iso, schedule_via_best_time, set_scheduled_for,
)
from marketing_agent.types import Platform


# ──────────────── parse_iso ────────────────


def test_parse_iso_z_suffix():
    dt = parse_iso("2026-05-04T13:00:00Z")
    assert dt.tzinfo is not None
    assert dt.year == 2026 and dt.month == 5 and dt.day == 4
    assert dt.hour == 13


def test_parse_iso_offset():
    dt = parse_iso("2026-05-04T09:00:00-04:00")
    # 09:00 EDT = 13:00 UTC
    assert dt.hour == 13


def test_parse_iso_naive_assumes_utc():
    dt = parse_iso("2026-05-04T13:00:00")
    assert dt.tzinfo is not None
    assert dt.hour == 13


# ──────────────── set / get scheduled_for ────────────────


def _write_queue_file(tmp_path: Path, body: str = "test body") -> Path:
    """Create a minimal queue file with valid frontmatter."""
    p = tmp_path / "20260504T130000Z-test-x.md"
    p.write_text(
        "---\n"
        "platform: x\n"
        "project: test\n"
        "generated_by: human\n"
        "char_count: 9\n"
        "---\n"
        f"{body}\n"
    )
    return p


def test_set_scheduled_for_inserts_field(tmp_path):
    p = _write_queue_file(tmp_path)
    when = datetime(2026, 5, 4, 13, 0, tzinfo=timezone.utc)
    set_scheduled_for(p, when)
    text = p.read_text()
    assert "scheduled_for: 2026-05-04T13:00:00+00:00" in text
    assert "test body" in text  # body preserved


def test_set_scheduled_for_replaces_existing(tmp_path):
    p = _write_queue_file(tmp_path)
    set_scheduled_for(p, datetime(2026, 5, 4, 13, 0, tzinfo=timezone.utc))
    set_scheduled_for(p, datetime(2026, 5, 5, 14, 0, tzinfo=timezone.utc))
    text = p.read_text()
    assert "2026-05-04" not in text
    assert "2026-05-05T14:00:00" in text


def test_set_scheduled_for_raises_on_non_queue_file(tmp_path):
    p = tmp_path / "no-frontmatter.md"
    p.write_text("just plain text, no frontmatter")
    with pytest.raises(ValueError):
        set_scheduled_for(p, datetime.now(timezone.utc))


def test_get_scheduled_for_returns_none_when_unset(tmp_path):
    p = _write_queue_file(tmp_path)
    assert get_scheduled_for(p) is None


def test_get_scheduled_for_roundtrip(tmp_path):
    p = _write_queue_file(tmp_path)
    when = datetime(2026, 5, 4, 13, 0, tzinfo=timezone.utc)
    set_scheduled_for(p, when)
    assert get_scheduled_for(p) == when


# ──────────────── is_due / filter_due ────────────────


def test_is_due_true_when_unscheduled(tmp_path):
    p = _write_queue_file(tmp_path)
    assert is_due(p) is True


def test_is_due_true_when_scheduled_in_past(tmp_path):
    p = _write_queue_file(tmp_path)
    set_scheduled_for(p, datetime(2020, 1, 1, tzinfo=timezone.utc))
    assert is_due(p) is True


def test_is_due_false_when_scheduled_in_future(tmp_path):
    p = _write_queue_file(tmp_path)
    future = datetime.now(timezone.utc) + timedelta(days=7)
    set_scheduled_for(p, future)
    assert is_due(p) is False


def test_filter_due_partitions_by_schedule(tmp_path):
    (tmp_path / "x").mkdir()
    (tmp_path / "y").mkdir()
    p_due = _write_queue_file(tmp_path / "x")
    p_wait = _write_queue_file(tmp_path / "y")
    set_scheduled_for(p_due, datetime(2020, 1, 1, tzinfo=timezone.utc))
    set_scheduled_for(p_wait, datetime.now(timezone.utc) + timedelta(days=30))

    due = filter_due([p_due, p_wait])
    assert p_due in due
    assert p_wait not in due


# ──────────────── next_occurrence_of_hour ────────────────


def test_next_occurrence_picks_today_when_in_future():
    # Anchor: Monday 09:00 UTC → asking for Monday 14:00 UTC → same day
    now = datetime(2026, 5, 4, 9, 0, tzinfo=timezone.utc)  # Monday
    assert now.weekday() == 0
    out = next_occurrence_of_hour(weekday=0, hour_utc=14, now=now)
    assert out == datetime(2026, 5, 4, 14, 0, tzinfo=timezone.utc)


def test_next_occurrence_picks_next_week_when_past_today():
    # Anchor: Monday 15:00 UTC → asking for Monday 14:00 UTC → next week
    now = datetime(2026, 5, 4, 15, 0, tzinfo=timezone.utc)
    out = next_occurrence_of_hour(weekday=0, hour_utc=14, now=now)
    assert out == datetime(2026, 5, 11, 14, 0, tzinfo=timezone.utc)


def test_next_occurrence_picks_next_weekday():
    # Anchor: Monday 09:00 UTC → asking for Tuesday 14:00 UTC → tomorrow
    now = datetime(2026, 5, 4, 9, 0, tzinfo=timezone.utc)
    out = next_occurrence_of_hour(weekday=1, hour_utc=14, now=now)
    assert out == datetime(2026, 5, 5, 14, 0, tzinfo=timezone.utc)


# ──────────────── schedule_via_best_time ────────────────


def test_schedule_via_best_time_falls_back_to_industry_default(tmp_path, monkeypatch):
    """With no engagement history, optimal_post_time returns industry default
    (X = Tue 14:00 UTC). schedule_via_best_time must set scheduled_for to the
    next occurrence of that slot."""
    monkeypatch.setenv("MARKETING_AGENT_DB_PATH", str(tmp_path / "h.db"))
    p = _write_queue_file(tmp_path)
    when = schedule_via_best_time(p, Platform.X)
    # The set time must match what we read back
    assert get_scheduled_for(p) == when
    # X default is Tue (weekday=1) 14:00 UTC
    assert when.weekday() == 1
    assert when.hour == 14
