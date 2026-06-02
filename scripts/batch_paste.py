#!/usr/bin/env python3
"""batch_paste.py — morning ritual: ship N pending drafts in 5 minutes.

The marketing-agent v0.18.6 publish loop is half-built: drafts get generated
into ~/.marketing_agent/queue/pending/ but most platforms (X/LinkedIn/Reddit
etc) have no API adapter, so `post` only handles the 1 case it knows. Result:
30 drafts piled up across May/June, posted/ folder has 0 rows, bandit is
starving for engagement data, every MVP we ship has no traffic source.

This script closes that gap with HITL paste workflow:

  1. Read pending/ frontmatter (platform, project, scheduled_for)
  2. Group by platform, sort by scheduled_for ascending
  3. For each due draft (default top 3 across platforms):
       a) pbcopy the body
       b) `open` the platform's compose URL in browser
       c) Wait for input: y (posted) / s (skip) / n (reject)
       d) On y: move pending/→posted/, record post_history row
  4. Print summary

Usage:
  scripts/batch_paste.py                  # interactive, 3 due drafts
  scripts/batch_paste.py --limit 5        # 5 due drafts
  scripts/batch_paste.py --platform x     # only X drafts
  scripts/batch_paste.py --dry-run        # show queue, no clipboard / open
  scripts/batch_paste.py --audit          # print full queue audit + exit
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sqlite3
import subprocess
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
QUEUE_ROOT = HOME / ".marketing_agent" / "queue"
PENDING = QUEUE_ROOT / "pending"
POSTED = QUEUE_ROOT / "posted"
REJECTED = QUEUE_ROOT / "rejected"
HISTORY_DB = HOME / ".marketing_agent" / "history.db"

# Platform → compose URL (deep-link to post-creation page)
COMPOSE_URLS = {
    "x": "https://x.com/compose/post",
    "twitter": "https://x.com/compose/post",
    "hacker_news": "https://news.ycombinator.com/submit",
    "hackernews": "https://news.ycombinator.com/submit",
    "reddit": None,  # subreddit-dependent, built dynamically
    "linkedin": "https://www.linkedin.com/feed/?shareActive=true",
    "bluesky": "https://bsky.app/",
    "dev_to": "https://dev.to/new",
    "devto": "https://dev.to/new",
    "threads": "https://www.threads.net/",
    "mastodon": "https://mastodon.social/",
    "xiaohongshu": "https://creator.xiaohongshu.com/publish/publish",
    "zhihu": "https://www.zhihu.com/question/new",
    "product_hunt": "https://www.producthunt.com/posts/new",
    "producthunt": "https://www.producthunt.com/posts/new",
}


def parse_frontmatter(path: Path) -> tuple[dict, str]:
    """Parse YAML-ish frontmatter. Returns (meta dict, body str)."""
    text = path.read_text()
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta = {}
    for line in parts[1].strip().splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip()
    return meta, parts[2].lstrip("\n")


def reddit_compose_url(body: str, meta: dict) -> str:
    """Reddit's submit URL takes the subreddit; extract from frontmatter or guess."""
    sub = meta.get("target") or meta.get("subreddit") or "SideProject"
    return f"https://www.reddit.com/r/{sub}/submit"


def get_compose_url(platform: str, body: str, meta: dict) -> str:
    p = platform.lower().replace("-", "_")
    if p in ("reddit",):
        return reddit_compose_url(body, meta)
    return COMPOSE_URLS.get(p) or "https://x.com/compose/post"


def collect_pending() -> list[dict]:
    """Read every pending draft, parse frontmatter, sort by scheduled_for."""
    rows = []
    for path in sorted(PENDING.glob("*.md")):
        meta, body = parse_frontmatter(path)
        platform = meta.get("platform", "unknown")
        project = meta.get("project", "?")
        scheduled = meta.get("scheduled_for") or meta.get("generated_at") or "9999-01-01T00:00:00+00:00"
        try:
            sched_dt = datetime.fromisoformat(scheduled.replace("Z", "+00:00"))
        except ValueError:
            sched_dt = datetime(9999, 1, 1, tzinfo=timezone.utc)
        rows.append({
            "path": path,
            "platform": platform,
            "project": project,
            "scheduled_for": sched_dt,
            "body": body,
            "meta": meta,
        })
    rows.sort(key=lambda r: r["scheduled_for"])
    return rows


