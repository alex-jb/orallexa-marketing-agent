"""Voyager-style auto-skill promotion.

Voyager (NeurIPS 2023) trained an agent in Minecraft that wrote its own
skill code as it discovered useful patterns. The 2026 application to
content agents: when a post lands top-quartile by engagement, extract
its observable structure (variant_key, length, opening pattern, hashtag
density) into a Claude Skill file that future generations can reference.

How it stays useful without an LLM key: structure extraction is purely
heuristic. We compute the post's structural fingerprint, render a skill
markdown that documents "this kind of post worked." Claude Code (or the
Agent SDK with skills="all") loads it as a hint on the next campaign.

Output dirs (both written so cross-agent + repo-local consumers find it):
  - `skills/learned/<slug>.md` — repo-local, version-controlled, separate
    from the curated `skills/marketing-voice/` so auto-extracted content
    doesn't pollute the human-authored brand voice guide.
  - `~/.solo-founder-os/skills/<slug>.md` — SFOS shared dir; this is what
    `solo_founder_os.skills.list_skills()` scans, so other agents in the
    stack (vc-outreach, customer-discovery, bilingual) can `pip install
    solo-founder-os` and pick up marketing-agent's distilled wins for
    free. Override path with SFOS_SKILLS_DIR.

Idempotent: re-running on the same top-quartile post replaces both files.
"""
from __future__ import annotations
import os
import re
import sqlite3
from pathlib import Path
from typing import Optional

from marketing_agent.logging import get_logger
from marketing_agent.memory import _default_db_path
from marketing_agent.types import Platform

log = get_logger(__name__)


DEFAULT_SKILL_DIR = Path("skills/learned")


def _sfos_skills_dir() -> Path:
    """SFOS-shared skills dir. Honors SFOS_SKILLS_DIR env override."""
    override = os.getenv("SFOS_SKILLS_DIR")
    if override:
        return Path(override)
    return Path.home() / ".solo-founder-os" / "skills"


def _slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:60]


def _opening_pattern(body: str) -> str:
    """Classify the post's opening into a coarse pattern.

    Order matters: build-in-public phrasing is checked before stat-led
    so that "Just shipped v0.12" isn't miscategorized on the digit in
    "0.12".
    """
    first_line = body.split("\n", 1)[0]
    if not first_line:
        return "unknown"
    first_char = first_line[0]
    if ord(first_char) > 0x2600:  # any emoji-ish code point
        return "emoji-led"
    if first_line.endswith("?"):
        return "question-led"
    low = first_line.lower()
    if low.startswith(("just shipped", "today i", "shipped",
                          "released", "just released", "open-sourced")):
        return "build-in-public-led"
    if any(c.isdigit() for c in first_line[:30]):
        return "stat-led"
    return "narrative-led"


def _structural_fingerprint(body: str) -> dict:
    """Heuristic features of a post that future drafts might mimic."""
    lines = [ln for ln in body.split("\n") if ln.strip()]
    return {
        "char_count": len(body),
        "line_count": len(lines),
        "opening_pattern": _opening_pattern(body),
        "hashtag_count": len(re.findall(r"#\w+", body)),
        "has_url": ("http://" in body) or ("https://" in body),
        "has_code_block": "```" in body,
        "exclamation_count": body.count("!"),
    }


def find_top_quartile_posts(*, platform: Optional[Platform] = None,
                              metric: str = "like",
                              min_samples: int = 4,
                              db_path: Optional[Path | str] = None
                              ) -> list[dict]:
    """Return posts whose peak `metric` count is in the top quartile of
    history for that platform. Excludes platforms with too little data
    (configurable min_samples)."""
    db = Path(db_path) if db_path else _default_db_path()
    if not db.exists():
        return []

    sql = """
        SELECT h.id, h.external_id, h.platform, h.body_preview,
               h.posted_at, COALESCE(MAX(e.count), 0) AS peak
        FROM post_history h
        LEFT JOIN engagement e
          ON e.post_id = h.external_id AND e.metric = ?
        WHERE 1=1
    """
    args: list = [metric]
    if platform:
        sql += " AND h.platform = ?"; args.append(platform.value)
    sql += " GROUP BY h.id"

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute(sql, args).fetchall()]
    if len(rows) < min_samples:
        return []

    # Compute the 75th percentile threshold per platform present
    by_plat: dict[str, list[dict]] = {}
    for r in rows:
        by_plat.setdefault(r["platform"], []).append(r)

    out: list[dict] = []
    for plat, posts in by_plat.items():
        if len(posts) < min_samples:
            continue
        peaks = sorted([p["peak"] for p in posts])
        cutoff = peaks[int(0.75 * len(peaks))]
        for p in posts:
            if p["peak"] >= cutoff and p["peak"] > 0:
                out.append(p)
    out.sort(key=lambda r: r["peak"], reverse=True)
    return out


