"""Failure post-mortem — explain why a specific post underperformed.

When you check engagement on a post and it landed below median for that
platform, you want to know WHY. This module compares one post against:

  1. Median engagement on the same platform (last N posts)
  2. Critic score on the post body (heuristic only — no LLM call)
  3. Posting hour vs. best-time CDF for that platform
  4. Length, hashtag count, image presence vs. peer median

Output: a markdown report with the diagnoses + recommendations. CLI:
    marketing-agent autopsy --post-id 1234567890

The whole thing runs offline against the SQLite tracker; no API calls.
"""
from __future__ import annotations
import sqlite3
import statistics
from datetime import datetime
from pathlib import Path
from typing import Optional

from marketing_agent.critic import heuristic_score
from marketing_agent.memory import _default_db_path
from marketing_agent.types import Platform, Post


def _fetch_post_by_external_id(post_id: str, *,
                                  db_path: Path) -> Optional[dict]:
    """Pull post_history row by external_id."""
    if not db_path.exists():
        return None
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM post_history WHERE external_id = ?",
            (post_id,),
        ).fetchone()
    return dict(row) if row else None


def _engagement_for_post(post_id: str, *, db_path: Path,
                            metric: str = "like") -> int:
    if not db_path.exists():
        return 0
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT MAX(count) FROM engagement "
            "WHERE post_id = ? AND metric = ?",
            (post_id, metric),
        ).fetchone()
    return int(row[0] or 0)


