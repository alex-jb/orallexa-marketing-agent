"""Tests for image upload paths on X / Bluesky / Mastodon adapters.

Strategy: mock urllib.request, requests.post, and tweepy. Verify each
adapter:
  1. Downloads the remote URL
  2. Calls the right upload endpoint with the right body shape
  3. Includes the media reference in the post call
  4. Falls back to text-only on any upload failure (no crash)
"""
from __future__ import annotations
from unittest.mock import MagicMock, patch

import pytest

from marketing_agent.types import Platform, Post


def _post_with_image(platform: Platform, body: str = "test post") -> Post:
    return Post(platform=platform, body=body,
                  image_url="https://image.pollinations.ai/prompt/test").with_count()


# ───────────────── X adapter ─────────────────


def test_x_post_calls_create_tweet_with_media_ids(monkeypatch):
    """X adapter downloads → media_upload → create_tweet(media_ids=[...])."""
    for k in ("X_API_KEY", "X_API_KEY_SECRET",
                "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        monkeypatch.setenv(k, "test-value")

    fake_response = MagicMock()
    fake_response.read.return_value = b"\xff\xd8\xff\xe0fake jpeg"
    fake_urlopen = MagicMock()
    fake_urlopen.return_value.__enter__.return_value = fake_response

    fake_media = MagicMock(media_id_string="999111")
    fake_api = MagicMock()
    fake_api.media_upload.return_value = fake_media

    fake_tweet_resp = MagicMock(data={"id": "1234567890"})
    fake_client = MagicMock()
    fake_client.create_tweet.return_value = fake_tweet_resp

    fake_oauth = MagicMock()

    with patch("urllib.request.urlopen", fake_urlopen), \
         patch("tweepy.Client", return_value=fake_client), \
         patch("tweepy.API", return_value=fake_api), \
         patch("tweepy.OAuth1UserHandler", fake_oauth):
        from marketing_agent.platforms.x import XAdapter
        url = XAdapter().post(_post_with_image(Platform.X))

    assert url == "https://x.com/i/web/status/1234567890"
    # create_tweet must have been called with media_ids set
    call_kwargs = fake_client.create_tweet.call_args.kwargs
    assert call_kwargs["text"] == "test post"
    assert call_kwargs["media_ids"] == ["999111"]
    # media_upload must have been called once
    assert fake_api.media_upload.call_count == 1


def test_x_post_falls_back_to_text_when_image_upload_fails(monkeypatch):
    """If urlopen raises, post still goes through, just text-only."""
    for k in ("X_API_KEY", "X_API_KEY_SECRET",
                "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        monkeypatch.setenv(k, "test-value")

    fake_tweet_resp = MagicMock(data={"id": "1234567890"})
    fake_client = MagicMock()
    fake_client.create_tweet.return_value = fake_tweet_resp

    with patch("urllib.request.urlopen", side_effect=ConnectionError("dns fail")), \
         patch("tweepy.Client", return_value=fake_client):
        from marketing_agent.platforms.x import XAdapter
        url = XAdapter().post(_post_with_image(Platform.X))

    assert url == "https://x.com/i/web/status/1234567890"
    # create_tweet called WITHOUT media_ids (text-only fallback)
    call_kwargs = fake_client.create_tweet.call_args.kwargs
    assert "media_ids" not in call_kwargs
    assert call_kwargs["text"] == "test post"


def test_x_post_text_only_when_no_image(monkeypatch):
    for k in ("X_API_KEY", "X_API_KEY_SECRET",
                "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        monkeypatch.setenv(k, "test-value")
    fake_tweet_resp = MagicMock(data={"id": "1"})
    fake_client = MagicMock()
    fake_client.create_tweet.return_value = fake_tweet_resp
    with patch("tweepy.Client", return_value=fake_client):
        from marketing_agent.platforms.x import XAdapter
        XAdapter().post(Post(platform=Platform.X, body="no image"))
    # No media_upload, no media_ids
    call_kwargs = fake_client.create_tweet.call_args.kwargs
    assert "media_ids" not in call_kwargs


# ───────────────── Bluesky adapter ─────────────────


def test_bluesky_post_uploads_blob_and_attaches_embed(monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "alex.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "appp-asss-word-here")

    fake_session = MagicMock()
    fake_session.json.return_value = {"accessJwt": "jwt-token", "did": "did:plc:xyz"}
    fake_session.raise_for_status.return_value = None

    fake_blob_response = MagicMock()
    fake_blob_response.json.return_value = {"blob": {"$type": "blob", "ref": {"$link": "abc"}}}
    fake_blob_response.raise_for_status.return_value = None

    fake_post_response = MagicMock()
    fake_post_response.json.return_value = {
        "uri": "at://did:plc:xyz/app.bsky.feed.post/3kabcdef",
    }
    fake_post_response.raise_for_status.return_value = None

    # Sequence: createSession → uploadBlob → createRecord
    fake_post = MagicMock(side_effect=[fake_session, fake_blob_response, fake_post_response])

    fake_url_response = MagicMock()
    fake_url_response.read.return_value = b"\xff\xd8\xff\xe0fake jpeg"
    fake_urlopen = MagicMock()
    fake_urlopen.return_value.__enter__.return_value = fake_url_response

    with patch("requests.post", fake_post), \
         patch("urllib.request.urlopen", fake_urlopen):
        from marketing_agent.platforms.bluesky import BlueskyAdapter
        url = BlueskyAdapter().post(_post_with_image(Platform.BLUESKY))

    assert url.startswith("https://bsky.app/profile/alex.bsky.social/post/")
    assert fake_post.call_count == 3  # session, blob, record
    # Inspect the createRecord call — record.embed.images must reference the blob
    record_call = fake_post.call_args_list[2]
    record = record_call.kwargs["json"]["record"]
    assert "embed" in record
    assert record["embed"]["$type"] == "app.bsky.embed.images"
    assert record["embed"]["images"][0]["image"]["ref"]["$link"] == "abc"


def test_bluesky_post_skips_blob_when_too_large(monkeypatch):
    """Blobs > 1MB are skipped (Bluesky cap); post goes text-only."""
    monkeypatch.setenv("BLUESKY_HANDLE", "alex.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "p")

    fake_session = MagicMock()
    fake_session.json.return_value = {"accessJwt": "jwt", "did": "did:x"}
    fake_session.raise_for_status.return_value = None

    fake_post_response = MagicMock()
    fake_post_response.json.return_value = {"uri": "at://x/y/3kbig"}
    fake_post_response.raise_for_status.return_value = None

    fake_post = MagicMock(side_effect=[fake_session, fake_post_response])

    huge = b"X" * 1_500_000  # 1.5MB > 1MB cap
    fake_url_response = MagicMock()
    fake_url_response.read.return_value = huge
    fake_urlopen = MagicMock()
    fake_urlopen.return_value.__enter__.return_value = fake_url_response

    with patch("requests.post", fake_post), \
         patch("urllib.request.urlopen", fake_urlopen):
        from marketing_agent.platforms.bluesky import BlueskyAdapter
        BlueskyAdapter().post(_post_with_image(Platform.BLUESKY))

    # Only 2 calls: session + createRecord. Blob upload was skipped.
    assert fake_post.call_count == 2
    record = fake_post.call_args_list[1].kwargs["json"]["record"]
    assert "embed" not in record


# ───────────────── Mastodon adapter ─────────────────


def test_mastodon_post_uploads_media_and_attaches_id(monkeypatch):
    monkeypatch.setenv("MASTODON_INSTANCE", "mastodon.social")
    monkeypatch.setenv("MASTODON_ACCESS_TOKEN", "tok")

    fake_media_response = MagicMock()
    fake_media_response.json.return_value = {"id": "media-12345"}
    fake_media_response.raise_for_status.return_value = None

    fake_status_response = MagicMock()
    fake_status_response.json.return_value = {
        "id": "post-99", "url": "https://mastodon.social/@alex/post-99",
    }
    fake_status_response.raise_for_status.return_value = None

    fake_post = MagicMock(side_effect=[fake_media_response, fake_status_response])

    fake_url_response = MagicMock()
    fake_url_response.read.return_value = b"\xff\xd8\xff\xe0fake jpeg"
    fake_urlopen = MagicMock()
    fake_urlopen.return_value.__enter__.return_value = fake_url_response

    with patch("requests.post", fake_post), \
         patch("urllib.request.urlopen", fake_urlopen):
        from marketing_agent.platforms.mastodon import MastodonAdapter
        url = MastodonAdapter().post(_post_with_image(Platform.MASTODON))

    assert url == "https://mastodon.social/@alex/post-99"
    assert fake_post.call_count == 2
    # The status creation call must include the media_id
    status_call = fake_post.call_args_list[1]
    assert status_call.kwargs["data"]["media_ids[]"] == ["media-12345"]
    assert status_call.kwargs["data"]["status"] == "test post"
