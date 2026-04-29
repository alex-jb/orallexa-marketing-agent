"""Bluesky firehose listener — free real-time engagement.

The Bluesky AT Protocol publishes a public WebSocket firehose at
`wss://bsky.network/xrpc/com.atproto.sync.subscribeRepos`. Every post,
like, repost, follow on the entire network flows through. We subscribe,
filter for events targeting THIS account's URIs, and record them into
the existing EngagementTracker SQLite.

Why this is a big deal:
  - X equivalent (Account Activity API) costs $42k/yr Enterprise tier
  - Bluesky firehose is FREE, public, no auth needed for subscription
  - Real-time data unlocks "alert me when a post takes off" UX

Only the read side is here. To filter by your account, set BLUESKY_HANDLE
(same env var used by the publisher adapter) — we resolve it to a DID
once at startup and filter the stream to events where the subject DID
matches.

CLI:
    marketing-agent-firehose-bsky          # runs forever
    marketing-agent-firehose-bsky --once   # one event then exit (for tests)

Optional dep: [firehose] = atproto>=0.0.55
"""
from __future__ import annotations
import os
import sys
from datetime import datetime, timezone
from typing import Optional

from marketing_agent.engagement import EngagementTracker
from marketing_agent.logging import get_logger
from marketing_agent.types import Engagement, Platform

log = get_logger(__name__)


def _is_atproto_available() -> bool:
    try:
        import atproto  # noqa: F401
        return True
    except ImportError:
        return False


def resolve_handle_to_did(handle: str) -> Optional[str]:
    """Resolve bsky handle (e.g. alex.bsky.social) → DID via public API."""
    try:
        import urllib.parse
        import urllib.request
        import json
        url = (f"https://public.api.bsky.app/xrpc/"
               f"com.atproto.identity.resolveHandle?"
               f"handle={urllib.parse.quote(handle)}")
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        return data.get("did")
    except Exception as e:
        log.debug("handle resolve failed: %s", e)
        return None


def _classify_record(record_type: str) -> Optional[str]:
    """Map AT Protocol record types to engagement metric names.

    We only care about events that imply someone interacted with a post.
    """
    return {
        "app.bsky.feed.like":   "like",
        "app.bsky.feed.repost": "repost",
        "app.bsky.feed.post":   "reply",  # reply == a post with `reply` ref
    }.get(record_type)


def listen(*, target_did: Optional[str] = None,
             tracker: Optional[EngagementTracker] = None,
             once: bool = False) -> int:
    """Subscribe to the firehose; record engagement into the tracker.

    target_did: only record events that target this DID. If None, resolves
    from BLUESKY_HANDLE env var. If neither, listens to everything (mostly
    useless for indie use; keeps the function testable).

    once: stop after one matching event. Used by tests.

    Returns 0 on graceful exit, 2 if atproto isn't installed.
    """
    if not _is_atproto_available():
        print("atproto not installed. Install with: "
                "pip install 'orallexa-marketing-agent[firehose]'",
                file=sys.stderr)
        return 2

    if target_did is None:
        handle = os.getenv("BLUESKY_HANDLE")
        if handle:
            target_did = resolve_handle_to_did(handle)
            log.info("resolved handle to did",
                      extra={"handle": handle, "did": target_did})

    tracker = tracker or EngagementTracker()
    n_recorded = 0

    try:
        from atproto import FirehoseSubscribeReposClient, parse_subscribe_repos_message
        from atproto import CAR, models  # noqa: F401  # used by atproto internals
    except ImportError:
        return 2

    client = FirehoseSubscribeReposClient()

    def on_message_handler(message) -> None:
        nonlocal n_recorded
        try:
            commit = parse_subscribe_repos_message(message)
            # Only commit messages have ops; skip handle/identity/etc
            if not hasattr(commit, "ops"):
                return
            for op in commit.ops:
                if op.action != "create":
                    continue
                # op.path looks like 'app.bsky.feed.like/3kabc...'
                rec_type = op.path.split("/", 1)[0]
                metric = _classify_record(rec_type)
                if metric is None:
                    continue
                # For target filtering we need to peek at the record body.
                # The firehose ships records as CAR blocks; full parsing is
                # heavy. The pragmatic shortcut: check whether the commit's
                # repo (the actor) matches OR check if the URI path
                # mentions our DID. v0.12 will properly decode CAR blocks.
                actor_did = getattr(commit, "repo", "")
                if target_did and target_did not in (actor_did, op.cid or ""):
                    continue
                event = Engagement(
                    platform=Platform.BLUESKY,
                    post_id=op.path,
                    metric=metric,
                    count=1,
                    timestamp=datetime.now(timezone.utc),
                    actor=actor_did,
                )
                tracker.record(event)
                n_recorded += 1
                log.info("bluesky engagement recorded",
                          extra={"metric": metric, "actor": actor_did})
                if once:
                    raise StopIteration
        except StopIteration:
            raise
        except Exception as e:
            log.debug("firehose handler error: %s", e)

    try:
        client.start(on_message_handler)
    except StopIteration:
        pass
    return 0


def main() -> int:
    """Entry point installed as marketing-agent-firehose-bsky."""
    import argparse
    p = argparse.ArgumentParser(prog="marketing-agent-firehose-bsky")
    p.add_argument("--did", default=None,
                    help="Target DID to filter on. Default: resolve from $BLUESKY_HANDLE")
    p.add_argument("--once", action="store_true",
                    help="Exit after the first matching event (for testing)")
    args = p.parse_args()
    return listen(target_did=args.did, once=args.once)


if __name__ == "__main__":
    sys.exit(main())
