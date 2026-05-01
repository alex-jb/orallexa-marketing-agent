"""VibeX top-of-feed → TrendItem stream.

Reads the top N most-traction VibeX projects from the last 24-72h and
surfaces them as TrendItem entries (same shape as GitHub/HN/Reddit
trending). Lands in `trends_to_drafts` automatically — your daily
marketing cron drafts platform-specific posts highlighting whatever
just hit Breakout/Legend/Myth on your own platform.

Why: the most authentic "what's interesting in AI today" content for
*your* audience comes from your own users. Beats generic GitHub
trending for relevance, beats Reddit scraping for signal-to-noise.

Auth: SUPABASE_PERSONAL_ACCESS_TOKEN + VIBEX_PROJECT_REF (or
SUPABASE_PROJECT_REF). $0 API cost — pure SQL through Supabase
Management API.
"""
from __future__ import annotations
import json
import os
import urllib.error
import urllib.request

from marketing_agent.trends import TrendItem


VIBEX_TOP_FEED_SQL = """
SELECT
  p.id              AS project_id,
  p.title           AS title,
  p.tagline         AS tagline,
  p.upvotes         AS upvotes,
  p.plays           AS plays,
  p.views           AS views,
  p.evolution_stage AS stage,
  p.created_at      AS created_at,
  c.name            AS creator_name
FROM projects p
LEFT JOIN creators c ON c.id = p.creator_id
WHERE p.created_at >= now() - interval '%(hours)s hours'
  AND p.evolution_stage IS NOT NULL
ORDER BY
  CASE p.evolution_stage
    WHEN 'Myth' THEN 6
    WHEN 'Legend' THEN 5
    WHEN 'Breakout' THEN 4
    WHEN 'Growing' THEN 3
    WHEN 'Active' THEN 2
    WHEN 'Seed' THEN 1
    ELSE 0
  END DESC,
  p.upvotes DESC,
  p.plays DESC
LIMIT %(limit)s
""".strip()


def _query(sql: str, *, token: str, project_ref: str) -> list[dict]:
    url = f"https://api.supabase.com/v1/projects/{project_ref}/database/query"
    body = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Authorization": f"Bearer {token}",
                  "Content-Type": "application/json",
                  "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode())
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("result", "rows", "data"):
            if key in data and isinstance(data[key], list):
                return data[key]
    return []


def trending_vibex_projects(
    *,
    hours: int = 48,
    limit: int = 10,
    project_ref: str | None = None,
    token: str | None = None,
) -> list[TrendItem]:
    """Return top recent VibeX projects ranked by stage then traction.

    Each project becomes one TrendItem with source="vibex". The
    `score` field gets the upvote count; `n_comments` = plays;
    `summary` includes the evolution stage so downstream content
    generation can riff on "this just hit Breakout" stories.
    """
    token = token or os.getenv("SUPABASE_PERSONAL_ACCESS_TOKEN") or ""
    project_ref = (project_ref or os.getenv("VIBEX_PROJECT_REF")
                    or os.getenv("SUPABASE_PROJECT_REF") or "")
    if not token or not project_ref:
        return []

    sql = VIBEX_TOP_FEED_SQL % {"hours": int(hours), "limit": int(limit)}
    try:
        rows = _query(sql, token=token, project_ref=project_ref)
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, TimeoutError):
        return []
    except Exception:
        return []

    out: list[TrendItem] = []
    for row in rows:
        project_id = row.get("project_id") or ""
        title = (row.get("title") or "(untitled)").strip()
        tagline = (row.get("tagline") or "").strip()
        stage = row.get("stage") or "Seed"
        upvotes = int(row.get("upvotes") or 0)
        plays = int(row.get("plays") or 0)
        creator_name = (row.get("creator_name") or "").strip()
        summary_parts = [f"Stage: **{stage}**"]
        if tagline:
            summary_parts.append(tagline)
        if creator_name:
            summary_parts.append(f"by {creator_name}")
        out.append(TrendItem(
            source="vibex",
            title=title,
            url=f"https://www.vibexforge.com/project/{project_id}",
            score=upvotes,
            n_comments=plays,
            summary=" — ".join(summary_parts),
            tags=[stage.lower(), "vibex"],
        ))
    return out
