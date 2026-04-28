"""VibeXForge integration client.

VibeXForge (vibexforge.com) is the sister product where AI projects are
submitted, scored across 5 dimensions by Claude, and represented as
collectible hero cards that evolve through 6 stages based on real
traction events.

This client lets the Marketing Agent:
  1. Pull project metadata from VibeXForge (so a single source of truth)
  2. Push engagement events back so card stages advance based on the
     real traction this agent generated

Auth: VIBEXFORGE_API_URL + VIBEXFORGE_API_TOKEN env vars. The token is
a service token issued from the VibeXForge admin dashboard.

Without those env vars, this client is a no-op so users who don't run
VibeXForge can still use the Marketing Agent standalone.
"""
from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import Optional

from marketing_agent.types import Engagement, Project


class VibeXForgeClient:
    """Pull projects + push engagement events from/to VibeXForge."""

    DEFAULT_URL = "https://vibexforge.com"

    def __init__(self, base_url: Optional[str] = None,
                  token: Optional[str] = None):
        self.base = (base_url or os.getenv("VIBEXFORGE_API_URL")
                     or self.DEFAULT_URL).rstrip("/")
        self.token = token or os.getenv("VIBEXFORGE_API_TOKEN")

    def is_configured(self) -> bool:
        return bool(self.token)

    def fetch_project(self, project_id: str) -> Optional[Project]:
        """GET /api/projects/{id} → return as marketing_agent.Project."""
        if not self.is_configured():
            return None
        import requests
        try:
            resp = requests.get(
                f"{self.base}/api/projects/{project_id}",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return None

        return Project(
            name=data.get("name", project_id),
            tagline=data.get("tagline", ""),
            description=data.get("description"),
            github_url=data.get("github_url"),
            website_url=data.get("website_url"),
            tags=data.get("tags", []),
            target_audience=data.get("target_audience"),
            recent_changes=data.get("recent_changes", []),
        )

    def push_engagement(self, project_id: str,
                          engagement: Engagement) -> bool:
        """POST /api/events with the engagement.

        VibeXForge's card-evolution engine reads these events and
        promotes cards through stages (Seed → Active → Growing → ...).
        Returns True on 2xx, False otherwise (incl. when not configured).
        """
        if not self.is_configured():
            return False
        import requests
        try:
            resp = requests.post(
                f"{self.base}/api/events",
                headers={"Authorization": f"Bearer {self.token}",
                         "Content-Type": "application/json"},
                json={
                    "project_id": project_id,
                    "type": "external_engagement",
                    "platform": engagement.platform.value,
                    "metric": engagement.metric,
                    "count": engagement.count,
                    "ts": engagement.timestamp.isoformat(),
                    "actor": engagement.actor,
                    "source": "orallexa-marketing-agent",
                },
                timeout=10,
            )
            return 200 <= resp.status_code < 300
        except Exception:
            return False

    def push_post_event(self, project_id: str, *, platform: str,
                          post_url: str) -> bool:
        """Quick helper: notify VibeXForge that we just posted to a platform."""
        if not self.is_configured():
            return False
        import requests
        try:
            resp = requests.post(
                f"{self.base}/api/events",
                headers={"Authorization": f"Bearer {self.token}",
                         "Content-Type": "application/json"},
                json={
                    "project_id": project_id,
                    "type": "post_published",
                    "platform": platform,
                    "url": post_url,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "source": "orallexa-marketing-agent",
                },
                timeout=10,
            )
            return 200 <= resp.status_code < 300
        except Exception:
            return False
