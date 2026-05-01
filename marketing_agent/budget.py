"""budget — soft daily cap on LLM spend.

Why: the proactive trends loop fans out across N projects × M platforms
× top_n trends. A misconfigured `top_n=20` or accidentally adding 8
platforms could blow up the daily LLM bill before the human notices.
This module reads `~/.marketing-agent/usage.jsonl` (the cross-provider
usage log written by `solo_founder_os.AnthropicClient` + the in-house
`log_usage` shim), prices each row, sums today's spend, and answers
"are we over the daily cap yet?".

The cap is opt-in via the env var `MARKETING_AGENT_DAILY_BUDGET_USD`.
Unset → unlimited (current behavior preserved). Numeric value → soft
cap; the caller (currently `_run_trends_for_projects` in daily_post.py)
checks before each project iteration and bails out gracefully when over.

Pricing source: `marketing_agent.cost.PRICES`. Edge inference (Cloudflare
Workers AI Llama 3.3) is approximated at $0.011 / 1M tokens — cheap
enough that a daily-budget overrun there is essentially impossible.
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from marketing_agent import cost as _cost  # late-bind USAGE_LOG_PATH for tests


# Edge inference (Cloudflare Workers AI Llama 3.3) — uniform per-token
# rate; treat input + output the same since CF doesn't price-distinguish.
_EDGE_RATE = 0.011 / 1_000_000


def _price_row(model: str, input_tokens: int, output_tokens: int) -> float:
    """Map (model, tokens) → USD using the cost.PRICES book.

    Falls through to the EDGE rate for cloudflare/llama; defaults to
    Sonnet pricing for unknown Anthropic-shaped models so we err on
    the side of overestimating spend (safer for a budget guard).
    """
    m = (model or "").lower()
    P = _cost.PRICES
    if "haiku" in m:
        in_r, out_r = P["claude_haiku_input"], P["claude_haiku_output"]
    elif "sonnet" in m or "opus" in m or "claude" in m:
        in_r, out_r = P["claude_sonnet_input"], P["claude_sonnet_output"]
    elif "llama" in m or "cloudflare" in m or "workers-ai" in m:
        return (input_tokens + output_tokens) * _EDGE_RATE
    else:
        # Unknown — assume Sonnet to be conservative.
        in_r, out_r = P["claude_sonnet_input"], P["claude_sonnet_output"]
    return input_tokens * in_r + output_tokens * out_r


def daily_spend_usd(*, log_path: Optional[Path] = None,
                       now: Optional[datetime] = None) -> float:
    """Sum today's spend (UTC day) from the usage JSONL.

    Returns 0.0 if the log doesn't exist or is empty/corrupt — never
    raises. The budget guard must never break the cron over a parse
    error in an unrelated row.
    """
    path = log_path or _cost.USAGE_LOG_PATH
    if not Path(path).exists():
        return 0.0
    today = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
    total = 0.0
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = str(row.get("ts", ""))
                if not ts.startswith(today):
                    continue
                total += _price_row(
                    str(row.get("model", "")),
                    int(row.get("input_tokens", 0) or 0),
                    int(row.get("output_tokens", 0) or 0),
                )
    except OSError:
        return 0.0
    return round(total, 6)


def configured_cap_usd() -> Optional[float]:
    """Read MARKETING_AGENT_DAILY_BUDGET_USD env var.

    Returns None when unset / unparseable / non-positive — signals
    "no cap, behave as before".
    """
    raw = os.getenv("MARKETING_AGENT_DAILY_BUDGET_USD")
    if not raw:
        return None
    try:
        v = float(raw)
    except ValueError:
        return None
    return v if v > 0 else None


def is_over_budget(*, log_path: Optional[Path] = None,
                      cap_usd: Optional[float] = None,
                      now: Optional[datetime] = None) -> bool:
    """True iff today's spend already meets-or-exceeds the cap.

    `cap_usd` defaults to `configured_cap_usd()`. When no cap is set,
    always returns False (preserve "unlimited" semantics).
    """
    cap = cap_usd if cap_usd is not None else configured_cap_usd()
    if cap is None:
        return False
    return daily_spend_usd(log_path=log_path, now=now) >= cap