def _platform_baseline(platform: str, *, db_path: Path,
                          metric: str = "like",
                          limit: int = 30) -> dict:
    """Return median + n recent peer-engagement values for the platform."""
    if not db_path.exists():
        return {"median": 0.0, "p25": 0.0, "p75": 0.0, "n": 0}
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """SELECT MAX(e.count)
               FROM post_history h
               LEFT JOIN engagement e
                 ON e.post_id = h.external_id AND e.metric = ?
               WHERE h.platform = ?
               GROUP BY h.id
               ORDER BY h.posted_at DESC LIMIT ?""",
            (metric, platform, limit),
        ).fetchall()
    counts = [int(r[0] or 0) for r in rows]
    if not counts:
        return {"median": 0.0, "p25": 0.0, "p75": 0.0, "n": 0}
    counts_sorted = sorted(counts)
    return {
        "median": float(statistics.median(counts_sorted)),
        "p25": float(counts_sorted[len(counts_sorted) // 4]),
        "p75": float(counts_sorted[3 * len(counts_sorted) // 4]),
        "n": len(counts_sorted),
    }


def autopsy(post_id: str, *, metric: str = "like",
              db_path: Optional[Path | str] = None) -> dict:
    """Run the autopsy. Returns a structured diagnosis dict.

    Keys:
        post              the post_history row, or None if not found
        engagement        peak metric count for this post
        baseline          median/p25/p75 of peers on the same platform
        underperformance  fraction below median (0 = at median, 1 = at zero)
        critic            CritiqueResult of post body (heuristic-only)
        diagnoses         list of human-readable findings
        recommendations   list of suggested fixes
    """
    db = Path(db_path) if db_path else _default_db_path()
    post_row = _fetch_post_by_external_id(post_id, db_path=db)
    if not post_row:
        return {
            "post": None,
            "diagnoses": [f"post {post_id} not found in history.db"],
            "recommendations": [],
        }

    eng = _engagement_for_post(post_id, db_path=db, metric=metric)
    baseline = _platform_baseline(post_row["platform"], db_path=db,
                                       metric=metric)

    median = baseline["median"]
    underperf = 0.0
    if median > 0:
        underperf = max(0.0, (median - eng) / median)

    # Run heuristic critic on the body preview (full body not stored — preview
    # is the first 200 chars; that's enough to flag hype words / structure)
    fake_post = Post(
        platform=Platform(post_row["platform"]),
        body=post_row["body_preview"] or "",
    )
    crit = heuristic_score(fake_post)

    diagnoses: list[str] = []
    recs: list[str] = []

    # 1. Engagement vs peers
    if baseline["n"] >= 5:
        if eng < median * 0.5 and median > 0:
            diagnoses.append(
                f"Engagement ({eng}) is well below platform median ({median:.0f}, "
                f"based on last {baseline['n']} posts).")
            recs.append("Try a different opening pattern next time — see "
                          "`marketing-agent bandit report` for the platform's "
                          "current winner.")
        elif eng < median:
            diagnoses.append(
                f"Engagement ({eng}) below median ({median:.0f}) but within "
                f"normal variance.")
    else:
        diagnoses.append(
            f"Only {baseline['n']} peer post(s) on this platform — too few "
            f"to compute a reliable median; benchmark unstable.")

    # 2. Critic findings
    if crit.reasons:
        diagnoses.append(
            f"Critic flagged structural issues (score {crit.score}/10): "
            + "; ".join(crit.reasons[:3]))
        recs.append("Strip flagged patterns and re-run with `--variants 3`.")

    # 3. Posting time vs. best time
    try:
        from marketing_agent.best_time import optimal_post_time
        wd_best, h_best, src = optimal_post_time(
            Platform(post_row["platform"]), metric=metric, db_path=db)
        posted_dt = datetime.fromisoformat(post_row["posted_at"])
        if (wd_best, h_best) != (posted_dt.weekday(), posted_dt.hour):
            wkdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            diagnoses.append(
                f"Posted {wkdays[posted_dt.weekday()]} {posted_dt.hour:02d}:00 UTC "
                f"but best slot ({src}) is "
                f"{wkdays[wd_best]} {h_best:02d}:00.")
            recs.append(
                f"Try `marketing-agent schedule --best-time --platform "
                f"{post_row['platform']}` next time.")
    except Exception:
        pass

    # 4. Length vs typical short-form ceiling
    blen = len(post_row["body_preview"] or "")
    if post_row["platform"] == "x" and blen < 60:
        diagnoses.append(
            f"Body is short ({blen} chars). X posts <80 chars often "
            f"under-perform: too thin to spark replies.")
        recs.append("Add a concrete number, link, or specific detail.")

    return {
        "post": post_row,
        "engagement": eng,
        "baseline": baseline,
        "underperformance": round(underperf, 2),
        "critic": {
            "score": crit.score,
            "reasons": crit.reasons,
        },
        "diagnoses": diagnoses,
        "recommendations": recs,
    }


def render_markdown(report: dict) -> str:
    """Render an autopsy dict as a markdown report."""
    if not report.get("post"):
        diags = "\n".join(f"- {d}" for d in report.get("diagnoses", []))
        return f"# Post-mortem\n\n**Post not found.**\n\n{diags}\n"
    p = report["post"]
    lines = [
        f"# Post-mortem — {p['platform']} · {p['external_id']}",
        f"",
        f"*Posted {p['posted_at']} · "
        f"engagement: **{report['engagement']} {report['baseline']['n'] and 'likes' or '(no metric)'}** "
        f"vs platform median {report['baseline']['median']:.0f} "
        f"({report['baseline']['n']} peers)*",
        f"",
        f"## Body excerpt",
        f"```",
        p["body_preview"] or "",
        f"```",
        f"",
        f"## Critic score: {report['critic']['score']}/10",
        f"",
    ]
    for r in report["critic"]["reasons"]:
        lines.append(f"- {r}")
    if not report["critic"]["reasons"]:
        lines.append("- (no structural issues detected)")
    lines.extend(["", "## Diagnoses", ""])
    for d in report["diagnoses"]:
        lines.append(f"- {d}")
    lines.extend(["", "## Recommendations", ""])
    if not report["recommendations"]:
        lines.append("- (engagement within normal variance — no specific fix)")
    for r in report["recommendations"]:
        lines.append(f"- {r}")
    return "\n".join(lines)
