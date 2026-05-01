"""Tests for the trends-too integration inside scripts/daily_post.py.

Strategy: import _run_trends_for_projects directly, mock the
network-level aggregate() and the generate_posts call that
trends_to_drafts uses internally, run with a couple of fake
ProjectConfig objects, assert per-project drafts land in the queue.
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


# scripts/ is not a package — add it to sys.path for the import.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


from marketing_agent import ApprovalQueue, Post  # noqa: E402
from marketing_agent.multiproject import (  # noqa: E402
    ProjectConfig, TrendsConfig,
)
from marketing_agent.trends import TrendItem  # noqa: E402
import marketing_agent.trends_to_drafts as ttd_module  # noqa: E402

from daily_post import _run_trends_for_projects  # noqa: E402


def _stub_generate(synth_project, platforms, mode=None, subreddit=None):
    return [
        Post(platform=p, body=f"d({p.value})").with_count()
        for p in platforms
    ]


@pytest.fixture
def queue(tmp_path, monkeypatch):
    """Force ApprovalQueue to use a temp dir via env, so the script-level
    trends_to_drafts() path uses the same isolated queue."""
    qdir = tmp_path / "queue"
    monkeypatch.setenv("MARKETING_AGENT_QUEUE", str(qdir))
    return ApprovalQueue(root=qdir)


def test_run_trends_for_projects_fans_out_per_project(queue):
    cfgs = [
        ProjectConfig(name="Alpha", repo="me/alpha",
                       tagline="A trading agent",
                       platforms=["x"]),
        ProjectConfig(name="Beta", repo="me/beta",
                       tagline="A growth tool",
                       platforms=["x", "linkedin"]),
    ]
    tcfg = TrendsConfig(enabled=True, languages=["python"],
                          hn_query="agent",
                          subreddits=["MachineLearning"],
                          top_n=2, hours=72)

    items = [
        TrendItem(source="hn", title="t1", url="u1", score=100),
        TrendItem(source="hn", title="t2", url="u2", score=90),
    ]
    with patch("marketing_agent.trends.aggregate", return_value=items), \
         patch.object(ttd_module, "generate_posts",
                          side_effect=_stub_generate):
        total = _run_trends_for_projects(cfgs, tcfg, mode_str="template")

    # Alpha: 2 trends × 1 platform = 2; Beta: 2 trends × 2 platforms = 4
    assert total == 6


def test_run_trends_for_projects_returns_zero_when_no_items(queue):
    cfgs = [ProjectConfig(name="Alpha", repo="me/alpha",
                            tagline="t", platforms=["x"])]
    tcfg = TrendsConfig(enabled=True, top_n=3, hours=168)
    with patch("marketing_agent.trends.aggregate", return_value=[]):
        total = _run_trends_for_projects(cfgs, tcfg, mode_str="template")
    assert total == 0


def test_run_trends_for_projects_passes_subreddit_target(queue):
    captured = {}

    def capture(synth_project, platforms, mode=None, subreddit=None):
        captured.setdefault(synth_project.name, []).append(subreddit)
        return _stub_generate(synth_project, platforms, mode=mode,
                                  subreddit=subreddit)

    cfgs = [
        ProjectConfig(name="Alpha", repo="me/alpha", tagline="t",
                       platforms=["reddit"], subreddit="MachineLearning"),
    ]
    tcfg = TrendsConfig(enabled=True, top_n=1, hours=72)
    items = [TrendItem(source="hn", title="t1", url="u1", score=100)]

    with patch("marketing_agent.trends.aggregate", return_value=items), \
         patch.object(ttd_module, "generate_posts", side_effect=capture):
        _run_trends_for_projects(cfgs, tcfg, mode_str="template")

    assert captured["Alpha"] == ["MachineLearning"]


def test_run_trends_for_projects_aggregates_once(queue):
    """Network fetch (aggregate) must be a single call shared across all projects."""
    cfgs = [
        ProjectConfig(name=f"P{i}", repo=f"me/p{i}", tagline="t",
                       platforms=["x"]) for i in range(3)
    ]
    tcfg = TrendsConfig(enabled=True, top_n=1, hours=24)
    items = [TrendItem(source="hn", title="t1", url="u1", score=100)]

    with patch("marketing_agent.trends.aggregate", return_value=items) as mock_agg, \
         patch.object(ttd_module, "generate_posts",
                          side_effect=_stub_generate):
        _run_trends_for_projects(cfgs, tcfg, mode_str="template")

    assert mock_agg.call_count == 1
