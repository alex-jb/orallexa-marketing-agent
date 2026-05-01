"""trend_perf_report — compare trend-anchored vs commit-driven posts.

Read-only analysis. After at least a week of v0.17.x daily-cron runs:

  - List queue/posted/*.md
  - Group by `generated_by:` frontmatter:
      * "trends"                → trend-anchored bucket
      * "hybrid"/"llm"/"template" → commit-driven bucket
  - For posts with `<!-- posted_id: ... -->`, fetch X engagement
    counts via EngagementTracker.fetch_x_metrics
  - Compare per-bucket medians (like / repost / reply)
  - Count critic-rejection rates per bucket (queue/rejected/*.md)
  - Inspect the trend-URL dedup memory (drafted_trends table)
  - Write `docs/trend_perf_<UTC-date>.md` + print verdict

Usage:
    python3 scripts/trend_perf_report.py
    python3 scripts/trend_perf_report.py --queue queue --out docs/myreport.md
"""
from __future__ import annotations
import argparse
import re
import sqlite3
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from marketing_agent.engagement import EngagementTracker
from marketing_agent.memory import _default_db_path


_FRONT_RE = re.compile(r"^---\n(.*?)\n---\n(.*)", re.DOTALL)
_POSTED_ID_RE = re.compile(r"<!-- posted_id: (.+?) -->")


def _parse(path: Path) -> tuple[dict, str]:
    """Return (frontmatter_dict, body) for a queue markdown file."""
    text = path.read_text(encoding="utf-8")
    m = _FRONT_RE.match(text)
    if not m:
        return {}, text
    front_text, body = m.groups()
    front: dict = {}
    for line in front_text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            front[k.strip()] = v.strip()
    return front, body


def _bucket(generated_by: str) -> str:
    return "trend" if generated_by == "trends" else "commit"


def _pid(body: str) -> Optional[str]:
    m = _POSTED_ID_RE.search(body)
    return m.group(1).strip() if m else None


def _median(xs):
    return round(statistics.median(xs), 2) if xs else None


def collect(queue_root: Path, *, fetch_x: bool):
    posted_dir = queue_root / "posted"
    rejected_dir = queue_root / "rejected"

    posted = sorted(posted_dir.glob("*.md")) if posted_dir.exists() else []
    rejected = sorted(rejected_dir.glob("*.md")) if rejected_dir.exists() else []

    posted_buckets: dict[str, list[dict]] = defaultdict(list)
    for p in posted:
        front, body = _parse(p)
        b = _bucket(front.get("generated_by", ""))
        rec = {"path": str(p), "front": front, "post_id": _pid(body)}
        posted_buckets[b].append(rec)

    rejected_buckets: dict[str, list[dict]] = defaultdict(list)
    for p in rejected:
        front, _ = _parse(p)
        b = _bucket(front.get("generated_by", ""))
        rejected_buckets[b].append({"path": str(p), "front": front})

    # Engagement fetch for X posts only (Reddit/LinkedIn not wired).
    metrics_per_bucket: dict[str, dict[str, list[int]]] = defaultdict(
        lambda: defaultdict(list)
    )
    if fetch_x:
        tracker = EngagementTracker()
        for bucket, recs in posted_buckets.items():
            for rec in recs:
                if rec["front"].get("platform") != "x" or not rec["post_id"]:
                    continue
                try:
                    events = tracker.fetch_x_metrics(rec["post_id"])
                except Exception as e:
                    print(f"   ! engagement fetch failed for {rec['post_id']}: {e}",
                            file=sys.stderr)
                    continue
                for e in events:
                    metrics_per_bucket[bucket][e.metric].append(e.count)

    return posted_buckets, rejected_buckets, metrics_per_bucket


def trend_memory_stats(db_path: Path) -> dict:
    """Inspect the drafted_trends table — total rows, top sources."""
    if not db_path.exists():
        return {"rows": 0, "by_source_top": {}}
    with sqlite3.connect(db_path) as conn:
        try:
            cur = conn.execute("SELECT COUNT(*) FROM drafted_trends")
            total = cur.fetchone()[0]
        except sqlite3.OperationalError:
            return {"rows": 0, "by_source_top": {}}
        # Approximate "source" from URL host
        cur = conn.execute("SELECT url FROM drafted_trends")
        by_host: dict[str, int] = defaultdict(int)
        for (url,) in cur:
            host = (url or "").split("/")[2] if "://" in (url or "") else "?"
            by_host[host] += 1
    top = dict(sorted(by_host.items(), key=lambda kv: -kv[1])[:5])
    return {"rows": total, "by_source_top": top}


