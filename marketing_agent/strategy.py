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
import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from marketing_agent.types import Platform, Project


class LaunchAction(BaseModel):
    """One scheduled action in the launch plan."""
    day: int = Field(..., ge=0, le=90, description="Day offset from launch anchor (0 = launch day)")
    platform: Platform
    kind: str = Field(..., description="post / thread / reply_burst / engage")
    topic: str = Field(..., max_length=200, description="What to talk about")
    target: Optional[str] = Field(None, description="Subreddit, account list, etc.")
    rationale: str = Field("", max_length=500, description="Why this action this day")


class LaunchPlan(BaseModel):
    project_name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    duration_days: int = 30
    ph_launch_day: int = Field(
        0,
        description="Day offset where Product Hunt launch happens. HN and "
                    "long-form follow-ups schedule relative to this.",
    )
    actions: list[LaunchAction]

    def to_markdown(self) -> str:
        out = [f"# Launch plan — {self.project_name}",
               f"\n*Generated {self.created_at.date().isoformat()} · "
               f"{self.duration_days} days · PH anchor day {self.ph_launch_day}*\n"]
        actions_by_day: dict[int, list[LaunchAction]] = {}
        for a in self.actions:
            actions_by_day.setdefault(a.day, []).append(a)
        for day in sorted(actions_by_day):
            rel = day - self.ph_launch_day
            rel_label = f" / PH{rel:+d}" if self.ph_launch_day else ""
            out.append(f"\n## Day {day}{rel_label}")
            for a in actions_by_day[day]:
                out.append(f"\n- **{a.platform.value} · {a.kind}** — {a.topic}")
                if a.target:
                    out.append(f"  - target: `{a.target}`")
                if a.rationale:
                    out.append(f"  - why: {a.rationale}")
        return "\n".join(out)


def default_plan(project: Project, *, days: int = 30,
                  ph_launch_day: int = 0) -> LaunchPlan:
    """A reasonable default schedule when no LLM key set.

    Args:
        days: total plan duration. Supports 30 / 60 / 90.
        ph_launch_day: day offset of Product Hunt launch (default 0 = today).
            HN, Show HN, and long-form retros schedule relative to PH because
            HN values "validated on PH first" narratives over rough launches.
    """
    ph = ph_launch_day
    actions = [
        # ─── Pre-PH ramp (only if ph_launch_day > 0) ─────────────────
        *([LaunchAction(day=max(0, ph - 7), platform=Platform.X, kind="post",
                          topic=f"Coming soon: {project.name} — PH launch in 1 week",
                          rationale="Pre-PH teaser builds the warm audience that votes")]
          if ph > 0 else []),
        *([LaunchAction(day=max(0, ph - 1), platform=Platform.X, kind="post",
                          topic="PH launch tomorrow — last call to follow",
                          rationale="Day-before reminder; PH morning reach hinges on this")]
          if ph > 0 else []),

        # ─── PH launch day ───────────────────────────────────────────
        LaunchAction(day=ph, platform=Platform.X, kind="thread",
                     topic=f"Launch announcement: {project.name}",
                     rationale="PH-day anchor; thread because more content drives more reach"),
        LaunchAction(day=ph, platform=Platform.LINKEDIN, kind="post",
                     topic=f"Launch announcement: {project.name}",
                     rationale="LinkedIn launch covers professional network"),

        # ─── PH+1 to PH+5: organic spread ───────────────────────────
        LaunchAction(day=ph + 1, platform=Platform.REDDIT, kind="post",
                     topic="Show r/* — tell the build story",
                     target="MachineLearning",
                     rationale="Reddit day after PH avoids competing with PH window"),
        LaunchAction(day=ph + 2, platform=Platform.REDDIT, kind="post",
                     topic="Different subreddit, different framing",
                     target="programming",
                     rationale="2nd subreddit — but different headline + body"),
        LaunchAction(day=ph + 3, platform=Platform.X, kind="thread",
                     topic="Behind-the-scenes / technical deep dive",
                     rationale="Day 3 reactivates dormant followers"),
        LaunchAction(day=ph + 5, platform=Platform.DEV_TO, kind="post",
                     topic="Long-form post mortem / how it works",
                     rationale="DEV.to is patient and SEO-friendly"),

        # ─── PH+7 to PH+14: HN window (after PH metrics exist) ──────
        LaunchAction(day=ph + 7, platform=Platform.X, kind="post",
                     topic="Week 1 retro — lessons learned + PH numbers",
                     rationale="Build-in-public weekly cadence; use real PH metrics"),
        LaunchAction(day=ph + 10, platform=Platform.HACKER_NEWS, kind="post",
                     topic="Show HN — built it, validated on PH, here's what worked",
                     rationale="HN rewards refined narratives with PH receipts attached"),
        LaunchAction(day=ph + 14, platform=Platform.X, kind="thread",
                     topic="Week 2 retro + numbers + asks",
                     rationale="Mid-month status update"),

        # ─── PH+21 to PH+28: month-1 retro ──────────────────────────
        LaunchAction(day=min(ph + 21, days - 1), platform=Platform.X, kind="post",
                     topic="Week 3 lesson — what worked, what didn't",
                     rationale="Honest content compounds trust"),
        LaunchAction(day=min(ph + 28, days - 1), platform=Platform.LINKEDIN, kind="post",
                     topic="Month 1 retrospective — metrics + what's next",
                     rationale="LinkedIn rewards 30-day retros"),
    ]

    # ─── Long-tail (60/90-day plans) ─────────────────────────────
    if days >= 60:
        actions.extend([
            LaunchAction(day=min(ph + 35, days - 1), platform=Platform.X, kind="post",
                          topic="Customer story / case study from a real user",
                          rationale="Social proof is the easiest week-5 win"),
            LaunchAction(day=min(ph + 45, days - 1), platform=Platform.DEV_TO, kind="post",
                          topic="Deep technical post — architecture decisions",
                          rationale="Long-tail SEO; ranks for months"),
            LaunchAction(day=min(ph + 56, days - 1), platform=Platform.LINKEDIN, kind="post",
                          topic="Month 2 retrospective — metrics + lessons",
                          rationale="Cadence: monthly retros build founder authority"),
        ])
    if days >= 90:
        actions.extend([
            LaunchAction(day=min(ph + 70, days - 1), platform=Platform.X, kind="thread",
                          topic="Quarter 1 milestone thread — the journey so far",
                          rationale="Quarterly milestones make great evergreen content"),
            LaunchAction(day=min(ph + 84, days - 1), platform=Platform.LINKEDIN, kind="post",
                          topic="Q1 review — revenue/users/learnings",
                          rationale="Quarterly retros build sustained credibility"),
        ])

    return LaunchPlan(
        project_name=project.name,
        duration_days=days,
        ph_launch_day=ph_launch_day,
        actions=actions,
    )


