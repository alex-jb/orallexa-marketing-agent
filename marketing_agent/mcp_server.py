"""MCP server — expose Marketing Agent tools to Claude Code / Claude Desktop / Cursor / Zed.

Why MCP? Solo OSS founders already live in Claude Code. Asking them to learn
another CLI is friction. With this server installed, they can say
"draft today's posts for my repo" and Claude invokes our tools directly.

Install:
    pip install "orallexa-marketing-agent[mcp]"

Configure (Claude Desktop / Code):
    {
      "mcpServers": {
        "marketing-agent": {
          "command": "marketing-agent-mcp"
        }
      }
    }

Tools exposed:
    - draft_posts        Generate platform-specific drafts for a project
    - submit_to_queue    Save a draft for human review
    - list_queue         List items in pending/approved/posted/rejected
    - engagement_top     Show top-performing past posts
    - optimal_time       Best time to post per platform (hour-of-week)
    - bandit_stats       Variant performance posterior
    - launch_plan        Generate a 30/60/90-day launch plan
"""
from __future__ import annotations
import sys
from typing import Optional

from marketing_agent import (
    ApprovalQueue, GenerationMode, Orchestrator, Platform, Project,
)
from marketing_agent.bandit import VariantBandit
from marketing_agent.best_time import optimal_post_time, report as bt_report
from marketing_agent.engagement import EngagementTracker
from marketing_agent.strategy import write_plan


def main() -> int:
    """Entry point installed as `marketing-agent-mcp`."""
    try:
        from fastmcp import FastMCP
    except ImportError:
        print("fastmcp not installed. Install with: "
              "pip install 'orallexa-marketing-agent[mcp]'", file=sys.stderr)
        return 2

    mcp = FastMCP("marketing-agent")

    @mcp.tool()
    def draft_posts(
        name: str,
        tagline: str,
        platforms: list[str],
        description: Optional[str] = None,
        github_url: Optional[str] = None,
        recent_changes: Optional[list[str]] = None,
        mode: str = "template",
        n_variants: int = 1,
    ) -> list[dict]:
        """Generate platform-specific marketing drafts for a project.

        Args:
            name: Short project name, e.g. "Orallexa".
            tagline: One-line pitch (≤200 chars).
            platforms: List of platforms — any of x, reddit, linkedin, dev_to,
                       bluesky, mastodon.
            mode: template (no LLM, deterministic) | llm (Claude) | hybrid.
            n_variants: For X, generate this many stylistic variants and have
                        the bandit pick one.

        Returns: list of {platform, body, title, char_count, variant_key}.
        """
        project = Project(
            name=name, tagline=tagline, description=description,
            github_url=github_url, recent_changes=recent_changes or [],
        )
        gen_mode = GenerationMode(mode)
        orch = Orchestrator(mode=gen_mode)
        posts = orch.generate(
            project, [Platform(p) for p in platforms], n_variants=n_variants,
        )
        return [{"platform": p.platform.value, "body": p.body,
                  "title": p.title, "char_count": p.char_count,
                  "variant_key": p.variant_key} for p in posts]

    @mcp.tool()
    def submit_to_queue(platform: str, body: str, project_name: str,
                          title: Optional[str] = None,
                          target: Optional[str] = None) -> str:
        """Save a draft to the approval queue for human review.

        Returns the path of the saved markdown file.
        """
        from marketing_agent.types import Post
        post = Post(platform=Platform(platform), body=body,
                     title=title, target=target)
        q = ApprovalQueue()
        path = q.submit(post, project_name, generated_by="mcp")
        return str(path)

    @mcp.tool()
    def list_queue(status: str = "pending") -> list[str]:
        """List items in the approval queue.

        Args:
            status: pending | approved | posted | rejected.
        """
        if status not in ("pending", "approved", "posted", "rejected"):
            return [f"invalid status: {status}"]
        q = ApprovalQueue()
        return [f.name for f in sorted((q.root / status).glob("*.md"))]

    @mcp.tool()
    def engagement_top(metric: str = "like", platform: Optional[str] = None,
                         limit: int = 10) -> list[dict]:
        """Show top-performing past posts by metric.

        Args:
            metric: like | reply | retweet | save | etc.
            platform: filter to one platform, or None for all.
            limit: max rows to return.
        """
        plat = Platform(platform) if platform else None
        return EngagementTracker().top_posts(
            platform=plat, metric=metric, limit=limit)

    @mcp.tool()
    def optimal_time(platform: str, project: Optional[str] = None,
                       metric: str = "like") -> dict:
        """Best time to post on a platform, based on engagement history.

        Returns: {weekday, hour_utc, source}. source = "data" if learned from
        history, "default" if falling back to industry-default times.
        """
        weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        wd, h, src = optimal_post_time(Platform(platform),
                                          project_name=project, metric=metric)
        return {"weekday": weekdays[wd], "weekday_idx": wd,
                "hour_utc": h, "source": src}

    @mcp.tool()
    def bandit_stats() -> list[dict]:
        """Variant bandit per-arm posterior (Beta distribution params + mean)."""
        return VariantBandit().stats()

    @mcp.tool()
    def launch_plan(name: str, tagline: str,
                      description: Optional[str] = None,
                      tags: Optional[list[str]] = None,
                      days: int = 30,
                      ph_launch_day: int = 0,
                      use_llm: bool = False,
                      out_dir: str = "docs") -> str:
        """Generate a 30/60/90-day launch plan markdown file.

        Args:
            days: 30 | 60 | 90.
            ph_launch_day: Day offset of Product Hunt launch. HN/long-form
                           retros schedule relative to this.
            use_llm: Use Claude to draft a custom plan (requires ANTHROPIC_API_KEY).

        Returns: path to the written markdown file.
        """
        project = Project(name=name, tagline=tagline,
                            description=description, tags=tags or [])
        return write_plan(project, days=days,
                            ph_launch_day=ph_launch_day,
                            use_llm=use_llm, out_dir=out_dir)

    mcp.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
