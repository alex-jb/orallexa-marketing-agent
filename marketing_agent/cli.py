"""Command-line entry point: `python -m marketing_agent <subcommand>`.

Subcommands:
    generate    Generate posts (no posting). Outputs to stdout or queue.
    post        Read approval queue, post each approved file.
    history     Show recent posts and stats.
    cost        Show running cost summary.
    queue       List items in pending/approved/posted/rejected.
    plan        Generate a launch plan (markdown) for a project.
    replies     Suggest reply drafts for tweets in your timeline.
    engage      Pull current engagement metrics for a posted tweet.

Designed for both interactive use and cron / GitHub Actions invocation.
"""
from __future__ import annotations
import argparse
import os
import sys
from typing import Optional

from marketing_agent import (
    GenerationMode, Orchestrator, Platform, Project,
)
from marketing_agent.memory import PostMemory
from marketing_agent.cost import CostTracker
from marketing_agent.queue import ApprovalQueue
from marketing_agent.platforms.base import NotConfigured


def cmd_generate(args) -> int:
    """Generate posts and either print or send to approval queue."""
    project = Project(
        name=args.name,
        tagline=args.tagline,
        description=args.description,
        github_url=args.github,
        website_url=args.website,
        recent_changes=args.changes or [],
    )
    mode = {"template": GenerationMode.TEMPLATE, "llm": GenerationMode.LLM,
            "hybrid": GenerationMode.HYBRID}[args.mode]
    orch = Orchestrator(mode=mode)
    posts = orch.generate(project,
                            [Platform(p) for p in args.platforms],
                            subreddit=args.subreddit)

    if args.to_queue:
        q = ApprovalQueue()
        for p in posts:
            path = q.submit(p, args.name, generated_by=mode.value)
            print(f"📥 {path}")
        return 0

    for p in posts:
        print(orch.preview(p))
        print()
    return 0


def cmd_post(args) -> int:
    """Publish all files in the approved/ queue."""
    q = ApprovalQueue()
    mem = PostMemory()
    cost = CostTracker()
    approved = q.list_approved()
    if not approved:
        print("(no items in approved/ — nothing to post)")
        return 0
    orch = Orchestrator()
    failed = 0
    for path in approved:
        post, meta = q.load(path)
        project_name = meta.get("project", "unknown")
        if mem.has_posted(post):
            print(f"⏭  {path.name} — already posted (dedup), skipping")
            continue
        try:
            url = orch.post(post)
            mem.record(post, project_name=project_name, external_id=url)
            if post.platform == Platform.X:
                cost.log_x_post(project_name=project_name)
            q.mark_posted(path, external_id=url)
            print(f"✅ {path.name} → {url}")
        except NotConfigured as e:
            print(f"⏭  {path.name} — {e}")
        except Exception as e:
            print(f"❌ {path.name} — {type(e).__name__}: {e}")
            failed += 1
    return 1 if failed else 0


def cmd_history(args) -> int:
    mem = PostMemory()
    rows = mem.recent(project_name=args.project,
                       platform=Platform(args.platform) if args.platform else None,
                       limit=args.limit)
    if not rows:
        print("(no history)")
        return 0
    for r in rows:
        print(f"{r['posted_at']}  {r['platform']:10s}  {r['project_name']:25s}  "
              f"{r['external_id'] or ''}")
    print(f"\nstats: {mem.stats()}")
    return 0


def cmd_cost(args) -> int:
    cost = CostTracker()
    total = cost.total(project_name=args.project, since_iso=args.since)
    by_cat = cost.by_category()
    print(f"💰 total cost: ${total:.4f}")
    if args.project:
        print(f"   filter: project={args.project}")
    if args.since:
        print(f"   filter: since={args.since}")
    for cat, c in sorted(by_cat.items()):
        print(f"   {cat:12s}  ${c:.4f}")
    return 0


def cmd_queue(args) -> int:
    q = ApprovalQueue()
    for sub in ("pending", "approved", "posted", "rejected"):
        files = sorted((q.root / sub).glob("*.md"))
        print(f"\n{sub} ({len(files)})")
        for f in files[-args.limit:]:
            print(f"  {f.name}")
    return 0


