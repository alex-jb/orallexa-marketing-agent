"""Daily auto-post — fetches recent commits from a target repo, builds a
Project, runs the marketing_agent SDK, and posts to configured platforms.

Designed to be invoked by GitHub Actions cron once per day.

Usage:
  python3 scripts/daily_post.py --repo alex-jb/orallexa-ai-trading-agent
  python3 scripts/daily_post.py --repo alex-jb/vibex --hours 24 --dry-run

Skips posting when:
  - No commits in window
  - All commits are skippable (CI-only / docs-only / chores)
  - Use --force to override skip rules
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

from marketing_agent import (
    ApprovalQueue, GenerationMode, Orchestrator, Platform, Project,
)
from marketing_agent.platforms.base import NotConfigured


SKIP_IF_ONLY_PREFIXES = ("ci", "docs:", "chore:", "fix(ci)", "style:", "refactor:")


def fetch_commits(repo: str, hours: int) -> list[dict]:
    """Fetch commits from `repo` in the last `hours` via gh CLI."""
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/commits",
         "-X", "GET", "-F", f"since={since}",
         "--paginate", "--jq",
         '.[] | {sha: .sha[0:7], msg: .commit.message, '
         'date: .commit.author.date, author: .commit.author.name}'],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        print(f"❌ gh api failed: {result.stderr}", file=sys.stderr)
        sys.exit(2)
    out: list[dict] = []
    for line in result.stdout.strip().split("\n"):
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def is_all_skippable(commits: list[dict]) -> bool:
    if not commits:
        return True
    for c in commits:
        first = c["msg"].split("\n", 1)[0].strip().lower()
        if not any(first.startswith(p) for p in SKIP_IF_ONLY_PREFIXES):
            return False
    return True


def build_project(repo: str, commits: list[dict],
                    name: str, tagline: str, description: str | None,
                    website: str | None, tags: list[str]) -> Project:
    """Build a Project model from commits + metadata."""
    return Project(
        name=name,
        tagline=tagline,
        description=description,
        github_url=f"https://github.com/{repo}",
        website_url=website,
        tags=tags,
        recent_changes=[c["msg"].split("\n", 1)[0].strip() for c in commits[:10]],
    )


# Per-repo defaults so the script knows what each project is about.
# Add new repos here as you build them.
REPO_PRESETS: dict[str, dict] = {
    "alex-jb/orallexa-ai-trading-agent": {
        "name": "Orallexa",
        "tagline": "Self-tuning multi-agent AI trading system",
        "description": (
            "Bull/Bear/Judge debate every signal on Claude Opus 4.7. "
            "8-source signal fusion (technical + ML + news + options + "
            "institutional + social + earnings + prediction markets). "
            "10 ML models including Kronos foundation model. 922 tests, MIT."
        ),
        "website": "https://orallexa-ui.vercel.app",
        "tags": ["multi-agent", "trading", "llm", "langgraph", "claude"],
    },
    "alex-jb/vibex": {
        "name": "VibeXForge",
        "tagline": "Gamified growth platform for AI creators",
        "description": (
            "Submit your AI project, Claude scores it across 5 dimensions, "
            "your project becomes a collectible hero card that evolves "
            "Seed → Myth based on real traction."
        ),
        "website": "https://vibexforge.com",
        "tags": ["gamification", "ai-creators", "growth", "claude", "supabase"],
    },
    "alex-jb/orallexa-marketing-agent": {
        "name": "Orallexa Marketing Agent",
        "tagline": "AI marketing agent for OSS founders",
        "description": (
            "Open-source Python SDK that turns any AI/OSS project into "
            "platform-specific marketing content and distributes it across "
            "X, Reddit, LinkedIn, DEV.to."
        ),
        "website": None,
        "tags": ["marketing", "automation", "ai-agent", "oss"],
    },
}


def _run_for_project(*, repo: str, preset: dict, hours: int,
                       platforms: list[str], subreddit: Optional[str],
                       dry_run: bool, to_queue: bool, force: bool,
                       mode_str: str, n_variants: int = 1) -> int:
    """Run the daily flow for ONE (repo, preset) pair. Returns count queued
    (when to_queue=True) or 0 on early-exit."""
    print(f"\n━━━ {preset['name']}  ({repo}) ━━━")
    print(f"🔍 Fetching commits from {repo} (last {hours}h)...")
    commits = fetch_commits(repo, hours)
    print(f"   Found {len(commits)} commits")

    if not commits:
        print("ℹ️  No commits in window — nothing to post.")
        return 0
    if is_all_skippable(commits) and not force:
        print("ℹ️  All commits look like CI/docs/chores — skipping (use --force to override).")
        for c in commits:
            print(f"     {c['sha']} {c['msg'].splitlines()[0]}")
        return 0

    project = build_project(repo, commits, **preset)
    platforms_e = [Platform(p) for p in platforms]
    mode = {"template": GenerationMode.TEMPLATE,
            "llm": GenerationMode.LLM,
            "hybrid": GenerationMode.HYBRID}[mode_str]
    orch = Orchestrator(mode=mode)

    print(f"🤖 Generating posts (mode={mode.value}, n_variants={n_variants})...")
    posts = orch.generate(project, platforms_e, subreddit=subreddit,
                              n_variants=n_variants)

    if to_queue:
        q = ApprovalQueue()
        queued = 0
        for post in posts:
            print(f"\n--- {post.platform.value.upper()} preview ---")
            print(orch.preview(post))
            p = q.submit(post, preset["name"], generated_by=mode.value)
            print(f"📥 {p.parent.name}: {p}")
            if p.parent.name == "pending":
                queued += 1
        return queued

    for post in posts:
        print(f"\n--- {post.platform.value.upper()} preview ---")
        print(orch.preview(post))
        if dry_run:
            continue
        if not orch.is_ready(post.platform):
            print(f"⏭  Skipped (no credentials configured for {post.platform.value})")
            continue
        try:
            url = orch.post(post)
            print(f"✅ Posted: {url}")
        except NotConfigured as e:
            print(f"⏭  Skipped: {e}")
        except Exception as e:
            print(f"❌ {post.platform.value} post failed: {type(e).__name__}: {e}")
    return 0


def _preset_from_config(cfg) -> dict:
    """Convert a ProjectConfig → REPO_PRESETS-shaped dict."""
    return {
        "name": cfg.name, "tagline": cfg.tagline,
        "description": cfg.description, "website": cfg.website,
        "tags": cfg.tags,
    }


def _run_trends_for_projects(cfgs, tcfg, *, mode_str: str) -> int:
    """For each enabled project, run trends_to_drafts using the shared
    TrendsConfig. Returns total drafts queued across all projects.

    Trends are aggregated ONCE (HTTP fetches cost), then reused across
    every project — each project gets its own per-trend angle via the
    synthetic-Project rewrite inside trends_to_drafts.

    Honors `MARKETING_AGENT_DAILY_BUDGET_USD` — when today's LLM spend
    has already met-or-exceeded the cap, the proactive pass is skipped
    entirely. Per-project budget checks also fire between iterations
    so a single project's first batch can still ship even if subsequent
    projects would tip over.
    """
    from marketing_agent.budget import (
        configured_cap_usd, daily_spend_usd, is_over_budget,
    )
    from marketing_agent.trends import aggregate
    from marketing_agent.trends_to_drafts import trends_to_drafts

    cap = configured_cap_usd()
    if cap is not None and is_over_budget(cap_usd=cap):
        spent = daily_spend_usd()
        print(f"⚠️  daily LLM budget reached "
               f"(${spent:.4f} >= ${cap:.4f}); skipping trends pass.")
        _write_trends_summary([])
        return 0

    print("\n━━━ proactive pass: trends → drafts ━━━")
    print(f"   languages={tcfg.languages or '(all)'}  "
          f"hn_query={tcfg.hn_query!r}  subreddits={tcfg.subreddits}")

    # Single network fetch shared across all projects.
    items = aggregate(
        github_languages=tcfg.languages or None,
        hn_query=tcfg.hn_query,
        subreddits=tcfg.subreddits or None,
        hours=tcfg.hours,
    )
    if not items:
        print("ℹ️  No trending items found in window — skipping.")
        return 0
    print(f"📈 {len(items)} unique trending items; "
          f"feeding top {tcfg.top_n} to each project.")

    mode = {"template": GenerationMode.TEMPLATE,
            "llm": GenerationMode.LLM,
            "hybrid": GenerationMode.HYBRID}[mode_str]

    total = 0
    drafted_summary: list[tuple[str, str, str, str]] = []  # (project, source, title, url)
    for cfg in cfgs:
        if cap is not None and is_over_budget(cap_usd=cap):
            spent = daily_spend_usd()
            print(f"⚠️  budget hit mid-loop (${spent:.4f} >= ${cap:.4f}); "
                   f"stopping after queued={total}, remaining projects skipped.")
            break
        project = Project(
            name=cfg.name, tagline=cfg.tagline,
            description=cfg.description,
            github_url=f"https://github.com/{cfg.repo}",
            website_url=cfg.website, tags=cfg.tags,
        )
        plats = [Platform(p) for p in cfg.platforms]
        results = trends_to_drafts(
            project=project, platforms=plats, items=items,
            top_n=tcfg.top_n, mode=mode, subreddit_target=cfg.subreddit,
        )
        n = sum(len(r.queued_paths) for r in results)
        total += n
        for r in results:
            if r.queued_paths:
                drafted_summary.append(
                    (cfg.name, r.trend.source, r.trend.title[:120], r.trend.url)
                )
        print(f"  · {cfg.name}: {n} draft(s) from "
              f"{len(results)} trend(s)")
    print(f"📥 trends pass total: {total} draft(s) queued")
    _write_trends_summary(drafted_summary)
    return total


def _write_trends_summary(rows) -> None:
    """Persist a per-day trend-draft summary the workflow can include in
    the daily issue body. Empty list still writes a stub file so the
    workflow's `cat` is unconditional.

    Format: markdown bullets grouped by project. Lives at
    `queue/_today_trends_summary.md` (under the queue dir so daily.yml's
    git-add of queue/ catches it for free).
    """
    import os as _os
    from pathlib import Path as _Path
    queue_root = _Path(_os.getenv(
        "MARKETING_AGENT_QUEUE", str(_Path.home() / ".marketing_agent" / "queue"),
    ))
    queue_root.mkdir(parents=True, exist_ok=True)
    summary_path = queue_root / "_today_trends_summary.md"

    if not rows:
        summary_path.write_text("_(no trend-anchored drafts today)_\n")
        return

    by_proj: dict[str, list[tuple[str, str, str]]] = {}
    for project, source, title, url in rows:
        by_proj.setdefault(project, []).append((source, title, url))
    lines = ["**Trend-anchored drafts:**"]
    for proj, items in by_proj.items():
        lines.append(f"- **{proj}**:")
        for src, title, url in items:
            lines.append(f"  - [{src}] [{title}]({url})")
    summary_path.write_text("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=None,
                    help="GitHub repo, e.g. alex-jb/orallexa-ai-trading-agent. "
                          "Mutually exclusive with --config.")
    ap.add_argument("--config", default=None,
                    help="Path to marketing-agent.yml; runs for every enabled "
                          "project. Mutually exclusive with --repo.")
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--platforms", nargs="+", default=["x"],
                    help="Override per-project platforms (config wins for "
                          "--config mode unless this is set).")
    ap.add_argument("--subreddit", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--to-queue", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--mode", choices=["template", "llm", "hybrid"], default="hybrid")
    ap.add_argument("--variants", type=int, default=1,
                    help="Generate N stylistic variants per platform; bandit "
                          "picks one (currently only X has multiple variants — "
                          "emoji-led / question-led / stat-led). Without this "
                          "flag the cron only ever produces emoji-led drafts and "
                          "the bandit can never learn the other variants' real "
                          "performance.")
    ap.add_argument("--trends-too", action="store_true",
                    help="After the commit-driven loop, also run "
                          "trends_to_drafts per project when the config has "
                          "trends.enabled=true. No-op if config disabled or "
                          "if --repo (single mode) is used without a config.")
    args = ap.parse_args()

    if not args.repo and not args.config:
        ap.error("must provide --repo or --config")
    if args.repo and args.config:
        ap.error("--repo and --config are mutually exclusive")

    commit_count = 0
    trends_count = 0

    if args.config:
        from marketing_agent.multiproject import load_config, load_trends_config
        cfgs = load_config(args.config)
        if not cfgs:
            print(f"⚠️  No enabled projects found in {args.config}", file=sys.stderr)
            return 0
        print(f"📋 multi-project run · {len(cfgs)} enabled project(s)")
        for cfg in cfgs:
            preset = _preset_from_config(cfg)
            # Per-project platform list from config; CLI --platforms only
            # overrides if explicitly different from default.
            plats = cfg.platforms if args.platforms == ["x"] else args.platforms
            sub = args.subreddit or cfg.subreddit
            queued = _run_for_project(
                repo=cfg.repo, preset=preset, hours=args.hours,
                platforms=plats, subreddit=sub,
                dry_run=args.dry_run, to_queue=args.to_queue,
                force=args.force, mode_str=args.mode,
                n_variants=args.variants,
            )
            commit_count += queued

        # Proactive pass: run trends_to_drafts per project if enabled.
        if args.trends_too and args.to_queue:
            tcfg = load_trends_config(args.config)
            if tcfg.enabled:
                trends_count = _run_trends_for_projects(
                    cfgs, tcfg, mode_str=args.mode,
                )
            else:
                print("ℹ️  --trends-too set, but trends.enabled=false in "
                       f"{args.config}; skipping proactive pass.")
    else:
        preset = REPO_PRESETS.get(args.repo)
        if preset is None:
            print(f"⚠️  No preset for {args.repo} — using minimal metadata",
                   file=sys.stderr)
            preset = {"name": args.repo.split("/")[-1], "tagline": "WIP",
                       "description": None, "website": None, "tags": []}
        commit_count = _run_for_project(
            repo=args.repo, preset=preset, hours=args.hours,
            platforms=args.platforms, subreddit=args.subreddit,
            dry_run=args.dry_run, to_queue=args.to_queue,
            force=args.force, mode_str=args.mode,
            n_variants=args.variants,
        )

    total_queued = commit_count + trends_count
    if args.to_queue:
        gh_out = os.getenv("GITHUB_OUTPUT")
        if gh_out:
            with open(gh_out, "a") as fh:
                fh.write(f"queued_count={total_queued}\n")
                fh.write(f"commit_count={commit_count}\n")
                fh.write(f"trends_count={trends_count}\n")
        print(f"\n✅ Total queued: {total_queued} "
               f"(commit-driven: {commit_count}, trend-anchored: {trends_count})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
