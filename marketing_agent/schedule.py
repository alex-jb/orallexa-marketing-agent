"""Scheduled posting — `scheduled_for` frontmatter + cron-aware publish.

Why? `git mv pending/X approved/X` triggers publish.yml immediately. For
launch-day campaigns you want **specific times** — PH-day at 9:00 EDT,
LinkedIn at 10:00, 即刻 at 14:00 Beijing. This module adds a `scheduled_for`
ISO datetime to a queue file's frontmatter; a new `scheduled.yml` cron
runs hourly and only publishes items where `scheduled_for <= now()`.

Items in `queue/approved/` without `scheduled_for` publish immediately
(preserves v0.9 behavior).

CLI:
    marketing-agent schedule \\
      --file queue/pending/X.md \\
      --at 2026-05-04T13:00:00Z

Or set scheduled_for via best_time:
    marketing-agent schedule --file <X> --best-time --platform x

The latter computes optimal_post_time() against the engagement DB and
sets scheduled_for to the next occurrence of that hour-of-week.
"""
from __future__ import annotations
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from marketing_agent.queue import _FRONTMATTER_RE
from marketing_agent.types import Platform


def parse_iso(value: str) -> datetime:
    """Parse 2026-05-04T13:00:00Z or +offset forms; always return tz-aware UTC."""
    s = value.strip()
    # Accept 'Z' suffix
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def set_scheduled_for(path: Path, when: datetime) -> None:
    """Insert or update `scheduled_for: <iso>` in the file's frontmatter.

    Idempotent — re-running with a new datetime just rewrites the line.
    """
    text = path.read_text()
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError(f"Not a queue file (no frontmatter): {path}")
    meta_str, body = m.groups()
    iso = when.astimezone(timezone.utc).isoformat()
    if "scheduled_for:" in meta_str:
        meta_str = re.sub(r"^scheduled_for:.*$",
                            f"scheduled_for: {iso}",
                            meta_str, flags=re.MULTILINE)
    else:
        meta_str = meta_str.rstrip() + f"\nscheduled_for: {iso}"
    path.write_text(f"---\n{meta_str}\n---\n{body.lstrip()}")


def get_scheduled_for(path: Path) -> Optional[datetime]:
    """Return the parsed scheduled_for time, or None if absent / malformed."""
    text = path.read_text()
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    for line in m.group(1).splitlines():
        if line.strip().startswith("scheduled_for:"):
            iso = line.split(":", 1)[1].strip()
            try:
                return parse_iso(iso)
            except ValueError:
                return None
    return None


def is_due(path: Path, *, now: Optional[datetime] = None) -> bool:
    """True iff the file has no scheduled_for OR scheduled_for <= now.

    Items without `scheduled_for` are treated as "due now" — preserves the
    v0.9 behavior where any file in approved/ publishes immediately.
    """
    sf = get_scheduled_for(path)
    if sf is None:
        return True
    when = now or datetime.now(timezone.utc)
    return sf <= when


def filter_due(paths: list[Path], *,
                 now: Optional[datetime] = None) -> list[Path]:
    """Return the subset of paths whose scheduled_for is in the past (or unset)."""
    return [p for p in paths if is_due(p, now=now)]


def next_occurrence_of_hour(weekday: int, hour_utc: int, *,
                              now: Optional[datetime] = None) -> datetime:
    """Compute the next datetime that falls on (weekday, hour_utc).

    weekday: 0=Mon..6=Sun (matches optimal_post_time output).
    Returns a tz-aware UTC datetime strictly in the future (≥ 1 minute from now).
    """
    n = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    # Today's candidate: replace hour, set minute=0
    candidate = n.replace(hour=hour_utc, minute=0, second=0, microsecond=0)
    days_ahead = (weekday - n.weekday()) % 7
    if days_ahead == 0 and candidate <= n + timedelta(minutes=1):
        days_ahead = 7  # already past today's slot → next week
    return candidate + timedelta(days=days_ahead)


def schedule_via_best_time(path: Path, platform: Platform, *,
                              project_name: Optional[str] = None,
                              metric: str = "like") -> datetime:
    """Set scheduled_for to the next occurrence of best-time for this platform.

    Returns the chosen datetime so the caller can log it.
    """
    from marketing_agent.best_time import optimal_post_time
    wd, h, _src = optimal_post_time(platform, project_name=project_name,
                                       metric=metric)
    when = next_occurrence_of_hour(wd, h)
    set_scheduled_for(path, when)
    return when
