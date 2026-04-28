"""Mastodon adapter — direct HTTPS, no SDK.

Mastodon servers are independent. Set MASTODON_INSTANCE to the server
you have an account on (e.g. mastodon.social or fosstodon.org).
Get an access token from Settings → Development → New application.
"""
from __future__ import annotations
import os

from marketing_agent.types import Platform, Post
from marketing_agent.platforms.base import NotConfigured


class MastodonAdapter:
    platform = Platform.MASTODON

    REQUIRED = ("MASTODON_INSTANCE", "MASTODON_ACCESS_TOKEN")

    def is_configured(self) -> bool:
        return all(os.getenv(k) for k in self.REQUIRED)

    def dry_run_preview(self, post: Post) -> str:
        body = post.body
        return (
            f"--- Mastodon preview · {len(body)} chars ---\n"
            f"{body}\n"
            f"--- end ---"
        )

    def post(self, post: Post) -> str:
        if not self.is_configured():
            raise NotConfigured(
                "Mastodon adapter missing env vars: "
                + ", ".join(k for k in self.REQUIRED if not os.getenv(k))
            )
        if len(post.body) > 500:
            raise ValueError(f"Mastodon toot too long: {len(post.body)} > 500")

        import requests  # lazy import

        instance = os.getenv("MASTODON_INSTANCE", "").rstrip("/")
        if not instance.startswith("http"):
            instance = f"https://{instance}"

        resp = requests.post(
            f"{instance}/api/v1/statuses",
            headers={
                "Authorization": f"Bearer {os.getenv('MASTODON_ACCESS_TOKEN')}",
            },
            data={"status": post.body},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("url", f"{instance}/web/statuses/{data['id']}")
