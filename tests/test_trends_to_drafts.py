"""Tests for trends_to_drafts — close the proactive loop.

Strategy: feed pre-built TrendItems via the `items=` kwarg (no network),
mock generate_posts to return deterministic Posts, and verify drafts land
in the queue's pending/ folder with generated_by=trends.
"""
from __future__ import annotations
from pathlib import Path
from unittest.mock import patch

import pytest

from marketing_agent import (
    ApprovalQueue, GenerationMode, Platform, Post, Project,
)
from marketing_agent.trends import TrendItem
import marketing_agent.trends_to_drafts as ttd_module
from marketing_agent.trends_to_drafts import (
    DraftResult, _project_with_trend, trends_to_drafts,
)


@pytest.fixture
def queue(tmp_path):
    return ApprovalQueue(root=tmp_path / "queue")


@pytest.fixture
def project():
    return Project(
        name="Orallexa",
        tagline="Self-tuning multi-agent AI trading OS",
        description="Quant trading agents.",
        recent_changes=["v0.5: added bandit"],
    )


@pytest.fixture
def trend_items():
    return [
        TrendItem(source="github", title="acme/agent-thing",
                    url="https://github.com/acme/agent-thing", score=420,
                    summary="An agent that does the thing"),
        TrendItem(source="hn", title="LLM agents are eating ops",
                    url="https://news.ycombinator.com/item?id=1", score=300),
        TrendItem(source="reddit", title="Best multi-agent stack right now?",
                    url="https://reddit.com/r/MachineLearning/comments/x", score=80),
    ]


# ───────────────── _project_with_trend ─────────────────


def test_project_with_trend_keeps_user_project_as_subject(project, trend_items):
    synth = _project_with_trend(project, trend_items[0])
    assert synth.name == project.name
    assert synth.tagline == project.tagline
    # Trend hook is FIRST in recent_changes, original commits follow.
    assert synth.recent_changes[0].startswith("Trending now (github):")
    assert "acme/agent-thing" in synth.recent_changes[0]
    assert synth.recent_changes[1] == "v0.5: added bandit"


def test_project_with_trend_appends_framing_instruction(project, trend_items):
    synth = _project_with_trend(project, trend_items[1])
    assert "connects this project's angle to a currently-trending topic" in (
        synth.description or ""
    )
    # Original description must be preserved.
    assert (synth.description or "").startswith("Quant trading agents.")


def test_project_with_trend_handles_missing_description(trend_items):
    bare = Project(name="X", tagline="t")
    synth = _project_with_trend(bare, trend_items[0])
    assert synth.description is not None
    assert "currently-trending topic" in synth.description


def test_project_with_trend_includes_url_when_present(project, trend_items):
    synth = _project_with_trend(project, trend_items[0])
    assert "https://github.com/acme/agent-thing" in synth.recent_changes[0]


# ───────────────── trends_to_drafts ─────────────────


def _stub_generate(synth_project, platforms, mode=None, subreddit=None):
    # Return one Post per platform; body references the trend so we can
    # assert later that synth_project carried the hook through.
    hook_line = synth_project.recent_changes[0] if synth_project.recent_changes else ""
    return [
        Post(platform=p, body=f"draft for {p.value}: {hook_line[:50]}").with_count()
        for p in platforms
    ]


def test_trends_to_drafts_happy_path(queue, project, trend_items):
    with patch.object(ttd_module, "generate_posts",
                  side_effect=_stub_generate):
        results = trends_to_drafts(
            project=project,
            platforms=[Platform.X, Platform.LINKEDIN],
            items=trend_items,
            top_n=3,
            mode=GenerationMode.TEMPLATE,
            queue=queue,
            gate=False,
        )
    assert len(results) == 3
    # 3 trends × 2 platforms = 6 drafts
    total = sum(len(r.queued_paths) for r in results)
    assert total == 6
    # All in pending/
    for r in results:
        for p in r.queued_paths:
            assert p.parent.name == "pending"


def test_trends_to_drafts_marks_generated_by_trends(queue, project, trend_items):
    with patch.object(ttd_module, "generate_posts",
                  side_effect=_stub_generate):
        results = trends_to_drafts(
            project=project, platforms=[Platform.X],
            items=trend_items[:1], top_n=1,
            mode=GenerationMode.TEMPLATE, queue=queue, gate=False,
        )
    queued = results[0].queued_paths[0]
    text = queued.read_text()
    assert "generated_by: trends" in text


def test_trends_to_drafts_respects_top_n(queue, project, trend_items):
    with patch.object(ttd_module, "generate_posts",
                  side_effect=_stub_generate):
        results = trends_to_drafts(
            project=project, platforms=[Platform.X],
            items=trend_items, top_n=2,
            mode=GenerationMode.TEMPLATE, queue=queue, gate=False,
        )
    assert len(results) == 2  # not 3


def test_trends_to_drafts_empty_items_returns_empty(queue, project):
    with patch.object(ttd_module, "aggregate", return_value=[]):
        results = trends_to_drafts(
            project=project, platforms=[Platform.X],
            mode=GenerationMode.TEMPLATE, queue=queue, gate=False,
        )
    assert results == []


def test_trends_to_drafts_calls_aggregate_when_items_not_passed(queue, project):
    with patch.object(ttd_module, "aggregate",
                  return_value=[]) as mock_agg, \
         patch.object(ttd_module, "generate_posts",
                 side_effect=_stub_generate):
        trends_to_drafts(
            project=project, platforms=[Platform.X],
            github_languages=["python"], hn_query="agent",
            subreddits=["MachineLearning"], hours=72,
            queue=queue, gate=False,
        )
    mock_agg.assert_called_once()
    kwargs = mock_agg.call_args.kwargs
    assert kwargs["github_languages"] == ["python"]
    assert kwargs["hn_query"] == "agent"
    assert kwargs["subreddits"] == ["MachineLearning"]
    assert kwargs["hours"] == 72


def test_trends_to_drafts_per_trend_failure_does_not_crash(queue, project, trend_items):
    """If generator raises for one trend, others still succeed."""
    call_count = {"n": 0}

    def flaky(synth_project, platforms, mode=None, subreddit=None):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("boom")
        return _stub_generate(synth_project, platforms, mode=mode,
                                  subreddit=subreddit)

    with patch.object(ttd_module, "generate_posts",
                  side_effect=flaky):
        results = trends_to_drafts(
            project=project, platforms=[Platform.X],
            items=trend_items, top_n=3,
            mode=GenerationMode.TEMPLATE, queue=queue, gate=False,
        )
    # 3 results returned, but one has zero queued_paths.
    assert len(results) == 3
    failed = [r for r in results if not r.queued_paths]
    assert len(failed) == 1


def test_trends_to_drafts_passes_subreddit_target_to_generator(queue, project, trend_items):
    captured = {}

    def capture(synth_project, platforms, mode=None, subreddit=None):
        captured["subreddit"] = subreddit
        return _stub_generate(synth_project, platforms, mode=mode,
                                  subreddit=subreddit)

    with patch.object(ttd_module, "generate_posts",
                  side_effect=capture):
        trends_to_drafts(
            project=project, platforms=[Platform.REDDIT],
            items=trend_items[:1], top_n=1,
            mode=GenerationMode.TEMPLATE, queue=queue, gate=False,
            subreddit_target="MachineLearning",
        )
    assert captured["subreddit"] == "MachineLearning"


def test_draft_result_dataclass_default_paths_is_empty():
    item = TrendItem(source="hn", title="x", url="u", score=1)
    r = DraftResult(trend=item)
    assert r.queued_paths == []
