"""Tests for the Bluesky firehose listener.

Strategy: mock atproto entirely (it's an optional dep). Verify graceful
degradation paths + the record-classification helpers without spinning
up a real WebSocket.
"""
from __future__ import annotations
import sys
from unittest.mock import MagicMock, patch


from marketing_agent.listeners.bluesky_firehose import (
    _classify_record, _is_atproto_available, listen, resolve_handle_to_did,
)


# ──────────────── _classify_record ────────────────


def test_classify_record_likes_to_like():
    assert _classify_record("app.bsky.feed.like") == "like"


def test_classify_record_repost():
    assert _classify_record("app.bsky.feed.repost") == "repost"


def test_classify_record_post_to_reply():
    # Posts (which include replies) classified as "reply" for our metrics
    assert _classify_record("app.bsky.feed.post") == "reply"


def test_classify_record_unknown_returns_none():
    assert _classify_record("app.bsky.actor.profile") is None
    assert _classify_record("nonsense") is None


# ──────────────── resolve_handle_to_did ────────────────


def test_resolve_handle_returns_did_on_success(monkeypatch):
    fake_response = MagicMock()
    fake_response.read.return_value = b'{"did": "did:plc:xyz123"}'
    fake_urlopen = MagicMock()
    fake_urlopen.return_value.__enter__.return_value = fake_response

    with patch("urllib.request.urlopen", fake_urlopen):
        did = resolve_handle_to_did("alex.bsky.social")
    assert did == "did:plc:xyz123"


def test_resolve_handle_returns_none_on_network_error():
    with patch("urllib.request.urlopen", side_effect=ConnectionError("dns")):
        did = resolve_handle_to_did("alex.bsky.social")
    assert did is None


# ──────────────── listen() graceful degradation ────────────────


def test_listen_returns_2_when_atproto_missing(monkeypatch, capsys):
    """Without atproto, listen() prints a helpful error and exits 2."""
    monkeypatch.setitem(sys.modules, "atproto", None)
    rc = listen(target_did="did:plc:xyz", once=True)
    assert rc == 2
    err = capsys.readouterr().err
    assert "atproto" in err
    assert "pip install" in err


def test_is_atproto_available_returns_bool():
    """Should never raise; either True or False based on installed deps."""
    assert _is_atproto_available() in (True, False)
