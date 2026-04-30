"""Threads (Meta) adapter — production API as of April 2026.

Threads' Graph-style API graduated to general availability in April 2026.
Bots / agent publishing is officially supported, capped at 250 posts per
24h per authenticated user — generous for indie OSS marketing.

Why ship this now:
  - 300M MAU on Threads (Meta-reported) and a strong builder/dev presence
  - Indie-OSS competitors (Postiz / Buffer / Hypefury) are not native to
    Threads yet — first-mover window for marketing-agent

Auth: 2 env vars
  - THREADS_ACCESS_TOKEN — long-lived user access token (Meta App)
  - THREADS_USER_ID      — your numeric Threads user ID

Publish flow (two-step, Meta-style):
  1. POST /v1.0/{user-id}/threads
       media_type=TEXT|IMAGE
       text=...
       image_url=...                (only for IMAGE)
       returns: { id: <creation_id> }
  2. POST /v1.0/{user-id}/threads_publish
       creation_id=<id>
       returns: { id: <post_id> }
"""
from __future__ import annotations
import os
from typing import Optional

from marketing_agent.retry import retry_on_transient
from marketing_agent.types import Platform, Post
from marketing_agent.platforms.base import NotConfigured


class ThreadsAdapter:
    """Threads (Meta) auto-publish adapter."""

    platform = Platform.THREADS

    REQUIRED = ("THREADS_ACCESS_TOKEN", "THREADS_USER_ID")
    BASE = "https://graph.threads.net/v1.0"
    CHAR_LIMIT = 500

    def is_configured(self) -> bool:
        return all(os.getenv(k) for k in self.REQUIRED)

    def dry_run_preview(self, post: Post) -> str:
        body = post.body
        return (
            f"--- Threads preview · {len(body)} chars ---\n"
            f"{body}\n"
            f"--- end ---"
        )

    @retry_on_transient(attempts=3, base_delay=2.0)
    def post(self, post: Post) -> str:
        if not self.is_configured():
            raise NotConfigured(
                "Threads adapter missing env vars: "
                + ", ".join(k for k in self.REQUIRED if not os.getenv(k))
            )
        if len(post.body) > self.CHAR_LIMIT:
            raise ValueError(
                f"Threads post too long: {len(post.body)} > {self.CHAR_LIMIT}")

        import requests  # lazy import

        token = os.getenv("THREADS_ACCESS_TOKEN")
        user_id = os.getenv("THREADS_USER_ID")
        headers = {"Authorization": f"Bearer {token}"}

        # Step 1: Create media container.
        params: dict = {
            "media_type": "IMAGE" if post.image_url else "TEXT",
            "text": post.body,
        }
        if post.image_url:
            params["image_url"] = post.image_url

        create_resp = requests.post(
            f"{self.BASE}/{user_id}/threads",
            headers=headers, data=params, timeout=20,
        )
        create_resp.raise_for_status()
        creation_id = create_resp.json().get("id")
        if not creation_id:
            raise RuntimeError(
                f"Threads create returned no id: {create_resp.text[:200]}")

        # Step 2: Publish the container.
        publish_resp = requests.post(
            f"{self.BASE}/{user_id}/threads_publish",
            headers=headers,
            data={"creation_id": creation_id},
            timeout=20,
        )
        publish_resp.raise_for_status()
        post_id = publish_resp.json().get("id")
        if not post_id:
            raise RuntimeError(
                f"Threads publish returned no id: {publish_resp.text[:200]}")

        # The canonical permalink isn't directly available from the publish
        # response on every API version, but the standard format is stable:
        return f"https://www.threads.net/@{user_id}/post/{post_id}"