def llm_plan(project: Project, *, days: int = 30,
              ph_launch_day: int = 0) -> LaunchPlan:
    """Use Claude to draft a custom plan. Falls back to default on any failure.

    Uses claude-haiku-4-5 — generating 8-15 short JSON actions doesn't need
    Sonnet's reasoning; Haiku is ~4x cheaper and 2x faster.
    """
    try:
        from marketing_agent.llm.anthropic_compat import (
            AnthropicClient, DEFAULT_HAIKU_MODEL,
        )
        from marketing_agent.cost import USAGE_LOG_PATH
        client = AnthropicClient(usage_log_path=USAGE_LOG_PATH)
        if not client.configured:
            return default_plan(project, days=days, ph_launch_day=ph_launch_day)

        ph = ph_launch_day
        n_actions = 8 + (days // 30) * 4  # 12 for 60-day, 16 for 90-day
        prompt = f"""You are a launch strategist for an indie OSS / AI project. Output a {days}-day launch plan as STRICT JSON.

Project:
  name: {project.name}
  tagline: {project.tagline}
  description: {project.description or '(none)'}
  target audience: {project.target_audience or 'OSS / AI builders'}
  tags: {', '.join(project.tags) if project.tags else '(none)'}

Launch context:
  Total plan duration: {days} days
  Product Hunt launch day: {ph} (0 means today; if >0, plan pre-PH ramp)

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
- Generate {n_actions - 2}-{n_actions + 3} actions across {days} days
- day must satisfy 0 <= day <= {days - 1}
- PH launch is day {ph}. Plan teaser/reminder posts BEFORE day {ph} if ph > 0
- HN should be 7-14 days AFTER PH launch (need PH metrics first; HN rewards "validated on PH" narratives over rough launches)
- Don't burst the same platform 3x in 2 days
- Reddit posts go in different subreddits with different framings
- For 60+ day plans: include long-tail content (case studies, deep technical posts, monthly retros)
- For 90+ day plans: add quarterly milestone posts
- Each rationale ≤ 200 chars and explains the timing+platform choice

Output ONLY the JSON, no preamble."""

        resp, err = client.messages_create(
            model=DEFAULT_HAIKU_MODEL, max_tokens=2500,
            messages=[{"role": "user", "content": prompt}],
        )
        if err is not None or resp is None:
            return default_plan(project, days=days, ph_launch_day=ph_launch_day)
        text = AnthropicClient.extract_text(resp).strip()
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
            ph_launch_day=ph_launch_day,
            actions=actions,
        )
    except Exception:
        return default_plan(project, days=days, ph_launch_day=ph_launch_day)


def write_plan(project: Project, *, days: int = 30,
                ph_launch_day: int = 0,
                use_llm: bool = True, out_dir: Optional[str] = None) -> str:
    """Generate a plan and write it to docs/launch_plan_*.md. Return the path."""
    from pathlib import Path
    if use_llm:
        plan = llm_plan(project, days=days, ph_launch_day=ph_launch_day)
    else:
        plan = default_plan(project, days=days, ph_launch_day=ph_launch_day)
    target = Path(out_dir) if out_dir else Path("docs")
    target.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", project.name.lower()).strip("-")
    fname = f"launch_plan_{slug}_{datetime.utcnow().strftime('%Y%m%d')}.md"
    path = target / fname
    path.write_text(plan.to_markdown())
    return str(path)
