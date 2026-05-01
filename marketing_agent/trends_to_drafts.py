"""trends_to_drafts — close the proactive loop.

v0.15 added `trends.py`: scrape GitHub / HN / Reddit and emit a markdown
digest of what's trending in your niche. That was *reactive* — the human
still had to open the digest and decide what to write about.

v0.17 closes the loop: take the top N trending items, generate a draft
post per (trend × platform) using the existing `content/generator`
pipeline, and submit each draft into the `ApprovalQueue` for human
review. The full reactive→proactive content path now runs automatically
on the daily cron.

Why route through the existing generator?
  - Reuses the entire content stack for free: ICPL preference few-shots,
    Cloudflare edge tier, prompt caching, per-platform voice guides,
    cross-provider usage logging.
  - The critic + semantic-dedup gate already runs inside
    `ApprovalQueue.submit()` — bad/duplicate trend takes get rejected
    before they hit pending/.
  - Same observability + cost telemetry as commit-driven posts.

Usage:
    from marketing_agent.trends_to_drafts import trends_to_drafts
    results = trends_to_drafts(
        project=Project(name="Orallexa", tagline="..."),
        platforms=[Platform.X, Platform.LINKEDIN],
        github_languages=["python"],
        hn_query="agent",
        subreddits=["MachineLearning"],
        top_n=5,
    )
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from marketing_agent.content.generator import generate_posts
from marketing_agent.logging import get_logger
from marketing_agent.queue import ApprovalQueue
from marketing_agent.trend_memory import TrendMemory
from marketing_agent.trends import TrendItem, aggregate
from marketing_agent.types import GenerationMode, Platform, Project

log = get_logger(__name__)


@dataclass
class DraftResult:
    """One trend → the queue paths produced for it."""
    trend: TrendItem
    queued_paths: list[Path] = field(default_factory=list)


def _project_with_trend(base: Project, trend: TrendItem) -> Project:
    """Build a per-trend synthetic Project.

    The user's real project stays the primary subject. The trend lands as
    a hook line at the top of `recent_changes`, plus an instruction in
    the description telling the LLM to connect the project's angle to
    the trending topic — without pretending the trend is theirs.
    """
    hook = f"Trending now ({trend.source}): {trend.title}"
    if trend.summary:
        hook += f" — {trend.summary[:160]}"
    if trend.url:
        hook += f" [{trend.url}]"

    framing = (
        "\n\nTask: write a post that connects this project's angle to a "
        "currently-trending topic in our niche (listed first under "
        "'recent changes'). Be honest — name the trend, share a take, "
        "link back to what the project is doing in this space. Do not "
        "claim the trend as the project's own work."
    )
    new_desc = (base.description or "") + framing
    return Project(
        name=base.name,
        tagline=base.tagline,
        description=new_desc,
        github_url=base.github_url,
        website_url=base.website_url,
        tags=base.tags,
        target_audience=base.target_audience,
        recent_changes=[hook] + list(base.recent_changes or []),
    )


def trends_to_drafts(
    project: Project,
    platforms: list[Platform],
    *,
    github_languages: Optional[list[str]] = None,
    hn_query: str = "",
    subreddits: Optional[list[str]] = None,
    hours: int = 168,
    top_n: int = 5,
    mode: GenerationMode = GenerationMode.HYBRID,
    queue: Optional[ApprovalQueue] = None,
    gate: bool = True,
    items: Optional[list[TrendItem]] = None,
    subreddit_target: Optional[str] = None,
    dedup_days: int = 7,
    memory: Optional[TrendMemory] = None,
    n_variants: int = 1,
) -> list[DraftResult]:
    """Aggregate trends → top N → generate drafts → submit to queue.

    Args:
        project:           the user's real project (kept as primary subject).
        platforms:         which platforms to fan out across per trend.
        github_languages:  see `trends.aggregate()`.
        hn_query:          see `trends.aggregate()`.
        subreddits:        see `trends.aggregate()`.
        hours:             lookback window in hours for trend aggregation.
        top_n:             how many fresh top trends to convert into drafts.
        mode:              GenerationMode.HYBRID (default) | LLM | TEMPLATE.
        queue:             override ApprovalQueue for testing.
        gate:              run critic + dedup gate on each draft (default on).
        items:             pre-aggregated TrendItems; skips network fetch.
        subreddit_target:  Reddit subreddit slug (passed through to generator).
        dedup_days:        skip trends whose URL was already drafted for THIS
                              project within this many days (default 7). Set to 0
                              to disable trend-URL memory entirely.
        memory:            override TrendMemory for testing.

    Trend-URL dedup: each successful (trend, any platform) draft marks
    the trend URL as "drafted for this project today". The next time
    aggregate() returns the same trend (very common with hot HN stories),
    it is filtered before generation and never burns LLM tokens.

    Returns one DraftResult per processed trend (only fresh ones — stale
    trends are dropped before generation, not returned).
    """
    if items is None:
        items = aggregate(
            github_languages=github_languages,
            hn_query=hn_query,
            subreddits=subreddits,
            hours=hours,
        )
    if not items:
        log.info("trends_to_drafts: no trending items; nothing to draft")
        return []

    mem = memory if memory is not None else (
        TrendMemory() if dedup_days > 0 else None
    )
    if mem is not None:
        before = len(items)
        items = mem.filter_fresh(items, project.name, days=dedup_days)
        skipped = before - len(items)
        if skipped:
            log.info(
                "trends_to_drafts: skipped %d stale trend(s) already drafted "
                "for %r within last %d days", skipped, project.name, dedup_days,
            )

    top = items[:top_n]
    q = queue or ApprovalQueue()
    out: list[DraftResult] = []

    for trend in top:
        synth = _project_with_trend(project, trend)
        try:
            posts = generate_posts(
                synth, platforms, mode=mode, subreddit=subreddit_target,
                n_variants=n_variants,
            )
        except Exception as e:
            log.warning(
                "trends_to_drafts: generate_posts failed for trend %r: %s",
                trend.title, e,
            )
            out.append(DraftResult(trend=trend, queued_paths=[]))
            continue

        result = DraftResult(trend=trend)
        for post in posts:
            try:
                path = q.submit(
                    post,
                    project_name=project.name,
                    generated_by="trends",
                    gate=gate,
                )
                result.queued_paths.append(path)
            except Exception as e:
                log.warning(
                    "trends_to_drafts: queue.submit failed for "
                    "(trend=%r, platform=%s): %s",
                    trend.title, post.platform.value, e,
                )
        # Mark the trend URL as drafted for this project — even if some
        # platforms failed, others succeeded and one draft is enough to
        # cool this trend down for the dedup window.
        if mem is not None and result.queued_paths and trend.url:
            mem.mark_drafted(trend.url, project.name)
        out.append(result)

    return out
