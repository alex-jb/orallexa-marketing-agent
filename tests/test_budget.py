"""Tests for budget — daily LLM spend cap."""
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta

from marketing_agent.budget import (
    _price_row, configured_cap_usd, daily_spend_usd, is_over_budget,
)
from marketing_agent.cost import PRICES


# ───────────────── _price_row ─────────────────


def test_price_row_haiku():
    cost = _price_row("claude-haiku-4-5", 1_000_000, 1_000_000)
    expected = PRICES["claude_haiku_input"] + PRICES["claude_haiku_output"]
    expected *= 1_000_000
    assert cost == expected


def test_price_row_sonnet():
    cost = _price_row("claude-sonnet-4-6", 1_000_000, 1_000_000)
    expected = PRICES["claude_sonnet_input"] + PRICES["claude_sonnet_output"]
    expected *= 1_000_000
    assert cost == expected


def test_price_row_unknown_model_falls_back_to_sonnet_conservatively():
    """Unknown models price as Sonnet — better to over-estimate spend."""
    unknown = _price_row("ridiculous-2099", 1000, 1000)
    sonnet = _price_row("claude-sonnet-4-6", 1000, 1000)
    assert unknown == sonnet


def test_price_row_edge_inference_priced_low():
    edge = _price_row("cloudflare-llama-3.3", 1_000_000, 1_000_000)
    sonnet = _price_row("claude-sonnet-4-6", 1_000_000, 1_000_000)
    # Edge must be at least 100× cheaper than Sonnet at 1M tokens.
    assert edge < sonnet / 100


# ───────────────── daily_spend_usd ─────────────────


def _write(path, rows):
    with open(path, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def test_daily_spend_returns_zero_when_log_missing(tmp_path):
    assert daily_spend_usd(log_path=tmp_path / "nope.jsonl") == 0.0


def test_daily_spend_returns_zero_when_log_empty(tmp_path):
    log = tmp_path / "u.jsonl"
    log.write_text("")
    assert daily_spend_usd(log_path=log) == 0.0


def test_daily_spend_sums_today_only(tmp_path):
    log = tmp_path / "u.jsonl"
    today = datetime.now(timezone.utc)
    yesterday = today - timedelta(days=1)
    _write(log, [
        {"ts": yesterday.isoformat(), "model": "claude-haiku-4-5",
          "input_tokens": 1000, "output_tokens": 1000},
        {"ts": today.isoformat(), "model": "claude-haiku-4-5",
          "input_tokens": 1000, "output_tokens": 1000},
    ])
    spent = daily_spend_usd(log_path=log, now=today)
    haiku_cost_per_call = (
        PRICES["claude_haiku_input"] * 1000
        + PRICES["claude_haiku_output"] * 1000
    )
    assert abs(spent - haiku_cost_per_call) < 1e-9


def test_daily_spend_skips_corrupt_lines(tmp_path):
    log = tmp_path / "u.jsonl"
    today = datetime.now(timezone.utc)
    log.write_text(
        "not json\n"
        + json.dumps({"ts": today.isoformat(), "model": "claude-haiku-4-5",
                       "input_tokens": 1000, "output_tokens": 1000}) + "\n"
        + "{partial json\n"
    )
    # Doesn't raise; counts the one valid row.
    spent = daily_spend_usd(log_path=log, now=today)
    assert spent > 0


# ───────────────── configured_cap_usd ─────────────────


def test_configured_cap_usd_unset(monkeypatch):
    monkeypatch.delenv("MARKETING_AGENT_DAILY_BUDGET_USD", raising=False)
    assert configured_cap_usd() is None


def test_configured_cap_usd_invalid(monkeypatch):
    monkeypatch.setenv("MARKETING_AGENT_DAILY_BUDGET_USD", "abc")
    assert configured_cap_usd() is None


def test_configured_cap_usd_zero_or_negative(monkeypatch):
    monkeypatch.setenv("MARKETING_AGENT_DAILY_BUDGET_USD", "0")
    assert configured_cap_usd() is None
    monkeypatch.setenv("MARKETING_AGENT_DAILY_BUDGET_USD", "-1")
    assert configured_cap_usd() is None


def test_configured_cap_usd_valid(monkeypatch):
    monkeypatch.setenv("MARKETING_AGENT_DAILY_BUDGET_USD", "5.50")
    assert configured_cap_usd() == 5.5


# ───────────────── is_over_budget ─────────────────


def test_is_over_budget_false_when_no_cap(tmp_path, monkeypatch):
    monkeypatch.delenv("MARKETING_AGENT_DAILY_BUDGET_USD", raising=False)
    assert is_over_budget(log_path=tmp_path / "u.jsonl") is False


def test_is_over_budget_false_when_under_cap(tmp_path):
    log = tmp_path / "u.jsonl"
    today = datetime.now(timezone.utc)
    _write(log, [{"ts": today.isoformat(), "model": "claude-haiku-4-5",
                    "input_tokens": 1000, "output_tokens": 1000}])
    assert is_over_budget(log_path=log, cap_usd=1.0, now=today) is False


def test_is_over_budget_true_when_over_cap(tmp_path):
    log = tmp_path / "u.jsonl"
    today = datetime.now(timezone.utc)
    # A million tokens of Sonnet output = $15
    _write(log, [{"ts": today.isoformat(), "model": "claude-sonnet-4-6",
                    "input_tokens": 0, "output_tokens": 1_000_000}])
    assert is_over_budget(log_path=log, cap_usd=10.0, now=today) is True
