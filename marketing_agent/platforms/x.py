"""X (Twitter) adapter — uses tweepy + 4-key OAuth 1.0a User Context."""
from __future__ import annotations
import os

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
        resp = client.create_tweet(text=body)
        tweet_id = resp.data["id"]
        return f"https://x.com/i/web/status/{tweet_id}"
