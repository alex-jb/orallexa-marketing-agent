"""X (Twitter) adapter — uses tweepy + 4-key OAuth 1.0a User Context."""
from __future__ import annotations
import os

from marketing_agent.retry import retry_on_transient
from marketing_agent.types import Platform, Post
from marketing_agent.platforms.base import NotConfigured


class XAdapter:
    platform = Platform.X

    REQUIRED = (
        "X_API_KEY", "X_API_KEY_SECRET",
        "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET",
    )

    def is_configured(self) -> bool:
        return all(os.getenv(k) for k in self.REQUIRED)

    def dry_run_preview(self, post: Post) -> str:
        body = post.body
        return (
            f"--- X (Twitter) preview · {len(body)} chars ---\n"
            f"{body}\n"
            f"--- end ---"
        )

    @retry_on_transient(attempts=3, base_delay=2.0)
    def post(self, post: Post) -> str:
        if not self.is_configured():
            raise NotConfigured(
                "X adapter missing env vars: "
                + ", ".join(k for k in self.REQUIRED if not os.getenv(k))
            )
        # Defensive — tweets > 280 chars get rejected
        body = post.body
        if len(body) > 280:
            raise ValueError(f"X tweet too long: {len(body)} > 280")

        import tweepy  # lazy import keeps test runs fast
        client = tweepy.Client(
            consumer_key=os.getenv("X_API_KEY"),
            consumer_secret=os.getenv("X_API_KEY_SECRET"),
            access_token=os.getenv("X_ACCESS_TOKEN"),
            access_token_secret=os.getenv("X_ACCESS_TOKEN_SECRET"),
        )

        # Optional image attachment — download remote URL, upload to X, attach.
        # X's create_tweet accepts media_ids only via the v1.1 media/upload.json
        # endpoint, so we use tweepy.API for the upload and v2 Client for the
        # tweet itself. Failure to upload degrades gracefully to text-only.
        media_ids: list[str] = []
        if post.image_url:
            try:
                media_id = self._upload_remote_image(post.image_url)
                if media_id:
                    media_ids.append(media_id)
            except Exception as e:
                # Don't block the tweet on image-upload failure — log and skip.
                from marketing_agent.logging import get_logger
                get_logger(__name__).warning(
                    "X image upload failed, posting text-only: %s", e,
                    extra={"image_url": post.image_url})

        kwargs: dict = {"text": body}
        if media_ids:
            kwargs["media_ids"] = media_ids
        resp = client.create_tweet(**kwargs)
        tweet_id = resp.data["id"]
        return f"https://x.com/i/web/status/{tweet_id}"

    def _upload_remote_image(self, url: str) -> str | None:
        """Download `url` to /tmp, upload via tweepy v1.1 API, return media_id.

        Returns None if download/upload fails (caller should proceed text-only).
        """
        import tempfile
        import urllib.request
        import tweepy
        # Download to a temp file (X's upload endpoint accepts a local path)
        with urllib.request.urlopen(url, timeout=15) as r:
            data = r.read()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(data)
            tmp = f.name
        auth = tweepy.OAuth1UserHandler(
            os.getenv("X_API_KEY"), os.getenv("X_API_KEY_SECRET"),
            os.getenv("X_ACCESS_TOKEN"), os.getenv("X_ACCESS_TOKEN_SECRET"),
        )
        api = tweepy.API(auth)
        media = api.media_upload(filename=tmp)
        return str(media.media_id_string) if media else None
