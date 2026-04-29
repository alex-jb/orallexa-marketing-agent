"""Reply Suggester — monitors a Twitter timeline, generates AI reply drafts.

Phase 2 core feature. The growth bottleneck for OSS founders is REPLY
volume to other people in their niche, not original posting. This module:

  1. Pulls recent tweets from a target list (your home timeline OR a
     specific list of accounts you want to engage with)
  2. Filters out tweets that don't match keywords (e.g. "agent", "LLM")
  3. Generates a draft reply via Claude (or a template fallback)
  4. Drops drafts into the approval queue for HITL review

You then review markdown files in ~/.marketing_agent/queue/pending/
and either approve them (move to approved/) or reject (move to rejected/).
The CLI `post` command publishes approved replies.

The script never auto-replies without human approval — that's the
distinction between "marketing tool" and "spam bot" per X's ToS.
"""
from __future__ import annotations
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from marketing_agent.queue import ApprovalQueue
from marketing_agent.types import Platform, Post


@dataclass
class Tweet:
    id: str
    author_id: str
    author_handle: Optional[str]
    text: str
    created_at: datetime
    public_metrics: dict


def fetch_recent_tweets_from_handles(handles: list[str], hours: int = 24,
                                       max_per_handle: int = 5) -> list[Tweet]:
    """Pull recent tweets from a list of accounts you follow."""
    import tweepy
    if not all(os.getenv(k) for k in
                ["X_API_KEY", "X_API_KEY_SECRET",
                 "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]):
        return []
    client = tweepy.Client(
        consumer_key=os.getenv("X_API_KEY"),
        consumer_secret=os.getenv("X_API_KEY_SECRET"),
        access_token=os.getenv("X_ACCESS_TOKEN"),
        access_token_secret=os.getenv("X_ACCESS_TOKEN_SECRET"),
    )
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    out: list[Tweet] = []
    for handle in handles:
        try:
            user = client.get_user(username=handle.lstrip("@"))
            if not user.data:
                continue
            tweets = client.get_users_tweets(
                user.data.id,
                max_results=max(5, min(max_per_handle, 100)),
                tweet_fields=["created_at", "public_metrics"],
                start_time=since,
            )
            for t in (tweets.data or []):
                out.append(Tweet(
                    id=str(t.id), author_id=str(user.data.id),
                    author_handle=handle.lstrip("@"),
                    text=t.text, created_at=t.created_at or since,
                    public_metrics=t.public_metrics or {},
                ))
        except Exception:
            continue  # best-effort, ignore per-handle failures
    return out


def filter_relevant(tweets: list[Tweet], *,
                     keywords: Optional[list[str]] = None,
                     min_engagement: int = 0) -> list[Tweet]:
    """Filter tweets that match any of the keywords + meet engagement floor."""
    out = []
    kw = [k.lower() for k in (keywords or [])]
    for t in tweets:
        if min_engagement:
            score = sum(t.public_metrics.values())
            if score < min_engagement:
                continue
        if kw and not any(k in t.text.lower() for k in kw):
            continue
        out.append(t)
    return out


_TEMPLATE_REPLY_OPENERS = (
    "Curious — ", "On the {topic} angle: ", "I've been wrestling with this. ",
    "Pairs with what I've been seeing — ", "+1 to this. ",
)


def template_reply(tweet: Tweet) -> str:
    """Deterministic template reply — used when no Claude key set.

    These are intentionally bland — meant to be overwritten by the human
    reviewer in the approval queue. The template's job is to anchor the
    reply structure, not to be the final text.
    """
    opener = _TEMPLATE_REPLY_OPENERS[hash(tweet.id) % len(_TEMPLATE_REPLY_OPENERS)]
    body_excerpt = tweet.text[:80]
    return (
        f"{opener}{body_excerpt[:60]}... — what's your take on the next step? "
        f"(draft — review and edit before approving)"
    )


def llm_reply(tweet: Tweet, *, your_voice: str = "") -> str:
    """Use Claude to draft a reply via solo_founder_os.AnthropicClient (so
    token usage flows into the cross-agent cost-audit report). Falls back
    to template_reply on missing key or any failure."""
    try:
        from solo_founder_os.anthropic_client import (
            AnthropicClient, DEFAULT_SONNET_MODEL,
        )
        from marketing_agent.cost import USAGE_LOG_PATH
        client = AnthropicClient(usage_log_path=USAGE_LOG_PATH)
        if not client.configured:
            return template_reply(tweet)

        voice = your_voice or (
            "I'm Alex Ji — Navy veteran, MS CS at Yeshiva, building Orallexa "
            "(multi-agent AI trading system) and Orallexa Marketing Agent "
            "(this tool that's drafting this reply). Voice: technical, honest, "
            "no hype. I disagree when I disagree."
        )
        prompt = f"""You are drafting a reply to a tweet on behalf of:

{voice}

The original tweet (author: @{tweet.author_handle}):
{tweet.text}

Write a single-tweet reply (≤270 chars). Rules:
- React to a SPECIFIC point in the tweet, not a generic compliment
- Add a thought, a question, a counter-example, or a useful link
- Don't open with 'Great take!' or hype
- Don't @ them — they're already in the reply thread
- Don't add hashtags
- 1 emoji max
- The HUMAN will review and edit before posting — keep it as a draft, not final

Output ONLY the reply text, no preamble, no quotes."""
        resp, err = client.messages_create(
            model=DEFAULT_SONNET_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        if err is not None or resp is None:
            return template_reply(tweet)
        text = AnthropicClient.extract_text(resp).strip()
        return text.strip('"').strip("'").strip()
    except Exception:
        return template_reply(tweet)


def suggest_replies_to_queue(handles: list[str], *,
                                keywords: Optional[list[str]] = None,
                                hours: int = 24,
                                min_engagement: int = 5,
                                project_name: str = "engagement",
                                use_llm: bool = True) -> list[str]:
    """End-to-end: fetch → filter → draft → write to queue.

    Returns list of paths (as strings) of pending queue files.
    """
    tweets = fetch_recent_tweets_from_handles(handles, hours=hours)
    relevant = filter_relevant(tweets, keywords=keywords,
                                min_engagement=min_engagement)

    queue = ApprovalQueue()
    paths: list[str] = []
    for t in relevant:
        body = llm_reply(t) if use_llm else template_reply(t)
        # Tweet replies need to know the parent tweet id; we store it in
        # `target` for the publisher to consume.
        post = Post(
            platform=Platform.X,
            body=body,
            target=t.id,  # parent tweet id for in_reply_to
        ).with_count()
        path = queue.submit(post, project_name=project_name,
                              generated_by=("llm" if use_llm else "template"))
        # Attach context to file (overwrite the file with extra metadata block)
        text = path.read_text()
        ctx = (f"\n\n<!-- replying to @{t.author_handle} tweet {t.id}\n"
               f"original:\n{t.text[:300]}\n-->\n")
        path.write_text(text + ctx)
        paths.append(str(path))
    return paths