def filter_due(rows: list[dict], platform: str | None, project: str | None = None) -> list[dict]:
    """Return due drafts sorted by recency-of-schedule (today first, then yesterday, ...).

    Why reversed: when 5 weeks of drafts pile up, the freshest material
    (today's Funeral launch) is the one that matches current product state.
    Old PH-day kits with stale data hurt more than they help.
    """
    now = datetime.now(timezone.utc)
    out = [r for r in rows if r["scheduled_for"] <= now]
    if platform:
        plat_norm = platform.lower().replace("-", "_")
        out = [r for r in out if r["platform"].lower().replace("-", "_") == plat_norm]
    if project:
        proj_norm = project.lower()
        out = [r for r in out if proj_norm in r["project"].lower()]
    out.sort(key=lambda r: r["scheduled_for"], reverse=True)
    return out


def archive_stale(rows: list[dict], days: int) -> int:
    """Move drafts overdue by > days to rejected/ with reason. Returns count moved."""
    now = datetime.now(timezone.utc)
    moved = 0
    for r in rows:
        delta_days = (now - r["scheduled_for"]).days
        if delta_days > days:
            sched = r["scheduled_for"].strftime("%Y-%m-%d")
            reject_draft(
                r,
                f"auto-archived: scheduled {sched}, {delta_days}d overdue (> {days}d threshold). "
                "Distribution window passed; re-draft with current product state.",
            )
            print(f"  ✗ archived: {r['path'].name} ({delta_days}d overdue)")
            moved += 1
    return moved