def promote(*, platform: Optional[Platform] = None,
              metric: str = "like",
              skill_dir: Optional[Path | str] = None,
              db_path: Optional[Path | str] = None,
              min_samples: int = 4,
              sfos_mirror: bool = True) -> list[Path]:
    """Find top-quartile posts and write `skills/learned/<slug>.md` for each.

    When `sfos_mirror` is True (default), each promoted skill is also
    written to `~/.solo-founder-os/skills/<slug>.md` so SFOS' shared
    `list_skills()` picks it up cross-agent. Override SFOS path via
    SFOS_SKILLS_DIR env var. Pass sfos_mirror=False to disable in tests
    where you don't want side-effects in the user's home dir (the
    autouse conftest fixture handles this for the suite).

    Returns the list of repo-local paths written. SFOS-mirror paths are
    not returned (they're a side effect, not a primary product).
    """
    target = Path(skill_dir) if skill_dir else DEFAULT_SKILL_DIR
    target.mkdir(parents=True, exist_ok=True)

    sfos_target = _sfos_skills_dir() if sfos_mirror else None
    if sfos_target is not None:
        try:
            sfos_target.mkdir(parents=True, exist_ok=True)
        except OSError as e:  # pragma: no cover (perms only)
            log.warning("SFOS mirror disabled — cannot mkdir %s: %s",
                          sfos_target, e)
            sfos_target = None

    posts = find_top_quartile_posts(
        platform=platform, metric=metric,
        min_samples=min_samples, db_path=db_path,
    )
    written: list[Path] = []
    for p in posts:
        body = (p.get("body_preview") or "")[:600]
        finger = _structural_fingerprint(body)
        slug = _slugify(f"{p['platform']}-{p['external_id'] or p['id']}")
        content = _render_skill(body, finger, p, metric=metric)

        path = target / f"{slug}.md"
        path.write_text(content, encoding="utf-8")
        written.append(path)

        if sfos_target is not None:
            try:
                (sfos_target / f"{slug}.md").write_text(content, encoding="utf-8")
            except OSError as e:  # pragma: no cover
                log.warning("SFOS mirror write failed for %s: %s", slug, e)

        log.info("promoted high-engagement post to skill",
                  extra={"platform": p["platform"], "peak": p["peak"],
                          "path": str(path),
                          "sfos_mirror": str(sfos_target) if sfos_target else None})
    return written


def _render_skill(body: str, finger: dict, row: dict, *, metric: str) -> str:
    """Markdown body for an auto-promoted skill file. Idempotent."""
    plat = row["platform"]
    posted = row.get("posted_at", "")
    return f"""---
name: learned-{plat}-{_slugify(row.get('external_id') or str(row['id']))}
description: Auto-promoted skill from a top-quartile {plat} post (peak {metric} = {row['peak']}). Reference its structure when drafting future {plat} content for similar projects.
type: learned-skill
auto_promoted: true
source_post_id: {row.get('external_id')}
posted_at: {posted}
---

# Auto-promoted skill — {plat} top-quartile pattern

This post landed in the top 25% of all {plat} posts by `{metric}` count
(peak: **{row['peak']}**). Future {plat} drafts on similar topics should
study its structure.

## Structural fingerprint

| Feature | Value |
|---|---|
| Character count | {finger['char_count']} |
| Line count | {finger['line_count']} |
| Opening pattern | `{finger['opening_pattern']}` |
| Hashtag count | {finger['hashtag_count']} |
| Has URL | {finger['has_url']} |
| Has code block | {finger['has_code_block']} |
| Exclamation count | {finger['exclamation_count']} |

## The post (excerpt)

```
{body}
```

## How to apply

When drafting future {plat} posts:

1. Aim for ~{finger['char_count']} chars.
2. Open with the same pattern: **{finger['opening_pattern']}**.
3. {'Include' if finger['has_url'] else 'Skip'} a URL.
4. {'Include' if finger['has_code_block'] else 'Skip'} a code block.
5. Keep hashtags ≤ {finger['hashtag_count']}.

This skill was auto-promoted by `marketing_agent.skill_promoter`.
Re-run `marketing-agent skills promote` after new engagement data lands.
"""
