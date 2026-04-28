"""Post memory — SQLite-backed dedup so we never re-post the same content twice.

The most common embarrassment of an auto-poster is posting the same thing
twice (e.g. cron retried after timeout, repo had no new commits but you
forced a run). This module gives every post a content hash and a
post-history table; the orchestrator can ask "have we posted this
already?" before sending.

Storage: a single SQLite file at `~/.marketing_agent/history.db`. Override
with `MARKETING_AGENT_DB_PATH`. Plain Python `sqlite3` — no external dep.
"""
from __future__ import annotations
import hashlib
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from marketing_agent.types import Platform, Post


_SCHEMA = """
CREATE TABLE IF NOT EXISTS post_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    content_hash    TEXT NOT NULL,
    platform        TEXT NOT NULL,
    project_name    TEXT NOT NULL,
    body_preview    TEXT NOT NULL,
    external_id     TEXT,
    posted_at       TEXT NOT NULL,
    UNIQUE(content_hash, platform)
);
CREATE INDEX IF NOT EXISTS idx_history_project_time
    ON post_history(project_name, posted_at);
CREATE INDEX IF NOT EXISTS idx_history_platform_time
    ON post_history(platform, posted_at);
"""


def _default_db_path() -> Path:
    override = os.getenv("MARKETING_AGENT_DB_PATH")
    if override:
        return Path(override)
    return Path.home() / ".marketing_agent" / "history.db"


def _hash(post: Post) -> str:
    """Deterministic content fingerprint. Title + body + platform."""
    parts = [post.platform.value, post.title or "", post.body]
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:16]


class PostMemory:
    """Track posts we've sent, by content hash."""

    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path) if db_path else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(_SCHEMA)

    def has_posted(self, post: Post) -> bool:
        """True if a post with the same hash + platform was already sent."""
        h = _hash(post)
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT 1 FROM post_history WHERE content_hash=? AND platform=? LIMIT 1",
                (h, post.platform.value),
            )
            return cur.fetchone() is not None

    def record(self, post: Post, project_name: str,
               external_id: Optional[str] = None) -> int:
        """Record a successful post. Returns the row id."""
        h = _hash(post)
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """INSERT OR IGNORE INTO post_history
                   (content_hash, platform, project_name, body_preview,
                    external_id, posted_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (h, post.platform.value, project_name,
                 post.body[:200], external_id,
                 datetime.now(timezone.utc).isoformat()),
            )
            return cur.lastrowid or 0

    def recent(self, project_name: Optional[str] = None,
               platform: Optional[Platform] = None,
               limit: int = 20) -> list[dict]:
        """Return recent post history, optionally filtered."""
        sql = "SELECT * FROM post_history WHERE 1=1"
        args: list = []
        if project_name:
            sql += " AND project_name=?"
            args.append(project_name)
        if platform:
            sql += " AND platform=?"
            args.append(platform.value)
        sql += " ORDER BY posted_at DESC LIMIT ?"
        args.append(limit)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(sql, args).fetchall()]

    def stats(self) -> dict[str, int]:
        """Aggregate counts by platform."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT platform, COUNT(*) AS n FROM post_history GROUP BY platform"
            ).fetchall()
        return {p: n for p, n in rows}
