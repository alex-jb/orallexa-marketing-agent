"""trend_memory — remember which trending URLs we already drafted about.

Why: without this, the same hot HN story (or top GitHub repo of the
week) lands in `trends.aggregate()` for 3-7 days in a row, and the
proactive loop produces a fresh "another take on this" draft each
morning. The post-content semantic-dedup gate inside `ApprovalQueue.submit`
catches near-duplicate WRITING but cannot see that the underlying TREND
URL is the same.

This module adds the missing layer: per-(project, trend URL) memory of
when we last drafted about it. `filter_fresh()` is called inside
`trends_to_drafts.trends_to_drafts()` between aggregate and generation,
so we never even spend tokens on a stale trend.

Storage: SQLite, same DB as `PostMemory` / `EngagementTracker`. One row
per (url, project) ever drafted. `was_drafted_recently()` does a
parametrized cutoff comparison against `drafted_at` (UTC ISO).
"""
from __future__ import annotations
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

from marketing_agent.memory import _default_db_path


_SCHEMA = """
CREATE TABLE IF NOT EXISTS drafted_trends (
    url             TEXT NOT NULL,
    project_name    TEXT NOT NULL,
    drafted_at      TEXT NOT NULL,
    PRIMARY KEY (url, project_name)
);
CREATE INDEX IF NOT EXISTS idx_drafted_trends_when
    ON drafted_trends(drafted_at);
"""


class TrendMemory:
    """Per-(project, trend URL) draft history — keep the proactive loop fresh."""

    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path) if db_path else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(_SCHEMA)

    # ───────────────── reads ─────────────────

    def was_drafted_recently(self, url: str, project_name: str,
                                *, days: int = 7,
                                now: Optional[datetime] = None) -> bool:
        """True if a draft was generated for this (url, project) within
        `days` of `now` (default: utcnow). Empty url short-circuits to False."""
        if not url:
            return False
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=days)
        cutoff_iso = cutoff.isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT 1 FROM drafted_trends "
                "WHERE url=? AND project_name=? AND drafted_at >= ? LIMIT 1",
                (url, project_name, cutoff_iso),
            )
            return cur.fetchone() is not None

    def filter_fresh(self, items, project_name: str, *,
                       days: int = 7,
                       now: Optional[datetime] = None) -> list:
        """Drop items whose URL was drafted for this project within `days`.

        Accepts any iterable of objects with a `.url` attr (TrendItem in
        practice). Order-preserving. Empty-URL items pass through.
        """
        out = []
        for it in items:
            url = getattr(it, "url", "") or ""
            if url and self.was_drafted_recently(
                    url, project_name, days=days, now=now):
                continue
            out.append(it)
        return out

    # ───────────────── writes ─────────────────

    def mark_drafted(self, url: str, project_name: str, *,
                       now: Optional[datetime] = None) -> None:
        """Record (or refresh) the (url, project) draft timestamp.

        Uses INSERT OR REPLACE — re-drafting after the cooldown bumps
        the timestamp to today, restarting the cooldown.
        """
        if not url:
            return
        ts = (now or datetime.now(timezone.utc)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO drafted_trends "
                "(url, project_name, drafted_at) VALUES (?, ?, ?)",
                (url, project_name, ts),
            )

    def mark_many(self, urls: Iterable[str], project_name: str, *,
                    now: Optional[datetime] = None) -> int:
        """Bulk variant. Returns the number of urls marked."""
        n = 0
        for u in urls:
            if u:
                self.mark_drafted(u, project_name, now=now)
                n += 1
        return n

    def purge_older_than(self, *, days: int = 90,
                            now: Optional[datetime] = None) -> int:
        """Garbage-collect rows older than `days`. Returns rows deleted.

        90-day default — rows older than that are noise (cooldown is at
        most a few weeks; old rows just bloat the table).
        """
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=days)
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "DELETE FROM drafted_trends WHERE drafted_at < ?",
                (cutoff.isoformat(),),
            )
            return cur.rowcount or 0
