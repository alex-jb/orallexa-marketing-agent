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
                            subreddit=args.subreddit,
                            n_variants=args.variants)

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
    """Publish approved/ items whose scheduled_for is due (or unset)."""
    from marketing_agent.schedule import filter_due, get_scheduled_for
    q = ApprovalQueue()
    mem = PostMemory()
    cost = CostTracker()
    all_approved = q.list_approved()
    if not all_approved:
        print("(no items in approved/ — nothing to post)")
        return 0

    due = filter_due(all_approved)
    waiting = [p for p in all_approved if p not in due]
    if waiting:
        print(f"⏰ {len(waiting)} item(s) waiting on schedule:")
        for p in waiting:
            sf = get_scheduled_for(p)
            print(f"   {p.name} @ {sf.isoformat() if sf else '(unscheduled)'}")
    if not due:
        return 0

    orch = Orchestrator()
    failed = 0
    for path in due:
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
    path = write_plan(project, days=args.days,
                       ph_launch_day=args.ph_launch_day,
                       use_llm=use_llm, out_dir=args.out_dir)
    print(f"📋 Plan written: {path}")
    return 0


def cmd_schedule(args) -> int:
    """Set scheduled_for on a queue file. Either explicit --at or --best-time."""
    from pathlib import Path
    from marketing_agent.schedule import (
        parse_iso, schedule_via_best_time, set_scheduled_for,
    )
    path = Path(args.file)
    if not path.exists():
        print(f"❌ not found: {path}")
        return 1
    if args.best_time:
        plat = Platform(args.platform) if args.platform else None
        if plat is None:
            print("❌ --best-time requires --platform")
            return 1
        when = schedule_via_best_time(path, plat, project_name=args.project)
        print(f"⏰ scheduled {path.name} for {when.isoformat()} (best-time CDF)")
        return 0
    if args.at:
        when = parse_iso(args.at)
        set_scheduled_for(path, when)
        print(f"⏰ scheduled {path.name} for {when.isoformat()}")
        return 0
    print("❌ provide either --at <iso> or --best-time --platform <p>")
    return 1


def cmd_ui(args) -> int:
    """Launch the Streamlit queue UI in the default browser."""
    from marketing_agent.web_ui import run_app
    return run_app(port=args.port)


def cmd_image(args) -> int:
    """Generate (or suggest) a cover image for a post."""
    from marketing_agent.content.images import generate_image, suggest_image_prompt
    project = Project(name=args.name, tagline=args.tagline,
                       description=args.description)
    plat = Platform(args.platform)
    if args.suggest_only:
        prompt = suggest_image_prompt(project, platform=plat, style=args.style)
        print(prompt)
        return 0
    result = generate_image(project, platform=plat, style=args.style,
                              prompt_override=args.prompt, model=args.model)
    if not result["url"]:
        print(f"❌ Image generation failed (backend={result['backend']})")
        print(f"   Prompt was: {result['prompt']}")
        return 1
    print(f"🖼  {result['url']}")
    print(f"   {result['width']}×{result['height']}  ·  backend={result['backend']}")
    print(f"   prompt: {result['prompt'][:120]}{'...' if len(result['prompt']) > 120 else ''}")
    return 0


def cmd_bandit(args) -> int:
    """Inspect or update the variant bandit."""
    from marketing_agent.bandit import VariantBandit
    b = VariantBandit()
    if args.action == "stats":
        rows = b.stats()
        if not rows:
            print("(no arms yet — generate with --variants > 1 first)")
            return 0
        print(f"  {'variant':25s}  {'pulls':>5s}  {'mean':>6s}  {'α':>6s}  {'β':>6s}")
        for r in rows:
            print(f"  {r['variant_key']:25s}  {r['n_pulls']:>5d}  "
                  f"{r['mean']:>6.3f}  {r['alpha']:>6.2f}  {r['beta']:>6.2f}")
        return 0
    if args.action == "update":
        b.update(args.variant_key, reward=args.reward)
        print(f"✓ updated {args.variant_key} with reward={args.reward}")
        return 0
    if args.action == "from-engagement":
        r = b.update_from_engagement(args.variant_key, raw_engagement=args.engagement)
        print(f"✓ updated {args.variant_key} with squashed reward={r:.3f} "
              f"(from raw engagement {args.engagement})")
        return 0
    return 1


