"""Reflexion memory — persistent critic findings retrieved on next generation.

Real Reflexion (NeurIPS 2024 follow-up) stores per-task reflections so the
agent learns across runs. This module is the cross-session backbone:

  1. Every time the supervisor critiques a draft, the (project, platform,
     reasons, score) tuple is appended to the SQLite reflection log.
  2. On the next generation pass for the same (project, platform), the
     supervisor pulls the top-K most recent low-score reflections and
     prepends them to the LLM prompt as "patterns to avoid."

Why SQLite + recent-K instead of embedding similarity? Recent-K is good
enough for a personal marketing agent — the failure modes don't shift
weekly, and lookups stay fast even with 100k entries. Add embeddings in
v0.7 if recall starts mattering.

Schema lives in the same SQLite file as memory + cost + engagement.

Storage is opt-in via gate=True path in queue.submit() (default) and
direct calls from supervisor.supervise(). Disable globally by setting
MARKETING_AGENT_NO_REFLEXION=1.
"""
from __future__ import annotations
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from marketing_agent.memory import _default_db_path
from marketing_agent.types import Platform

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reflection_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name  TEXT NOT NULL,
    platform      TEXT NOT NULL,
    score         REAL NOT NULL,
    reasons       TEXT NOT NULL,           -- newline-joined critic reasons
    body_preview  TEXT NOT NULL,           -- first 200 chars of the rejected draft
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reflect_proj_plat
    ON reflection_log(project_name, platform, created_at DESC);
"""


def _disabled() -> bool:
    return bool(os.getenv("MARKETING_AGENT_NO_REFLEXION"))


class ReflexionMemory:
    """Persistent log of critic findings, queryable per (project, platform)."""

    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path) if db_path else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(_SCHEMA)

    def record(self, *, project_name: str, platform: Platform,
                 score: float, reasons: list[str],
                 body_preview: str = "") -> int:
        """Append a reflection. Skip silently if globally disabled."""
        if _disabled():
            return 0
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """INSERT INTO reflection_log
                   (project_name, platform, score, reasons, body_preview, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (project_name, platform.value, float(score),
                 "\n".join(reasons or []),
                 (body_preview or "")[:200],
                 datetime.now(timezone.utc).isoformat()),
            )
            return cur.lastrowid or 0

    def recent_low_score(self, *, project_name: str, platform: Platform,
                            top_k: int = 5,
                            max_score: float = 6.0) -> list[dict]:
        """Return the top_k most recent reflections with score < max_score.

        These are the "patterns we recently produced and self-rejected" —
        ideal as a steering hint to keep the agent from repeating them.
        """
        if _disabled():
            return []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT score, reasons, body_preview, created_at
                   FROM reflection_log
                   WHERE project_name = ? AND platform = ? AND score < ?
                   ORDER BY created_at DESC LIMIT ?""",
                (project_name, platform.value, max_score, top_k),
            ).fetchall()
        return [{**dict(r),
                  "reasons": [ln for ln in (r["reasons"] or "").split("\n") if ln]}
                 for r in rows]

    def steering_hint(self, *, project_name: str, platform: Platform,
                         top_k: int = 3) -> str:
        """Compact human-readable hint for an LLM prompt. '' if no history."""
        rows = self.recent_low_score(
            project_name=project_name, platform=platform, top_k=top_k)
        if not rows:
            return ""
        lines = [
            "[Recent patterns to avoid — your past low-scoring drafts on this "
            f"({project_name}/{platform.value}) channel]:",
        ]
        for r in rows:
            top_reasons = "; ".join(r["reasons"][:3]) or "(unspecified)"
            lines.append(f"- score {r['score']}: {top_reasons}")
        return "\n".join(lines)

    def stats(self) -> dict:
        """Aggregate counts. For CLI / observability."""
        if _disabled():
            return {"disabled": True}
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM reflection_log").fetchone()[0]
            avg = conn.execute(
                "SELECT AVG(score) FROM reflection_log").fetchone()[0]
            by_plat = dict(conn.execute(
                """SELECT platform, COUNT(*) FROM reflection_log
                   GROUP BY platform"""
            ).fetchall())
        return {"total": total, "avg_score": round(avg or 0.0, 2),
                "by_platform": by_plat}
