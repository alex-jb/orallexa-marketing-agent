"""Cost tracking — record approximate $ spent per content generation + post.

Per-call costs (April 2026):
- Claude Sonnet 4.6:   input $3.00 / 1M tokens, output $15.00 / 1M
- Claude Haiku 4.5:    input $0.25 / 1M tokens, output $1.25 / 1M
- X API write:         $0.010 / post (pay-per-use)
- X API read:          $0.005 / call

Tracked in the same SQLite as post history. Useful for: 'is this auto-
posting actually paying for itself?' and 'is the LLM bill creeping up?'.

v0.13: AnthropicClient calls flow through solo-founder-os' shared
AnthropicClient → ~/.marketing-agent/usage.jsonl. cost-audit-agent picks
this path up in the cross-agent monthly report.
"""
from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from marketing_agent.memory import _default_db_path

# Shared usage log path — every solo-founder-os AnthropicClient instance
# writes here. cost-audit-agent reads it for the cross-agent cost report.
USAGE_LOG_PATH = Path.home() / ".marketing-agent" / "usage.jsonl"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cost_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT NOT NULL,
    category        TEXT NOT NULL,    -- llm | x_post | x_read | reddit_post | other
    descriptor      TEXT,
    units           REAL,
    unit_cost_usd   REAL,
    cost_usd        REAL NOT NULL,
    project_name    TEXT
);
CREATE INDEX IF NOT EXISTS idx_cost_ts ON cost_log(ts);
CREATE INDEX IF NOT EXISTS idx_cost_project ON cost_log(project_name);
"""

# Public price book. Update when pricing changes.
PRICES = {
    "claude_sonnet_input": 3.0 / 1_000_000,
    "claude_sonnet_output": 15.0 / 1_000_000,
    "claude_haiku_input": 0.25 / 1_000_000,
    "claude_haiku_output": 1.25 / 1_000_000,
    "x_post": 0.010,
    "x_read": 0.005,
}


class CostTracker:
    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path) if db_path else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(_SCHEMA)

    def log(self, *, category: str, cost_usd: float,
            descriptor: str = "", units: float = 0.0,
            unit_cost_usd: float = 0.0,
            project_name: Optional[str] = None) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO cost_log
                   (ts, category, descriptor, units, unit_cost_usd, cost_usd, project_name)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (datetime.now(timezone.utc).isoformat(), category, descriptor,
                 units, unit_cost_usd, cost_usd, project_name),
            )

    def log_claude(self, *, model: str, input_tokens: int,
                    output_tokens: int, project_name: Optional[str] = None) -> float:
        """Log a Claude call. Returns the cost charged."""
        if "haiku" in model.lower():
            in_rate = PRICES["claude_haiku_input"]
            out_rate = PRICES["claude_haiku_output"]
        else:
            in_rate = PRICES["claude_sonnet_input"]
            out_rate = PRICES["claude_sonnet_output"]
        cost = input_tokens * in_rate + output_tokens * out_rate
        self.log(category="llm", descriptor=model,
                 units=input_tokens + output_tokens,
                 cost_usd=cost, project_name=project_name)
        return cost

    def log_x_post(self, *, project_name: Optional[str] = None) -> float:
        cost = PRICES["x_post"]
        self.log(category="x_post", units=1, unit_cost_usd=cost,
                 cost_usd=cost, project_name=project_name)
        return cost

    def total(self, *, project_name: Optional[str] = None,
                since_iso: Optional[str] = None) -> float:
        sql = "SELECT COALESCE(SUM(cost_usd), 0) FROM cost_log WHERE 1=1"
        args: list = []
        if project_name:
            sql += " AND project_name=?"; args.append(project_name)
        if since_iso:
            sql += " AND ts >= ?"; args.append(since_iso)
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute(sql, args).fetchone()[0] or 0.0

    def by_category(self) -> dict[str, float]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT category, ROUND(SUM(cost_usd), 4) FROM cost_log GROUP BY category"
            ).fetchall()
        return {c: total for c, total in rows}
