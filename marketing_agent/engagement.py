"""Engagement tracker — record what each post earned.

Per-platform metrics (likes / replies / RTs / clicks / saves / new follows)
recorded against the post's external_id. Used to:
  1. Feed back into Strategy Agent (which posts work?)
  2. Show in `cost` CLI alongside spend (ROI)
  3. Detect when a post unexpectedly takes off

Storage: same SQLite DB as memory + cost.
"""
from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from marketing_agent.memory import _default_db_path
from marketing_agent.types import Engagement, Platform

_SCHEMA = """
CREATE TABLE IF NOT EXISTS engagement (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id       TEXT NOT NULL,
    platform      TEXT NOT NULL,
    metric        TEXT NOT NULL,
    count         INTEGER NOT NULL,
    actor         TEXT,
    ts            TEXT NOT NULL,
    UNIQUE(post_id, platform, metric, ts)
);
CREATE INDEX IF NOT EXISTS idx_eng_post ON engagement(post_id, platform);
CREATE INDEX IF NOT EXISTS idx_eng_metric ON engagement(metric, ts);
"""


class EngagementTracker:
    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path) if db_path else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(_SCHEMA)

    def record(self, event: Engagement) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR IGNORE INTO engagement
                   (post_id, platform, metric, count, actor, ts)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (event.post_id, event.platform.value, event.metric,
                 event.count, event.actor, event.timestamp.isoformat()),
            )

    def fetch_x_metrics(self, post_id: str) -> list[Engagement]:
        """Pull current metrics from X API for a single tweet.

        Auth strategy: prefer the X_BEARER_TOKEN (app-only) for reads —
        many free-tier X apps have read-only Bearer access even when the
        OAuth1 user-context flow returns 401 on /tweets/:id. Falls back
        to OAuth1 (consumer + access tokens) when no Bearer is set.
        """
        import os
        bearer = os.getenv("X_BEARER_TOKEN")
        oauth1_keys = ["X_API_KEY", "X_API_KEY_SECRET",
                          "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]
        has_oauth1 = all(os.getenv(k) for k in oauth1_keys)
        if not bearer and not has_oauth1:
            return []
        import tweepy
        if bearer:
            client = tweepy.Client(bearer_token=bearer)
        else:
            client = tweepy.Client(
                consumer_key=os.getenv("X_API_KEY"),
                consumer_secret=os.getenv("X_API_KEY_SECRET"),
                access_token=os.getenv("X_ACCESS_TOKEN"),
                access_token_secret=os.getenv("X_ACCESS_TOKEN_SECRET"),
            )
        tweet = client.get_tweet(post_id, tweet_fields=["public_metrics"])
        if not tweet.data:
            return []
        m = tweet.data.public_metrics or {}
        ts = datetime.now(timezone.utc)
        events = []
        for k, count in m.items():
            metric_name = k.replace("_count", "")  # like_count → like
            events.append(Engagement(
                platform=Platform.X, post_id=post_id,
                metric=metric_name, count=count, timestamp=ts,
            ))
        for e in events:
            self.record(e)
        return events

    def top_posts(self, *, platform: Optional[Platform] = None,
                    metric: str = "like", limit: int = 10) -> list[dict]:
        """Return top posts by a single metric, latest count per (post, metric)."""
        sql = """
            SELECT post_id, platform, metric, MAX(count) AS peak
            FROM engagement
            WHERE metric = ?
        """
        args: list = [metric]
        if platform:
            sql += " AND platform = ?"; args.append(platform.value)
        sql += " GROUP BY post_id, platform, metric ORDER BY peak DESC LIMIT ?"
        args.append(limit)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(sql, args).fetchall()]

    def total_engagement(self) -> dict[str, int]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT metric, SUM(count) FROM engagement GROUP BY metric"
            ).fetchall()
        return {m: int(c or 0) for m, c in rows}
