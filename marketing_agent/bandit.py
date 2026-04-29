"""Variant bandit — Thompson sampling over post stylistic variants.

Why bandit instead of always picking "the best so far"? Because best-so-far
under <50 trials is just noise: a single viral tweet from "stat-led" makes
you over-commit to it forever. Thompson sampling explores under-tried arms
proportional to uncertainty.

Storage: extra table in the same SQLite DB as memory + cost + engagement.
Per (platform, variant_key) we keep Beta(α, β) parameters. After each
post is published we record the reward (post → engagement.like_count
normalized 0-1 via a logistic squash). Choose() samples each Beta and
picks argmax.

Math: classic Thompson with Beta(1, 1) prior (uniform). Reward is squashed
to [0, 1] so we don't get explosion at high engagement.

Usage:
    bandit = VariantBandit()
    chosen = bandit.choose([p.variant_key for p in variants if p.variant_key])
    # publish that variant; later when we have engagement:
    bandit.update("x:stat-led", reward=0.85)
"""
from __future__ import annotations
import math
import random
import sqlite3
from pathlib import Path
from typing import Optional

from marketing_agent.memory import _default_db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS bandit_arm (
    variant_key   TEXT PRIMARY KEY,
    alpha         REAL NOT NULL DEFAULT 1.0,
    beta          REAL NOT NULL DEFAULT 1.0,
    n_pulls       INTEGER NOT NULL DEFAULT 0,
    last_updated  TEXT
);
"""


def _squash(raw: float, midpoint: float = 50.0) -> float:
    """Map raw engagement count (likes, etc.) into [0, 1] reward.

    50 likes → 0.5 reward; 200 likes → ~0.8; 1000 likes → ~0.95.
    Tuned so a "decent" post gets a meaningful signal without one viral
    post overwhelming the prior.
    """
    if raw <= 0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-(raw - midpoint) / midpoint))


class VariantBandit:
    """Thompson-sampling bandit over content style variants."""

    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path) if db_path else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(_SCHEMA)

    def _ensure_arm(self, key: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO bandit_arm (variant_key) VALUES (?)",
                (key,),
            )

    def choose(self, variant_keys: list[str]) -> str:
        """Sample one variant via Thompson sampling. Returns the chosen key.

        If only one variant given, returns it (no exploration needed).
        """
        if not variant_keys:
            raise ValueError("variant_keys cannot be empty")
        if len(variant_keys) == 1:
            return variant_keys[0]
        for k in variant_keys:
            self._ensure_arm(k)
        with sqlite3.connect(self.db_path) as conn:
            rows = {r[0]: (r[1], r[2]) for r in conn.execute(
                "SELECT variant_key, alpha, beta FROM bandit_arm "
                "WHERE variant_key IN (" + ",".join("?" * len(variant_keys)) + ")",
                variant_keys,
            ).fetchall()}
        samples = {k: random.betavariate(*rows.get(k, (1.0, 1.0)))
                   for k in variant_keys}
        return max(samples.items(), key=lambda kv: kv[1])[0]

    def update(self, variant_key: str, *, reward: float) -> None:
        """Update Beta parameters with a reward in [0, 1].

        Beta(α, β) is conjugate to Bernoulli; for continuous reward in [0, 1]
        we treat it as a partial success (α += r, β += 1 - r). Standard
        approximation in industry bandit code.
        """
        if not 0.0 <= reward <= 1.0:
            raise ValueError(f"reward must be in [0, 1], got {reward}")
        self._ensure_arm(variant_key)
        from datetime import datetime, timezone
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """UPDATE bandit_arm
                   SET alpha = alpha + ?, beta = beta + ?,
                       n_pulls = n_pulls + 1,
                       last_updated = ?
                   WHERE variant_key = ?""",
                (reward, 1.0 - reward,
                 datetime.now(timezone.utc).isoformat(),
                 variant_key),
            )

    def update_from_engagement(self, variant_key: str, raw_engagement: float,
                                  midpoint: float = 50.0) -> float:
        """Convenience: squash raw engagement count → reward → update.

        Returns the squashed reward used.
        """
        r = _squash(raw_engagement, midpoint=midpoint)
        self.update(variant_key, reward=r)
        return r

    def stats(self) -> list[dict]:
        """Per-arm summary: alpha, beta, n_pulls, posterior mean."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM bandit_arm ORDER BY n_pulls DESC"
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["mean"] = round(d["alpha"] / (d["alpha"] + d["beta"]), 4)
            out.append(d)
        return out
