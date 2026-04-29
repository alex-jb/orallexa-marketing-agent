"""Bluesky adapter — uses AT Protocol via direct HTTPS calls.

Bluesky is the fastest-growing X alternative in 2026. We use the
AT Protocol's `com.atproto.server.createSession` for auth + `app.bsky.
feed.post` for posting. No SDK dependency required — just `requests`.

Auth: app password (NOT your account password). Get one at
https://bsky.app/settings/app-passwords.
"""
from __future__ import annotations
import os
from datetime import datetime, timezone

from marketing_agent.retry import retry_on_transient
from marketing_agent.types import Platform, Post
from marketing_agent.platforms.base import NotConfigured


class BlueskyAdapter:
    platform = Platform.BLUESKY

    REQUIRED = ("BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD")
    BASE = "https://bsky.social/xrpc"

    def is_configured(self) -> bool:
        return all(os.getenv(k) for k in self.REQUIRED)

    def dry_run_preview(self, post: Post) -> str:
        body = post.body
        return (
            f"--- Bluesky preview · {len(body)} chars ---\n"
            f"{body}\n"
            f"--- end ---"
        )

    @retry_on_transient(attempts=3, base_delay=2.0)
    def post(self, post: Post) -> str:
        if not self.is_configured():
            raise NotConfigured(
                "Bluesky adapter missing env vars: "
                + ", ".join(k for k in self.REQUIRED if not os.getenv(k))
            )
        if len(post.body) > 300:
            raise ValueError(f"Bluesky post too long: {len(post.body)} > 300")

        import requests  # lazy import

        # 1. Get a session token
        sess = requests.post(
            f"{self.BASE}/com.atproto.server.createSession",
            json={
                "identifier": os.getenv("BLUESKY_HANDLE"),
                "password": os.getenv("BLUESKY_APP_PASSWORD"),
            },
            timeout=15,
        )
        sess.raise_for_status()
        access = sess.json()["accessJwt"]
        did = sess.json()["did"]

        # 2. Optional image — upload as a blob, then reference in record.embed
        embed = None
        if post.image_url:
            try:
                blob = self._upload_blob(post.image_url, access)
                if blob is not None:
                    embed = {
                        "$type": "app.bsky.embed.images",
                        "images": [{"alt": "", "image": blob}],
                    }
            except Exception as e:
                from marketing_agent.logging import get_logger
                get_logger(__name__).warning(
                    "Bluesky blob upload failed, posting text-only: %s", e,
                    extra={"image_url": post.image_url})

        record: dict = {
            "$type": "app.bsky.feed.post",
            "text": post.body,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        if embed is not None:
            record["embed"] = embed

        # 3. Create the post
        resp = requests.post(
            f"{self.BASE}/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {access}"},
            json={
                "repo": did,
                "collection": "app.bsky.feed.post",
                "record": record,
            },
            timeout=15,
        )
        resp.raise_for_status()
        rkey = resp.json()["uri"].split("/")[-1]
        handle = os.getenv("BLUESKY_HANDLE")
        return f"https://bsky.app/profile/{handle}/post/{rkey}"

    def _upload_blob(self, url: str, access_jwt: str) -> dict | None:
        """Download a remote image and POST it to com.atproto.repo.uploadBlob.

        Returns the blob descriptor dict suitable for record.embed.images, or
        None on failure (caller falls back to text-only).
        """
        import urllib.request
        import requests
        with urllib.request.urlopen(url, timeout=15) as r:
            data = r.read()
        # Bluesky caps blobs at 1MB. Skip if larger.
        if len(data) > 1_000_000:
            return None
        upload = requests.post(
            f"{self.BASE}/com.atproto.repo.uploadBlob",
            headers={
                "Authorization": f"Bearer {access_jwt}",
                "Content-Type": "image/jpeg",
            },
            data=data,
            timeout=20,
        )
        upload.raise_for_status()
        return upload.json().get("blob")
