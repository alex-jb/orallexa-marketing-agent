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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True,
                    help="GitHub repo, e.g. alex-jb/orallexa-ai-trading-agent")
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--platforms", nargs="+",
                    default=["x"],
                    help="One or more of: x reddit linkedin dev_to")
    ap.add_argument("--subreddit", default=None,
                    help="Required when posting to reddit")
    ap.add_argument("--dry-run", action="store_true",
                    help="Generate and preview, don't actually post")
    ap.add_argument("--to-queue", action="store_true",
                    help="Submit drafts to ApprovalQueue (HITL) instead of posting directly")
    ap.add_argument("--force", action="store_true",
                    help="Post even when commits look skippable")
    ap.add_argument("--mode", choices=["template", "llm", "hybrid"], default="hybrid")
    args = ap.parse_args()

    preset = REPO_PRESETS.get(args.repo)
    if preset is None:
        print(f"⚠️  No preset for {args.repo} — using minimal metadata", file=sys.stderr)
        preset = {"name": args.repo.split("/")[-1], "tagline": "WIP",
                  "description": None, "website": None, "tags": []}

    print(f"🔍 Fetching commits from {args.repo} (last {args.hours}h)...")
    commits = fetch_commits(args.repo, args.hours)
    print(f"   Found {len(commits)} commits")

    if not commits:
        print("ℹ️  No commits in window — nothing to post.")
        return 0

    if is_all_skippable(commits) and not args.force:
        print("ℹ️  All commits look like CI/docs/chores — skipping (use --force to override).")
        for c in commits:
            print(f"     {c['sha']} {c['msg'].splitlines()[0]}")
        return 0

    project = build_project(args.repo, commits, **preset)

    platforms = [Platform(p) for p in args.platforms]
    mode = {"template": GenerationMode.TEMPLATE,
            "llm": GenerationMode.LLM,
            "hybrid": GenerationMode.HYBRID}[args.mode]
    orch = Orchestrator(mode=mode)

    print(f"🤖 Generating posts (mode={mode.value})...")
    posts = orch.generate(project, platforms, subreddit=args.subreddit)

    if args.to_queue:
        q = ApprovalQueue()
        paths: list[str] = []
        for post in posts:
            print(f"\n--- {post.platform.value.upper()} preview ---")
            print(orch.preview(post))
            p = q.submit(post, preset["name"], generated_by=mode.value)
            paths.append(str(p))
            print(f"📥 queued: {p}")
        # GitHub Actions: surface the paths as a step output for the next job.
        gh_out = os.getenv("GITHUB_OUTPUT")
        if gh_out:
            with open(gh_out, "a") as fh:
                fh.write(f"queued_count={len(paths)}\n")
        return 0

    failed = 0
    for post in posts:
        print(f"\n--- {post.platform.value.upper()} preview ---")
        print(orch.preview(post))

        if args.dry_run:
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
            failed += 1

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