def render_report(posted, rejected, metrics, mem_stats, *, low_sample=5) -> tuple[str, str]:
    """Return (markdown_text, verdict_one_liner)."""
    n_t, n_c = len(posted.get("trend", [])), len(posted.get("commit", []))
    rt = len(rejected.get("trend", []))
    rc = len(rejected.get("commit", []))

    def rate(num, den):
        return f"{num}/{num + den} ({100 * num / (num + den):.0f}%)" if (num + den) else "n/a"

    lines = [
        f"# Trend-anchored vs commit-driven post performance",
        f"",
        f"_Generated {datetime.now(timezone.utc).isoformat()}_",
        f"",
        f"## Sample sizes (queue/posted)",
        f"- trend-anchored: **{n_t}** posted",
        f"- commit-driven: **{n_c}** posted",
        f"",
        f"## Critic rejection rates (queue/rejected vs queue/posted)",
        f"- trend-anchored: {rate(rt, n_t)}",
        f"- commit-driven: {rate(rc, n_c)}",
        f"",
        f"## X engagement medians",
    ]
    for metric in ("like", "repost", "reply"):
        t = _median(metrics.get("trend", {}).get(metric, []))
        c = _median(metrics.get("commit", {}).get(metric, []))
        lines.append(f"- **{metric}** — trend: {t}  ·  commit: {c}")
    lines += [
        f"",
        f"## Trend-URL dedup memory",
        f"- rows: **{mem_stats['rows']}**",
        f"- top sources: {mem_stats['by_source_top']}",
        f"",
        f"## Verdict",
    ]

    # Verdict logic
    likes_t = _median(metrics.get("trend", {}).get("like", []))
    likes_c = _median(metrics.get("commit", {}).get("like", []))
    if n_t < low_sample or n_c < low_sample:
        verdict = (
            f"⚠️ Insufficient sample (trend={n_t}, commit={n_c}; need ≥{low_sample} "
            f"each). Re-run in another week before drawing conclusions."
        )
    elif likes_t is None or likes_c is None:
        verdict = (
            "⚠️ X engagement data missing for one or both buckets — verify X "
            "credentials, then re-run."
        )
    elif likes_t >= likes_c * 0.9:
        verdict = (
            f"✅ Trend-anchored posts hold their own (median likes "
            f"trend={likes_t} vs commit={likes_c}). Keep the proactive loop on."
        )
    elif likes_t >= likes_c * 0.7:
        verdict = (
            f"⚖️ Trend-anchored medianlikes ({likes_t}) trail commit-driven "
            f"({likes_c}) by 10-30%. Tweak: narrow `subreddits`, raise `top_n` "
            f"selectivity, or refine `hn_query` in marketing-agent.yml."
        )
    else:
        verdict = (
            f"❌ Trend-anchored median likes ({likes_t}) underperform "
            f"commit-driven ({likes_c}) by >30%. Consider disabling "
            f"`trends.enabled` until tuned, or drop `top_n` to 1-2."
        )
    lines.append(verdict)
    return "\n".join(lines) + "\n", verdict


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", default="queue",
                    help="Queue root containing posted/ and rejected/")
    ap.add_argument("--out", default=None,
                    help="Output markdown path (default docs/trend_perf_<utc>.md)")
    ap.add_argument("--no-fetch-x", action="store_true",
                    help="Skip live X engagement fetch (useful when no key)")
    ap.add_argument("--low-sample", type=int, default=5,
                    help="Min sample size per bucket to draw conclusions")
    args = ap.parse_args()

    queue_root = Path(args.queue)
    if not queue_root.exists():
        print(f"❌ queue root not found: {queue_root}", file=sys.stderr)
        return 2

    posted, rejected, metrics = collect(queue_root, fetch_x=not args.no_fetch_x)
    mem_stats = trend_memory_stats(_default_db_path())
    md, verdict = render_report(
        posted, rejected, metrics, mem_stats, low_sample=args.low_sample,
    )

    out_path = (
        Path(args.out) if args.out
        else Path("docs") / f"trend_perf_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.md"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(f"📄 report written: {out_path}")
    print(f"\n{verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
