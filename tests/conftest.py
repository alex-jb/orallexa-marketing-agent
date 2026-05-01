"""Session-wide test fixtures.

Prevent any test from accidentally writing to the user's real
~/.marketing_agent/ directory (post history, trend dedup memory,
etc.). Every test starts with a per-test temp DB + queue dir.
"""
from __future__ import annotations
import pytest


@pytest.fixture(autouse=True)
def _isolate_marketing_agent_state(tmp_path, monkeypatch):
    """Redirect SQLite + queue + usage-log paths to per-test tmp dirs.

    Without this, modules that fall back to defaults (PostMemory,
    TrendMemory, ApprovalQueue, USAGE_LOG_PATH) would share state
    across tests and contaminate the developer's home directory.
    """
    monkeypatch.setenv("MARKETING_AGENT_DB_PATH",
                          str(tmp_path / "history.db"))
    monkeypatch.setenv("MARKETING_AGENT_QUEUE",
                          str(tmp_path / "queue"))
    monkeypatch.setenv("MARKETING_AGENT_REFLECTIONS_JSONL",
                          str(tmp_path / "reflections.jsonl"))
    monkeypatch.setenv("MARKETING_AGENT_PREFERENCE_JSONL",
                          str(tmp_path / "preference-pairs.jsonl"))
    monkeypatch.setenv("SFOS_SKILLS_DIR",
                          str(tmp_path / "sfos-skills"))
    monkeypatch.setenv("SFOS_BANDIT_DB",
                          str(tmp_path / "sfos-bandit.sqlite"))
    # USAGE_LOG_PATH is a constant, not env-driven — patch it lazily
    # only if the test imports the cost module.
    import marketing_agent.cost as cost_mod
    monkeypatch.setattr(cost_mod, "USAGE_LOG_PATH",
                          tmp_path / "usage.jsonl")
