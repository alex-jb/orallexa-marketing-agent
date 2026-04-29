"""Mastodon adapter — direct HTTPS, no SDK.

Mastodon servers are independent. Set MASTODON_INSTANCE to the server
you have an account on (e.g. mastodon.social or fosstodon.org).
Get an access token from Settings → Development → New application.
"""
from __future__ import annotations
import os

from marketing_agent.retry import retry_on_transient
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

    @retry_on_transient(attempts=3, base_delay=2.0)
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

        token = os.getenv("MASTODON_ACCESS_TOKEN")
        headers = {"Authorization": f"Bearer {token}"}

        # Optional image — upload via media/v2 endpoint, attach by id
        media_ids: list[str] = []
        if post.image_url:
            try:
                media_id = self._upload_media(post.image_url, instance, headers)
                if media_id:
                    media_ids.append(media_id)
            except Exception as e:
                from marketing_agent.logging import get_logger
                get_logger(__name__).warning(
                    "Mastodon media upload failed, posting text-only: %s", e,
                    extra={"image_url": post.image_url})

        data: dict = {"status": post.body}
        if media_ids:
            # Mastodon expects media_ids as a list — requests handles repeated keys
            data["media_ids[]"] = media_ids

        resp = requests.post(
            f"{instance}/api/v1/statuses",
            headers=headers, data=data, timeout=15,
        )
        resp.raise_for_status()
        body = resp.json()
        return body.get("url", f"{instance}/web/statuses/{body['id']}")

    def _upload_media(self, url: str, instance: str, headers: dict) -> str | None:
        """Download a remote image and POST it to /api/v2/media. Returns media id."""
        import urllib.request
        import requests
        with urllib.request.urlopen(url, timeout=15) as r:
            data = r.read()
        # Mastodon image limits vary by instance; 8MB is a safe ceiling
        if len(data) > 8_000_000:
            return None
        files = {"file": ("image.jpg", data, "image/jpeg")}
        resp = requests.post(
            f"{instance}/api/v2/media",
            headers=headers, files=files, timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("id")
