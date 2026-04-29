"""Best-time-to-post analyzer — empirical CDF over hour-of-week.

For each (platform, project) pair, looks at:
  post_history.posted_at   →  weekday + hour bucket
  engagement.count (metric=like, latest per post)  →  reward

Aggregates mean reward per (weekday, hour) bucket. Returns argmax.

Why empirical CDF, not ML? With <500 posts, you can't fit anything more
than a histogram without overfitting. Buffer/Hypefury's "AI optimal time"
in 2025 is literally argmax over hour-of-week buckets.

Falls back to platform-specific industry defaults when there's no data.
"""
from __future__ import annotations
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from marketing_agent.memory import _default_db_path
from marketing_agent.types import Platform


# Industry-default best hours (UTC) — sourced from Buffer / Hootsuite 2025
# annual reports. Used when no historical data exists.
_INDUSTRY_DEFAULTS_UTC: dict[Platform, tuple[int, int]] = {
    Platform.X:           (1, 14),  # Tue 14:00 UTC ≈ 10am EDT
    Platform.LINKEDIN:    (1, 13),  # Tue 13:00 UTC
    Platform.REDDIT:      (2, 11),  # Wed 11:00 UTC ≈ early morning EDT
    Platform.DEV_TO:      (1, 12),  # Tue noon UTC
    Platform.BLUESKY:     (3, 16),  # Thu 16:00 UTC
    Platform.MASTODON:    (3, 17),  # Thu 17:00 UTC
    Platform.ZHIHU:       (1, 13),  # Tue ~21:00 Beijing
    Platform.XIAOHONGSHU: (4, 12),  # Fri ~20:00 Beijing
}

_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def optimal_post_time(platform: Platform, *,
                       project_name: Optional[str] = None,
                       metric: str = "like",
                       min_samples: int = 5,
                       db_path: Optional[Path | str] = None
                       ) -> tuple[int, int, str]:
    """Return (weekday, hour_utc, source) where weekday is 0=Mon..6=Sun.

    source ∈ {"data", "default"} — "data" means we had >= min_samples posts
    in at least one bucket; "default" means we fell back to industry default.
    """
    db = Path(db_path) if db_path else _default_db_path()
    if not db.exists():
        wd, h = _INDUSTRY_DEFAULTS_UTC.get(platform, (1, 14))
        return wd, h, "default"

    sql = """
        SELECT h.posted_at, COALESCE(MAX(e.count), 0) AS reward
        FROM post_history h
        LEFT JOIN engagement e
          ON e.post_id = h.external_id
         AND e.metric = ?
        WHERE h.platform = ?
    """
    args: list = [metric, platform.value]
    if project_name:
        sql += " AND h.project_name = ?"
        args.append(project_name)
    sql += " GROUP BY h.id"

    buckets: dict[tuple[int, int], list[float]] = {}
    with sqlite3.connect(db) as conn:
        for posted_at, reward in conn.execute(sql, args).fetchall():
            try:
                ts = datetime.fromisoformat(posted_at)
            except ValueError:
                continue
            key = (ts.weekday(), ts.hour)
            buckets.setdefault(key, []).append(float(reward))

    if not buckets or max(len(v) for v in buckets.values()) < min_samples:
        wd, h = _INDUSTRY_DEFAULTS_UTC.get(platform, (1, 14))
        return wd, h, "default"

    # Argmax mean reward across buckets
    means = {k: sum(v) / len(v) for k, v in buckets.items()}
    best = max(means.items(), key=lambda kv: kv[1])[0]
    return best[0], best[1], "data"


def report(platform: Platform, *, project_name: Optional[str] = None,
            metric: str = "like",
            db_path: Optional[Path | str] = None) -> list[dict]:
    """Full hour-of-week report — weekday/hour/n_samples/mean_reward.

    For visualization or CLI output. Sorted by mean reward descending.
    """
    db = Path(db_path) if db_path else _default_db_path()
    if not db.exists():
        return []

    sql = """
        SELECT h.posted_at, COALESCE(MAX(e.count), 0) AS reward
        FROM post_history h
        LEFT JOIN engagement e
          ON e.post_id = h.external_id
         AND e.metric = ?
        WHERE h.platform = ?
    """
    args: list = [metric, platform.value]
    if project_name:
        sql += " AND h.project_name = ?"
        args.append(project_name)
    sql += " GROUP BY h.id"

    buckets: dict[tuple[int, int], list[float]] = {}
    with sqlite3.connect(db) as conn:
        for posted_at, reward in conn.execute(sql, args).fetchall():
            try:
                ts = datetime.fromisoformat(posted_at)
            except ValueError:
                continue
            key = (ts.weekday(), ts.hour)
            buckets.setdefault(key, []).append(float(reward))

    out = []
    for (wd, h), rewards in buckets.items():
        out.append({
            "weekday": _WEEKDAYS[wd],
            "weekday_idx": wd,
            "hour_utc": h,
            "n_samples": len(rewards),
            "mean_reward": round(sum(rewards) / len(rewards), 2),
        })
    out.sort(key=lambda r: r["mean_reward"], reverse=True)
    return out