def pbcopy(text: str) -> bool:
    """Copy text to macOS clipboard. Returns True on success."""
    try:
        proc = subprocess.run(["pbcopy"], input=text, text=True, timeout=5)
        return proc.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def open_url(url: str) -> bool:
    try:
        subprocess.run(["open", url], timeout=5, check=False)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def record_posted(draft: dict, external_id: str | None) -> None:
    """Insert post_history row + move file pending/→posted/."""
    body = draft["body"]
    content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    body_preview = body[:200]
    now_iso = datetime.now(timezone.utc).isoformat()

    con = sqlite3.connect(HISTORY_DB)
    try:
        con.execute(
            """
            INSERT OR IGNORE INTO post_history
              (content_hash, platform, project_name, body_preview, external_id, posted_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (content_hash, draft["platform"], draft["project"], body_preview, external_id, now_iso),
        )
        con.commit()
    finally:
        con.close()

    POSTED.mkdir(parents=True, exist_ok=True)
    dst = POSTED / draft["path"].name
    shutil.move(str(draft["path"]), str(dst))


def reject_draft(draft: dict, reason: str) -> None:
    REJECTED.mkdir(parents=True, exist_ok=True)
    dst = REJECTED / draft["path"].name
    shutil.move(str(draft["path"]), str(dst))
    # Write reason to a sibling .reason.txt
    (dst.parent / (dst.stem + ".reason.txt")).write_text(reason)


def print_audit(rows: list[dict]) -> None:
    now = datetime.now(timezone.utc)
    print(f"\n=== Pending queue audit ({len(rows)} drafts) ===\n")
    by_platform = {}
    for r in rows:
        by_platform.setdefault(r["platform"], []).append(r)
    for platform, group in sorted(by_platform.items()):
        print(f"\n## {platform} ({len(group)})")
        for r in group:
            delta = (now - r["scheduled_for"]).days
            status = f"{delta}d overdue" if delta > 0 else f"in {-delta}d"
            sched = r["scheduled_for"].strftime("%Y-%m-%d")
            print(f"  - [{sched} | {status:>12}] {r['project']:<30} {r['path'].name}")


def interactive_paste(rows: list[dict], dry_run: bool) -> dict:
    posted = 0
    skipped = 0
    rejected = 0
    print(f"\nDue drafts: {len(rows)}\n")
    for i, draft in enumerate(rows, 1):
        platform = draft["platform"]
        project = draft["project"]
        compose_url = get_compose_url(platform, draft["body"], draft["meta"])
        sched = draft["scheduled_for"].strftime("%Y-%m-%d")
        print(f"\n──[{i}/{len(rows)}]──────────────────────────────────────")
        print(f"  Project:   {project}")
        print(f"  Platform:  {platform}")
        print(f"  Scheduled: {sched}")
        print(f"  File:      {draft['path'].name}")
        print(f"  Compose:   {compose_url}")
        preview = draft["body"][:200].replace("\n", " ⏎ ")
        print(f"  Preview:   {preview}...")
        if dry_run:
            print("  [dry-run] would pbcopy + open compose URL")
            continue
        prompt = "\n  Action? (p)aste-and-open / (s)kip / (r)eject / (q)uit: "
        choice = input(prompt).strip().lower()
        if choice == "q":
            print("Quitting.")
            break
        if choice == "s":
            skipped += 1
            continue
        if choice == "r":
            reason = input("  Reason for reject (1-line): ").strip() or "manual reject"
            reject_draft(draft, reason)
            rejected += 1
            print("  ✗ Rejected.")
            continue
        # default = paste-and-open
        if pbcopy(draft["body"]):
            print("  ✓ Body copied to clipboard")
        else:
            print("  ✗ pbcopy failed; copy the body manually")
        if open_url(compose_url):
            print(f"  ✓ Opened {compose_url}")
        else:
            print(f"  ✗ open failed; visit {compose_url} manually")
        url_after = input("\n  After posting, paste the post URL (or just enter): ").strip()
        record_posted(draft, url_after or None)
        posted += 1
        print(f"  ✓ Recorded to post_history + moved to posted/")
    return {"posted": posted, "skipped": skipped, "rejected": rejected}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=3, help="Max drafts to handle in this run (default 3)")
    ap.add_argument("--platform", default=None, help="Filter by platform (x, reddit, hacker_news, etc.)")
    ap.add_argument("--project", default=None, help="Filter by project name substring (e.g. 'launchkit', 'funeral')")
    ap.add_argument("--dry-run", action="store_true", help="Show what would happen, no clipboard/open")
    ap.add_argument("--audit", action="store_true", help="Print full queue audit + exit")
    ap.add_argument("--archive-stale", type=int, metavar="DAYS",
                    help="Auto-reject drafts overdue by > DAYS, then exit (e.g. --archive-stale 14)")
    args = ap.parse_args()

    if not PENDING.exists():
        print(f"No pending dir at {PENDING}", file=sys.stderr)
        sys.exit(1)

    all_pending = collect_pending()
    if args.audit:
        print_audit(all_pending)
        return

    if args.archive_stale is not None:
        print(f"\nArchiving drafts overdue > {args.archive_stale} days...\n")
        moved = archive_stale(all_pending, args.archive_stale)
        print(f"\n=== Archived {moved} stale drafts. Pending remaining: {len(all_pending) - moved} ===")
        return

    due = filter_due(all_pending, args.platform, args.project)
    if not due:
        print(f"No due drafts (total pending: {len(all_pending)}).")
        if args.platform:
            print(f"  (filtered by platform={args.platform})")
        if args.project:
            print(f"  (filtered by project={args.project})")
        return

    # Diversify: prefer different platforms in same session, sort by scheduled
    seen_platforms = set()
    diversified = []
    queue = list(due)
    # Round-robin one-per-platform until limit
    while queue and len(diversified) < args.limit:
        progressed = False
        i = 0
        while i < len(queue) and len(diversified) < args.limit:
            r = queue[i]
            key = (r["platform"].lower(), r["project"])
            if key not in seen_platforms:
                diversified.append(r)
                seen_platforms.add(key)
                queue.pop(i)
                progressed = True
            else:
                i += 1
        if not progressed:
            # All remaining drafts duplicate platforms we already have; take next anyway
            diversified.extend(queue[: args.limit - len(diversified)])
            break

    summary = interactive_paste(diversified, args.dry_run)
    print(f"\n=== Summary ===")
    print(f"  posted:   {summary['posted']}")
    print(f"  skipped:  {summary['skipped']}")
    print(f"  rejected: {summary['rejected']}")
    print(f"  pending remaining: {len(all_pending) - summary['posted'] - summary['rejected']}")


if __name__ == "__main__":
    main()
