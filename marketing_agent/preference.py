"""ICPL — In-Context Preference Learning from human edits.

Per Q1 2026 research, in-context preference learning (ICPL) is the cheapest
path to "learn from edits" for sub-500-pair regimes — no LoRA, no DPO,
no training. Just: log every (original_draft, human_edited) pair, and at
generation time inject the most recent N pairs as few-shot exemplars
into the LLM prompt.

Migration path: at ~500+ pairs, swap to DPO via Together.ai or similar
(~$3/1M tokens). Until then, ICPL captures most of the value at zero cost.

Storage: extra table in the same SQLite as memory + cost + engagement.
"""
from __future__ import annotations
import difflib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from marketing_agent.memory import _default_db_path
from marketing_agent.types import Platform

_SCHEMA = """
CREATE TABLE IF NOT EXISTS edits (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name    TEXT NOT NULL,
    platform        TEXT NOT NULL,
    original_body   TEXT NOT NULL,
    edited_body     TEXT NOT NULL,
    diff_chars      INTEGER NOT NULL,
    edit_ratio      REAL NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_edits_proj_plat
    ON edits(project_name, platform, created_at DESC);
"""


def _diff_summary(a: str, b: str) -> tuple[int, float]:
    """Return (chars_changed, edit_ratio in [0,1]).

    edit_ratio: 0.0 = identical, 1.0 = completely rewritten. Computed via
    SequenceMatcher.ratio() inverted.
    """
    if a == b:
        return 0, 0.0
    matcher = difflib.SequenceMatcher(None, a, b)
    ratio = 1.0 - matcher.ratio()
    chars = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            chars += max(i2 - i1, j2 - j1)
    return chars, round(ratio, 3)


class PreferenceStore:
    """SQLite-backed log of (original, edited) pairs from human review."""

    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path) if db_path else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(_SCHEMA)

    def record(self, *, project_name: str, platform: Platform,
                 original_body: str, edited_body: str) -> Optional[int]:
        """Append an edit. Returns row id, or None if no actual change."""
        if original_body.strip() == edited_body.strip():
            return None
        chars, ratio = _diff_summary(original_body, edited_body)
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """INSERT INTO edits
                   (project_name, platform, original_body, edited_body,
                    diff_chars, edit_ratio, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (project_name, platform.value, original_body, edited_body,
                 chars, ratio,
                 datetime.now(timezone.utc).isoformat()),
            )
            return cur.lastrowid

    def recent_pairs(self, *, project_name: Optional[str] = None,
                       platform: Optional[Platform] = None,
                       limit: int = 5,
                       min_ratio: float = 0.05) -> list[dict]:
        """Return most-recent edit pairs above a minimum edit-ratio.

        We skip near-identical edits (typo fixes) — they're not informative
        as preference signal. Default threshold: 5% of body changed.
        """
        sql = ("SELECT project_name, platform, original_body, edited_body, "
                "edit_ratio, created_at FROM edits WHERE edit_ratio >= ?")
        args: list = [min_ratio]
        if project_name:
            sql += " AND project_name = ?"; args.append(project_name)
        if platform:
            sql += " AND platform = ?"; args.append(platform.value)
        sql += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(sql, args).fetchall()]

    def few_shot_block(self, *, project_name: Optional[str] = None,
                          platform: Optional[Platform] = None,
                          limit: int = 5) -> str:
        """Render recent edit pairs as an LLM prompt fragment.

        Returns "" when the store has no qualifying pairs (caller can skip
        the injection cleanly).
        """
        pairs = self.recent_pairs(
            project_name=project_name, platform=platform, limit=limit)
        if not pairs:
            return ""
        lines = [
            "[Examples of how the human reviewer improved past drafts on "
            "this channel — match this editing direction]:"
        ]
        for p in pairs:
            lines.append(f"\nORIGINAL: {p['original_body'][:300]}")
            lines.append(f"IMPROVED: {p['edited_body'][:300]}")
        return "\n".join(lines)

    def stats(self) -> dict:
        """Aggregate counts for CLI / observability."""
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM edits").fetchone()[0]
            avg = conn.execute(
                "SELECT AVG(edit_ratio) FROM edits"
            ).fetchone()[0] or 0.0
            by_plat = dict(conn.execute(
                "SELECT platform, COUNT(*) FROM edits GROUP BY platform"
            ).fetchall())
        return {
            "total_edits": total,
            "avg_edit_ratio": round(avg, 3),
            "by_platform": by_plat,
        }
