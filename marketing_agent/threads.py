"""Thread builder — splits long content into a Twitter/X thread.

Strategy: smart split that prefers paragraph breaks → sentence breaks →
word breaks. Each tweet ≤ 270 chars (10-char buffer for trailing
counters like "(1/5)"). First tweet may have a hook; trailing tweets
include their position when the thread has > 2 entries.
"""
from __future__ import annotations
import re

from marketing_agent.types import Platform, Post

# X tweet hard max is 280; leave 10 chars for "(N/M)" appendix.
TWEET_BUDGET = 270


def split_into_thread(body: str, *, budget: int = TWEET_BUDGET,
                       number_tweets: bool = True) -> list[str]:
    """Split a long string into a sequence of tweet-length chunks.

    Algorithm:
      1. If body fits in `budget`, return as single-element list.
      2. Else split on paragraph breaks (\\n\\n) first.
      3. Pieces still too long get split on sentence breaks.
      4. Sentences too long get word-split as last resort.
      5. Optional: append "(i/N)" suffix when thread has > 2 tweets.
    """
    body = body.strip()
    if len(body) <= budget:
        return [body]

    # Stage 1: paragraph chunks
    chunks: list[str] = []
    for para in re.split(r"\n\n+", body):
        para = para.strip()
        if not para:
            continue
        if len(para) <= budget:
            chunks.append(para)
        else:
            chunks.extend(_split_long_paragraph(para, budget))

    # Stage 2: pack consecutive small chunks into the same tweet if room
    packed: list[str] = []
    for c in chunks:
        if packed and len(packed[-1]) + 2 + len(c) <= budget:
            packed[-1] = packed[-1] + "\n\n" + c
        else:
            packed.append(c)

    # Stage 3: optional numbering
    if number_tweets and len(packed) > 2:
        n = len(packed)
        packed = [
            f"{t}\n\n({i+1}/{n})" if len(t) + len(f"\n\n({i+1}/{n})") <= 280 else t
            for i, t in enumerate(packed)
        ]

    return packed


def _split_long_paragraph(para: str, budget: int) -> list[str]:
    """Split a paragraph that exceeds budget on sentence boundaries."""
    sentences = re.split(r"(?<=[.!?])\s+", para)
    out: list[str] = []
    cur = ""
    for s in sentences:
        if not s:
            continue
        if len(s) > budget:
            # Sentence itself is too long; word-split
            if cur:
                out.append(cur.strip())
                cur = ""
            out.extend(_word_split(s, budget))
        elif len(cur) + 1 + len(s) <= budget:
            cur = (cur + " " + s).strip() if cur else s
        else:
            out.append(cur.strip())
            cur = s
    if cur:
        out.append(cur.strip())
    return out


def _word_split(text: str, budget: int) -> list[str]:
    """Last-resort word-level chunking."""
    words = text.split()
    out: list[str] = []
    cur = ""
    for w in words:
        if len(cur) + 1 + len(w) <= budget:
            cur = (cur + " " + w).strip() if cur else w
        else:
            out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    return out


def build_thread_posts(body: str, *, append_url: str | None = None,
                        number_tweets: bool = True) -> list[Post]:
    """Split body into Posts. Optionally append a URL on the FIRST tweet.

    Returning Post objects (not raw strings) so the platform adapter can
    chain them via in_reply_to_tweet_id.
    """
    chunks = split_into_thread(body, number_tweets=number_tweets)
    if append_url and chunks:
        first = chunks[0]
        addition = f"\n\n{append_url}"
        if len(first) + len(addition) <= TWEET_BUDGET:
            chunks[0] = first + addition
    return [Post(platform=Platform.X, body=c).with_count() for c in chunks]
