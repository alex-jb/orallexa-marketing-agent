"""Smoke + integration tests for the MCP server module.

Strategy:
  - Server smoke: module imports + main() degrades when fastmcp absent
  - Tool integration: each tool_* implementation is unit-testable directly
    (we extracted them from inside main() in v0.9 specifically for this).
    These tests verify the tools' behavior end-to-end through real
    Orchestrator / EngagementTracker / queue paths.
"""
from __future__ import annotations
import sys



# ───────────────── server smoke ─────────────────


def test_module_imports():
    """Module must import even without fastmcp installed."""
    from marketing_agent import mcp_server  # noqa: F401


def test_main_returns_2_when_fastmcp_missing(monkeypatch, capsys):
    """If fastmcp is not installed, main() should print a helpful error and exit 2."""
    monkeypatch.setitem(sys.modules, "fastmcp", None)
    from marketing_agent.mcp_server import main
    rc = main()
    assert rc == 2
    err = capsys.readouterr().err
    assert "fastmcp" in err
    assert "pip install" in err


# ───────────────── tool integration tests ─────────────────


def test_tool_draft_posts_returns_dict_per_platform(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from marketing_agent.mcp_server import tool_draft_posts
    out = tool_draft_posts(
        name="TestProj", tagline="A test for MCP draft tool",
        platforms=["x", "linkedin"], mode="template",
    )
    assert len(out) == 2
    plats = {p["platform"] for p in out}
    assert plats == {"x", "linkedin"}
    for p in out:
        assert p["body"]
        assert p["char_count"] > 0


def test_tool_draft_posts_with_variants(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from marketing_agent.mcp_server import tool_draft_posts
    out = tool_draft_posts(
        name="X", tagline="t", platforms=["x"], mode="template", n_variants=3,
    )
    # Even with variants=3, returns one chosen post per platform
    assert len(out) == 1
    # Bandit picks one of the 3 X variants
    assert out[0]["variant_key"] in ("x:emoji-led", "x:question-led", "x:stat-led")


def test_tool_submit_and_list_queue(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKETING_AGENT_QUEUE", str(tmp_path / "q"))
    from marketing_agent.mcp_server import tool_list_queue, tool_submit_to_queue
    path = tool_submit_to_queue(
        platform="x",
        body="A solid post about marketing-agent v0.9 release notes today.",
        project_name="test",
    )
    # File ends up in either pending/ or rejected/ depending on critic gate
    assert any(d in path for d in ("pending", "rejected"))
    items = tool_list_queue("pending") + tool_list_queue("rejected")
    assert any(i.endswith(".md") for i in items)


def test_tool_list_queue_invalid_status_returns_error_string(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKETING_AGENT_QUEUE", str(tmp_path / "q"))
    from marketing_agent.mcp_server import tool_list_queue
    out = tool_list_queue("nonsense")
    assert any("invalid status" in s for s in out)


def test_tool_optimal_time_returns_default_without_history(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKETING_AGENT_DB_PATH", str(tmp_path / "h.db"))
    from marketing_agent.mcp_server import tool_optimal_time
    out = tool_optimal_time(platform="x")
    assert "weekday" in out
    assert out["source"] in ("default", "data")
    assert 0 <= out["hour_utc"] <= 23


def test_tool_bandit_stats_returns_list(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKETING_AGENT_DB_PATH", str(tmp_path / "h.db"))
    from marketing_agent.mcp_server import tool_bandit_stats
    stats = tool_bandit_stats()
    assert isinstance(stats, list)


def test_tool_engagement_top_returns_list(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKETING_AGENT_DB_PATH", str(tmp_path / "h.db"))
    from marketing_agent.mcp_server import tool_engagement_top
    out = tool_engagement_top()
    assert isinstance(out, list)


def test_tool_launch_plan_writes_file(tmp_path):
    from marketing_agent.mcp_server import tool_launch_plan
    path = tool_launch_plan(
        name="Demo", tagline="t", days=30, out_dir=str(tmp_path),
        use_llm=False,
    )
    from pathlib import Path
    assert Path(path).exists()
    assert "Demo" in Path(path).read_text()