def cmd_plan(args) -> int:
    """Generate a launch plan markdown file."""
    from marketing_agent.strategy import write_plan
    project = Project(name=args.name, tagline=args.tagline,
                       description=args.description, tags=args.tags or [])
    use_llm = args.mode == "llm"
    path = write_plan(project, days=args.days, use_llm=use_llm,
                       out_dir=args.out_dir)
    print(f"📋 Plan written: {path}")
    return 0


def cmd_replies(args) -> int:
    """Generate reply drafts for tweets from given handles → approval queue."""
    from marketing_agent.reply_suggester import suggest_replies_to_queue
    paths = suggest_replies_to_queue(
        args.handles, keywords=args.keywords or None,
        hours=args.hours, min_engagement=args.min_engagement,
        project_name=args.project, use_llm=(args.mode != "template"),
    )
    if not paths:
        print("(no relevant tweets found, or X not configured)")
    for p in paths:
        print(f"📥 {p}")
    return 0


def cmd_engage(args) -> int:
    """Pull current engagement metrics for a tweet via X API."""
    from marketing_agent.engagement import EngagementTracker
    t = EngagementTracker()
    events = t.fetch_x_metrics(args.post_id)
    if not events:
        print("(no metrics — X not configured or tweet not found)")
        return 1
    for e in events:
        print(f"  {e.metric:10s}  {e.count}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="marketing_agent",
        description="AI marketing agent for OSS founders.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="Generate posts")
    g.add_argument("--name", required=True)
    g.add_argument("--tagline", required=True)
    g.add_argument("--description", default=None)
    g.add_argument("--github", default=None)
    g.add_argument("--website", default=None)
    g.add_argument("--changes", nargs="*", default=None)
    g.add_argument("--platforms", nargs="+",
                    default=["x", "reddit", "linkedin"])
    g.add_argument("--subreddit", default=None)
    g.add_argument("--mode", choices=["template", "llm", "hybrid"], default="hybrid")
    g.add_argument("--to-queue", action="store_true",
                    help="Send to approval queue instead of stdout")
    g.set_defaults(func=cmd_generate)

    p = sub.add_parser("post", help="Publish approved queue items")
    p.set_defaults(func=cmd_post)

    h = sub.add_parser("history", help="Show recent post history")
    h.add_argument("--project", default=None)
    h.add_argument("--platform", default=None)
    h.add_argument("--limit", type=int, default=20)
    h.set_defaults(func=cmd_history)

    c = sub.add_parser("cost", help="Show cost summary")
    c.add_argument("--project", default=None)
    c.add_argument("--since", default=None,
                    help="ISO datetime, e.g. 2026-04-01T00:00:00")
    c.set_defaults(func=cmd_cost)

    qcmd = sub.add_parser("queue", help="List approval queue contents")
    qcmd.add_argument("--limit", type=int, default=10)
    qcmd.set_defaults(func=cmd_queue)

    pl = sub.add_parser("plan", help="Generate a launch plan (markdown)")
    pl.add_argument("--name", required=True)
    pl.add_argument("--tagline", required=True)
    pl.add_argument("--description", default=None)
    pl.add_argument("--tags", nargs="*", default=None)
    pl.add_argument("--days", type=int, default=30)
    pl.add_argument("--mode", choices=["template", "llm"], default="template")
    pl.add_argument("--out-dir", default="docs")
    pl.set_defaults(func=cmd_plan)

    r = sub.add_parser("replies", help="Generate reply drafts to your timeline")
    r.add_argument("--handles", nargs="+", required=True)
    r.add_argument("--keywords", nargs="*", default=None)
    r.add_argument("--hours", type=int, default=24)
    r.add_argument("--min-engagement", type=int, default=5)
    r.add_argument("--project", default="engagement")
    r.add_argument("--mode", choices=["template", "llm", "hybrid"], default="hybrid")
    r.set_defaults(func=cmd_replies)

    e = sub.add_parser("engage", help="Pull current engagement metrics for a tweet")
    e.add_argument("--post-id", required=True)
    e.set_defaults(func=cmd_engage)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
