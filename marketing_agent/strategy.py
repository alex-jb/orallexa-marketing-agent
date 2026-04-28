"""Strategy Agent — given a project + goals, produce a launch plan.

Following the "Planner + Executor" production agent pattern:
  - Planner Agent (this module) decides WHAT and WHEN
  - Executor Agent (the existing Orchestrator + scheduling) does the posting

Output: a 30-day launch plan as a Pydantic LaunchPlan, written to
docs/launch_plan_<project>_<date>.md for human review.

Without ANTHROPIC_API_KEY, falls back to a sensible default plan based
on project metadata.
"""
from __future__ import annotations
import json
import os
import re
from datetime import datetime, timedelta
from typing import Optional

from pydantic import BaseModel, Field

from marketing_agent.types import Platform, Project


class LaunchAction(BaseModel):
    """One scheduled action in the launch plan."""
    day: int = Field(..., ge=0, le=60, description="Day offset from launch (0 = launch day)")
    platform: Platform
    kind: str = Field(..., description="post / thread / reply_burst / engage")
    topic: str = Field(..., max_length=200, description="What to talk about")
    target: Optional[str] = Field(None, description="Subreddit, account list, etc.")
    rationale: str = Field("", max_length=500, description="Why this action this day")


class LaunchPlan(BaseModel):
    project_name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    duration_days: int = 30
    actions: list[LaunchAction]

    def to_markdown(self) -> str:
        out = [f"# Launch plan — {self.project_name}",
               f"\n*Generated {self.created_at.date().isoformat()} · {self.duration_days} days*\n"]
        actions_by_day: dict[int, list[LaunchAction]] = {}
        for a in self.actions:
            actions_by_day.setdefault(a.day, []).append(a)
        for day in sorted(actions_by_day):
            out.append(f"\n## Day {day}")
            for a in actions_by_day[day]:
                out.append(f"\n- **{a.platform.value} · {a.kind}** — {a.topic}")
                if a.target:
                    out.append(f"  - target: `{a.target}`")
                if a.rationale:
                    out.append(f"  - why: {a.rationale}")
        return "\n".join(out)


def default_plan(project: Project, *, days: int = 30) -> LaunchPlan:
    """A reasonable default schedule when no LLM key set."""
    actions = [
        LaunchAction(day=0, platform=Platform.X, kind="thread",
                     topic=f"Launch announcement: {project.name}",
                     rationale="Day 0 anchor; thread because more content drives more reach"),
        LaunchAction(day=0, platform=Platform.LINKEDIN, kind="post",
                     topic=f"Launch announcement: {project.name}",
                     rationale="LinkedIn launch covers professional network"),
        LaunchAction(day=1, platform=Platform.REDDIT, kind="post",
                     topic="Show r/* — tell the build story",
                     target="MachineLearning",
                     rationale="Reddit tomorrow, not today, to avoid burnout"),
        LaunchAction(day=2, platform=Platform.REDDIT, kind="post",
                     topic="Different subreddit, different framing",
                     target="programming",
                     rationale="2nd subreddit — but different headline + body"),
        LaunchAction(day=3, platform=Platform.X, kind="thread",
                     topic="Behind-the-scenes / technical deep dive",
                     rationale="Day 3 reactivates dormant followers"),
        LaunchAction(day=5, platform=Platform.DEV_TO, kind="post",
                     topic="Long-form post mortem / how it works",
                     rationale="DEV.to is patient and SEO-friendly"),
        LaunchAction(day=7, platform=Platform.X, kind="post",
                     topic="Week 1 retro — lessons learned",
                     rationale="Build-in-public weekly cadence"),
        LaunchAction(day=10, platform=Platform.HACKER_NEWS, kind="post",
                     topic="Show HN — best time after week 1 lessons",
                     rationale="HN rewards refined narratives over rough launches"),
        LaunchAction(day=14, platform=Platform.X, kind="thread",
                     topic="Week 2 retro + numbers + asks",
                     rationale="Mid-month status update"),
        LaunchAction(day=21, platform=Platform.X, kind="post",
                     topic="Week 3 lesson — pick one tactic that worked, one that didn't",
                     rationale="Honest content compounds trust"),
        LaunchAction(day=28, platform=Platform.LINKEDIN, kind="post",
                     topic="Month 1 retrospective — metrics + what's next",
                     rationale="LinkedIn rewards 30-day retros"),
    ]
    return LaunchPlan(
        project_name=project.name,
        duration_days=days,
        actions=actions,
    )


def llm_plan(project: Project, *, days: int = 30) -> LaunchPlan:
    """Use Claude to draft a custom plan. Falls back to default on any failure."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return default_plan(project, days=days)

    try:
        from anthropic import Anthropic

        prompt = f"""You are a launch strategist for an indie OSS / AI project. Output a {days}-day launch plan as STRICT JSON.

Project:
  name: {project.name}
  tagline: {project.tagline}
  description: {project.description or '(none)'}
  target audience: {project.target_audience or 'OSS / AI builders'}
  tags: {', '.join(project.tags) if project.tags else '(none)'}

Output JSON shape:
{{
  "actions": [
    {{
      "day": 0,
      "platform": "x|reddit|linkedin|hacker_news|dev_to|bluesky|mastodon|substack",
      "kind": "post|thread|reply_burst|engage",
      "topic": "what to write about",
      "target": "subreddit name or null",
      "rationale": "why this day, this platform, this angle"
    }}
  ]
}}

Rules:
- Generate 8-15 actions across the {days} days
- Day 0 = launch day; max day = {days - 1}
- Don't burst the same platform 3x in 2 days (looks spammy)
- Reddit posts go in different subreddits, with platform-tuned framings
- HN should NOT be on day 0 (rough launches die on HN); aim for day 7-14
- Mix posts, threads, and reply_burst (engage with others' posts)
- Each rationale ≤ 200 chars and explains the timing+platform choice

Output ONLY the JSON, no preamble."""

        client = Anthropic()
        resp = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text).strip()
        if not text.startswith("{"):
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                text = m.group(0)
        data = json.loads(text)
        actions = [LaunchAction(**a) for a in data["actions"]]
        return LaunchPlan(
            project_name=project.name,
            duration_days=days,
            actions=actions,
        )
    except Exception:
        return default_plan(project, days=days)


def write_plan(project: Project, *, days: int = 30,
                use_llm: bool = True, out_dir: Optional[str] = None) -> str:
    """Generate a plan and write it to docs/launch_plan_*.md. Return the path."""
    from pathlib import Path
    plan = llm_plan(project, days=days) if use_llm else default_plan(project, days=days)
    target = Path(out_dir) if out_dir else Path("docs")
    target.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", project.name.lower()).strip("-")
    fname = f"launch_plan_{slug}_{datetime.utcnow().strftime('%Y%m%d')}.md"
    path = target / fname
    path.write_text(plan.to_markdown())
    return str(path)
