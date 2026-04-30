"""Trends — proactive content ideation from free public sources.

The reactive path (project + commits → posts) is in `content/generator.py`.
This module is the proactive complement: scan what's trending in the
user's niche RIGHT NOW so the agent can suggest fresh angles to write
about, not just rehash recent commits.

Three sources, all free, all stdlib-only:

  1. GitHub trending pages — public HTML, scraped with BeautifulSoup-free
     regex (so no extra dep). Filtered by language tag.
  2. Hacker News — official Algolia API (no key needed, free, stable).
  3. Reddit — uses PRAW when configured; falls back to public JSON
     `https://reddit.com/r/<sub>/.json` (no auth needed for read).

Aggregator de-dupes overlapping topics and outputs a ranked Markdown
digest:

    marketing-agent trends --tags ai-agent claude --subreddits MachineLearning
    → docs/trends_2026-04-30.md
"""
from __future__ import annotations
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from marketing_agent.logging import get_logger

log = get_logger(__name__)


@dataclass
class TrendItem:
    """One trending item from any source."""
    source: str          # "github" | "hn" | "reddit"
    title: str
    url: str
    score: int = 0       # stars / points / upvotes
    n_comments: int = 0
    summary: str = ""
    tags: list[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


# ───────────────── GitHub trending ─────────────────


def _http_get(url: str, *, timeout: int = 10) -> Optional[str]:
    """Stdlib HTTP GET with realistic User-Agent. None on any failure."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": ("Mozilla/5.0 (compatible; orallexa-marketing-agent/0.15)"),
            "Accept": "text/html,application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        log.debug("HTTP GET failed: %s — %s", url, e)
        return None


_GH_REPO_RE = re.compile(
    r'<h2 class="h3 lh-condensed">\s*<a[^>]*href="/([^/]+/[^"]+)"',
    re.DOTALL,
)
_GH_DESC_RE = re.compile(
    r'<p class="col-9 color-fg-muted my-1 pr-4">\s*(.*?)\s*</p>',
    re.DOTALL,
)
_GH_STARS_RE = re.compile(
    r'<a[^>]*href="/[^"]+/stargazers">\s*[^<]*?([\d,]+)\s*</a>',
)


def trending_github_repos(language: str = "",
                            since: str = "weekly",
                            limit: int = 25) -> list[TrendItem]:
    """Scrape GitHub trending. Returns up to `limit` repos.

    `language`: pass an empty string for all languages, or e.g. "python".
    `since`: 'daily' | 'weekly' | 'monthly'.
    """
    qs = []
    if since:
        qs.append(f"since={since}")
    base = f"https://github.com/trending/{urllib.parse.quote(language)}" if language \
        else "https://github.com/trending"
    if qs:
        base += "?" + "&".join(qs)

    html = _http_get(base)
    if not html:
        return []

    items: list[TrendItem] = []
    repos = _GH_REPO_RE.findall(html)[:limit]
    descs = _GH_DESC_RE.findall(html)
    stars = _GH_STARS_RE.findall(html)

    for i, repo in enumerate(repos):
        repo_clean = repo.split('"')[0].strip()
        desc = (descs[i] if i < len(descs) else "").strip()
        # Strip residual HTML
        desc = re.sub(r"<[^>]+>", "", desc).strip()
        try:
            star_count = int(stars[i].replace(",", "")) if i < len(stars) else 0
        except ValueError:
            star_count = 0
        items.append(TrendItem(
            source="github",
            title=repo_clean,
            url=f"https://github.com/{repo_clean}",
            score=star_count,
            summary=desc[:240],
            tags=[language] if language else [],
        ))
    return items


# ───────────────── Hacker News (Algolia) ─────────────────


def trending_hn_posts(*, query: str = "",
                        hours: int = 24,
                        min_points: int = 50,
                        limit: int = 25) -> list[TrendItem]:
    """Pull HN front-page-quality posts via Algolia search.

    `query`: e.g. "agent" or "" for all. Algolia handles full-text.
    """
    since_ts = int((datetime.now(timezone.utc) -
                      timedelta(hours=hours)).timestamp())
    params = {
        "tags": "story",
        "numericFilters": f"created_at_i>{since_ts},points>={min_points}",
        "hitsPerPage": str(limit),
    }
    if query:
        params["query"] = query
    url = ("https://hn.algolia.com/api/v1/search?"
           + urllib.parse.urlencode(params))

    body = _http_get(url)
    if not body:
        return []
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return []

    items: list[TrendItem] = []
    for hit in data.get("hits", []):
        items.append(TrendItem(
            source="hn",
            title=hit.get("title", "(no title)"),
            url=(hit.get("url")
                  or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"),
            score=int(hit.get("points", 0) or 0),
            n_comments=int(hit.get("num_comments", 0) or 0),
            summary="",
            tags=hit.get("_tags", []),
        ))
    return items


# ───────────────── Reddit (public JSON, no auth) ─────────────────


def trending_subreddit_posts(subreddit: str, *,
                                hours: int = 24,
                                min_score: int = 25,
                                limit: int = 25) -> list[TrendItem]:
    """Public-JSON read on r/<subreddit>/top.json. No PRAW needed for read."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp()
    period = "day" if hours <= 24 else ("week" if hours <= 168 else "month")
    url = (f"https://www.reddit.com/r/{urllib.parse.quote(subreddit)}/top.json"
           f"?t={period}&limit={limit}")

    body = _http_get(url)
    if not body:
        return []
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return []

    items: list[TrendItem] = []
    for child in data.get("data", {}).get("children", []):
        d = child.get("data", {})
        if d.get("created_utc", 0) < cutoff:
            continue
        if d.get("score", 0) < min_score:
            continue
        items.append(TrendItem(
            source="reddit",
            title=d.get("title", "(no title)"),
            url=f"https://reddit.com{d.get('permalink', '')}",
            score=int(d.get("score", 0) or 0),
            n_comments=int(d.get("num_comments", 0) or 0),
            summary=(d.get("selftext", "") or "")[:240],
            tags=[subreddit],
        ))
    return items


# ───────────────── Aggregator ─────────────────


def aggregate(*, github_languages: list[str] | None = None,
                hn_query: str = "",
                subreddits: list[str] | None = None,
                hours: int = 168,
                limit_per_source: int = 15) -> list[TrendItem]:
    """One call → aggregated list across all 3 sources."""
    out: list[TrendItem] = []
    for lang in (github_languages or [""]):
        out.extend(trending_github_repos(
            language=lang, since="weekly" if hours > 48 else "daily",
            limit=limit_per_source,
        ))
    out.extend(trending_hn_posts(
        query=hn_query, hours=hours, min_points=50,
        limit=limit_per_source,
    ))
    for sub in (subreddits or []):
        out.extend(trending_subreddit_posts(
            sub, hours=hours, min_score=25, limit=limit_per_source,
        ))
    # De-dupe by URL — same project can appear from multiple sources
    seen: set[str] = set()
    deduped: list[TrendItem] = []
    for it in out:
        if it.url in seen:
            continue
        seen.add(it.url)
        deduped.append(it)
    # Rank: simple normalized score per source, then sum
    return sorted(deduped, key=lambda i: i.score, reverse=True)


def render_markdown(items: list[TrendItem], *,
                       max_per_source: int = 10) -> str:
    """Markdown digest grouped by source. Top N per source."""
    if not items:
        return ("# Trends digest\n\n"
                "_No trending items found in the configured window._\n")

    by_src: dict[str, list[TrendItem]] = {}
    for it in items:
        by_src.setdefault(it.source, []).append(it)

    lines = [
        "# Trends digest",
        f"\n*Generated {datetime.now(timezone.utc).isoformat()} · "
        f"{len(items)} unique items · {len(by_src)} source(s)*\n",
    ]
    section_titles = {
        "github": "## 🐙 GitHub trending",
        "hn":     "## 📰 Hacker News",
        "reddit": "## 🤖 Reddit",
    }
    for src in ("github", "hn", "reddit"):
        if src not in by_src:
            continue
        lines.append(section_titles[src])
        lines.append("")
        for it in by_src[src][:max_per_source]:
            stats = []
            if it.score:
                stats.append(f"⭐ {it.score}" if src == "github"
                              else f"▲ {it.score}")
            if it.n_comments:
                stats.append(f"💬 {it.n_comments}")
            stats_s = "  ".join(stats)
            lines.append(f"### [{it.title}]({it.url})")
            if stats_s:
                lines.append(f"*{stats_s}*")
            if it.summary:
                lines.append(f"\n{it.summary}\n")
            lines.append("")
    return "\n".join(lines)
