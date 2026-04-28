"""Reddit adapter — uses PRAW for posting to a chosen subreddit.

Reddit is anti-spam. Same content cross-posted to multiple subreddits is
the most common ban trigger. This adapter posts to ONE subreddit per call;
the orchestrator can call it multiple times with different content/voices.
"""
from __future__ import annotations
import os

from marketing_agent.types import Platform, Post
from marketing_agent.platforms.base import NotConfigured


class RedditAdapter:
    platform = Platform.REDDIT

    REQUIRED = (
        "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET",
        "REDDIT_USERNAME", "REDDIT_PASSWORD",
        "REDDIT_USER_AGENT",
    )

    def is_configured(self) -> bool:
        return all(os.getenv(k) for k in self.REQUIRED)

    def dry_run_preview(self, post: Post) -> str:
        sub = post.target or "MachineLearning"
        return (
            f"--- Reddit preview · r/{sub} ---\n"
            f"Title: {post.title or '(no title)'}\n\n"
            f"{post.body}\n"
            f"--- end ---"
        )

    def post(self, post: Post) -> str:
        if not self.is_configured():
            raise NotConfigured(
                "Reddit adapter missing env vars: "
                + ", ".join(k for k in self.REQUIRED if not os.getenv(k))
            )
        if not post.title:
            raise ValueError("Reddit posts require a title")
        if not post.target:
            raise ValueError("Reddit posts require a target subreddit (post.target)")

        import praw  # lazy import

        reddit = praw.Reddit(
            client_id=os.getenv("REDDIT_CLIENT_ID"),
            client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
            username=os.getenv("REDDIT_USERNAME"),
            password=os.getenv("REDDIT_PASSWORD"),
            user_agent=os.getenv("REDDIT_USER_AGENT"),
        )
        submission = reddit.subreddit(post.target).submit(
            title=post.title, selftext=post.body
        )
        return f"https://reddit.com{submission.permalink}"