def cmd_best_time(args) -> int:
    """Show optimal post time per platform based on engagement history."""
    from marketing_agent.best_time import optimal_post_time, report
    weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    plat = Platform(args.platform)
    wd, h, src = optimal_post_time(plat, project_name=args.project,
                                     metric=args.metric,
                                     min_samples=args.min_samples)
    print(f"⏰ optimal post time for {plat.value}: "
          f"{weekdays[wd]} {h:02d}:00 UTC  ({src})")
    if args.verbose:
        rows = report(plat, project_name=args.project, metric=args.metric)
        if rows:
            print("\n   weekday  hour  n  mean_reward")
            for r in rows[:10]:
                print(f"   {r['weekday']:7s}  {r['hour_utc']:02d}    "
                      f"{r['n_samples']:2d}  {r['mean_reward']}")
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
    g.add_argument("--variants", type=int, default=1,
                    help="Generate N stylistic variants per platform; "
                         "bandit picks one (currently only X has multiple variants)")
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
    pl.add_argument("--days", type=int, default=30,
                     help="Plan duration. 30 / 60 / 90 supported.")
    pl.add_argument("--ph-launch-day", type=int, default=0,
                     help="Day offset of Product Hunt launch (default 0 = today). "
                          "HN/Show HN/long-form retros schedule relative to this.")
    pl.add_argument("--mode", choices=["template", "llm"], default="template")
    pl.add_argument("--out-dir", default="docs")
    pl.set_defaults(func=cmd_plan)

    sc = sub.add_parser("schedule", help="Schedule a queue file for a specific time")
    sc.add_argument("--file", required=True,
                     help="Path to a queue/*.md file")
    sc.add_argument("--at", default=None,
                     help="ISO datetime, e.g. 2026-05-04T13:00:00Z")
    sc.add_argument("--best-time", action="store_true",
                     help="Auto-pick the next occurrence of the best hour for "
                          "this platform from the engagement DB CDF")
    sc.add_argument("--platform", default=None,
                     choices=[p.value for p in Platform],
                     help="Required when --best-time is used")
    sc.add_argument("--project", default=None,
                     help="Optional: filter best-time CDF by project_name")
    sc.set_defaults(func=cmd_schedule)

    u = sub.add_parser("ui", help="Open the Streamlit queue UI in a browser")
    u.add_argument("--port", type=int, default=8501)
    u.set_defaults(func=cmd_ui)

    img = sub.add_parser("image", help="Generate a cover image for a post")
    img.add_argument("--name", required=True)
    img.add_argument("--tagline", required=True)
    img.add_argument("--description", default=None)
    img.add_argument("--platform", default="x",
                      choices=[p.value for p in Platform])
    img.add_argument("--style", default="minimalist",
                      help="Visual style hint passed to the image prompt")
    img.add_argument("--model", default="flux",
                      help="Pollinations model: flux | flux-realism | turbo")
    img.add_argument("--prompt", default=None,
                      help="Override the auto-generated prompt with this exact string")
    img.add_argument("--suggest-only", action="store_true",
                      help="Just print the prompt; don't generate an image URL")
    img.set_defaults(func=cmd_image)

    bd = sub.add_parser("bandit", help="Inspect / train the variant bandit")
    bd_sub = bd.add_subparsers(dest="action", required=True)
    bd_sub.add_parser("stats", help="Show per-arm posterior")
    bd_up = bd_sub.add_parser("update", help="Manually update an arm with a reward in [0,1]")
    bd_up.add_argument("variant_key")
    bd_up.add_argument("--reward", type=float, required=True)
    bd_eng = bd_sub.add_parser("from-engagement",
                                help="Update an arm from raw engagement count")
    bd_eng.add_argument("variant_key")
    bd_eng.add_argument("--engagement", type=float, required=True)
    bd.set_defaults(func=cmd_bandit)

    bt = sub.add_parser("best-time", help="Show optimal post time per platform")
    bt.add_argument("--platform", required=True,
                     choices=[p.value for p in Platform])
    bt.add_argument("--project", default=None,
                     help="Filter to a specific project (optional)")
    bt.add_argument("--metric", default="like",
                     help="Engagement metric to optimize (default: like)")
    bt.add_argument("--min-samples", type=int, default=5,
                     help="Min posts per bucket before trusting data over default")
    bt.add_argument("--verbose", "-v", action="store_true",
                     help="Print full hour-of-week table")
    bt.set_defaults(func=cmd_best_time)

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
