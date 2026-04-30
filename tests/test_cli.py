"""CLI smoke tests — verify subcommand wiring + arg parsing.

Strategy: call `main()` with various argv lists. We don't assert on
output (that's brittle); we assert on exit codes + that the right
underlying function got called.
"""
from __future__ import annotations
from pathlib import Path

import pytest

from marketing_agent import cli


# ──────────────── help / --version paths ────────────────


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["--help"])
    assert e.value.code == 0


def test_no_subcommand_errors():
    with pytest.raises(SystemExit) as e:
        cli.main([])
    assert e.value.code != 0


def test_invalid_subcommand_errors():
    with pytest.raises(SystemExit) as e:
        cli.main(["nonsense"])
    assert e.value.code != 0


# ──────────────── generate ────────────────


def test_generate_template_mode_runs(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    rc = cli.main([
        "generate",
        "--name", "T", "--tagline", "tagline",
        "--platforms", "x",
        "--mode", "template",
    ])
    assert rc == 0


def test_generate_with_to_queue(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("MARKETING_AGENT_QUEUE", str(tmp_path / "q"))
    rc = cli.main([
        "generate",
        "--name", "T", "--tagline", "tagline",
        "--platforms", "x",
        "--mode", "template",
        "--to-queue",
    ])
    assert rc == 0
    # At least one file should have been written into pending/ or rejected/
    pending = list((tmp_path / "q" / "pending").glob("*.md"))
    rejected = list((tmp_path / "q" / "rejected").glob("*.md"))
    assert pending or rejected


# ──────────────── queue ────────────────


def test_queue_list_runs_on_empty_root(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("MARKETING_AGENT_QUEUE", str(tmp_path / "q"))
    rc = cli.main(["queue"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "pending" in out
    assert "approved" in out


# ──────────────── plan ────────────────


def test_plan_template_mode_writes_file(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    rc = cli.main([
        "plan",
        "--name", "Demo",
        "--tagline", "test",
        "--days", "30",
        "--mode", "template",
        "--out-dir", str(tmp_path),
    ])
    assert rc == 0
    files = list(tmp_path.glob("launch_plan_*.md"))
    assert len(files) == 1
    assert "Demo" in files[0].read_text()


# ──────────────── best-time ────────────────


def test_best_time_runs(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MARKETING_AGENT_DB_PATH", str(tmp_path / "h.db"))
    rc = cli.main(["best-time", "--platform", "x"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "optimal post time for x" in out


# ──────────────── bandit ────────────────


def test_bandit_stats_runs_on_empty_db(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MARKETING_AGENT_DB_PATH", str(tmp_path / "h.db"))
    rc = cli.main(["bandit", "stats"])
    assert rc == 0


def test_bandit_update_records(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MARKETING_AGENT_DB_PATH", str(tmp_path / "h.db"))
    rc = cli.main(["bandit", "update", "x:emoji-led", "--reward", "0.7"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "x:emoji-led" in out


# ──────────────── image ────────────────


def test_image_subcommand_returns_url(capsys):
    rc = cli.main([
        "image",
        "--name", "T",
        "--tagline", "tagline",
        "--platform", "x",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "image.pollinations.ai" in out


def test_image_suggest_only_prints_prompt(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    rc = cli.main([
        "image",
        "--name", "T",
        "--tagline", "tagline",
        "--platform", "x",
        "--suggest-only",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    # Template prompt must include either tagline or aspect ratio
    assert "16:9" in out or "tagline" in out.lower()


# ──────────────── schedule ────────────────


def _make_queue_file(path: Path, body: str = "test body") -> Path:
    path.write_text(
        "---\n"
        "platform: x\n"
        "project: t\n"
        "generated_by: human\n"
        "char_count: 9\n"
        "---\n"
        f"{body}\n"
    )
    return path


def test_schedule_at_iso_sets_frontmatter(tmp_path, capsys):
    f = _make_queue_file(tmp_path / "x.md")
    rc = cli.main([
        "schedule",
        "--file", str(f),
        "--at", "2026-05-04T13:00:00Z",
    ])
    assert rc == 0
    assert "scheduled_for: 2026-05-04T13:00:00+00:00" in f.read_text()


def test_schedule_best_time_sets_frontmatter(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKETING_AGENT_DB_PATH", str(tmp_path / "h.db"))
    f = _make_queue_file(tmp_path / "x.md")
    rc = cli.main([
        "schedule",
        "--file", str(f),
        "--best-time",
        "--platform", "x",
    ])
    assert rc == 0
    assert "scheduled_for:" in f.read_text()


def test_schedule_missing_args_errors(tmp_path):
    f = _make_queue_file(tmp_path / "x.md")
    rc = cli.main(["schedule", "--file", str(f)])
    assert rc != 0


def test_schedule_missing_file_errors(tmp_path):
    rc = cli.main([
        "schedule",
        "--file", str(tmp_path / "doesnt-exist.md"),
        "--at", "2026-05-04T13:00:00Z",
    ])
    assert rc != 0


# ──────────────── trends ────────────────


def test_trends_runs_with_mocked_sources(monkeypatch, capsys):
    """`marketing-agent trends` should produce a markdown digest."""
    import marketing_agent.trends as tr
    from marketing_agent.trends import TrendItem
    monkeypatch.setattr(tr, "trending_github_repos",
                          lambda **k: [TrendItem(source="github",
                                                    title="owner/repo",
                                                    url="https://github.com/owner/repo",
                                                    score=500)])
    monkeypatch.setattr(tr, "trending_hn_posts", lambda **k: [])
    monkeypatch.setattr(tr, "trending_subreddit_posts", lambda *a, **k: [])
    rc = cli.main([
        "trends", "--languages", "python",
        "--hours", "24", "--limit", "5",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Trends digest" in out
    assert "owner/repo" in out


# ──────────────── ui (graceful no-streamlit) ────────────────


def test_ui_subcommand_when_streamlit_missing(monkeypatch, capsys):
    """Without streamlit, ui subcommand prints help and exits 2."""
    import marketing_agent.web_ui as wu
    monkeypatch.setattr(wu, "_is_streamlit_available", lambda: False)
    rc = cli.main(["ui"])
    assert rc == 2
