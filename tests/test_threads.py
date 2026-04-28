"""Tests for thread auto-splitting."""
from __future__ import annotations

from marketing_agent import build_thread_posts, split_into_thread, Platform


def test_short_body_returns_single_chunk():
    chunks = split_into_thread("hello world")
    assert chunks == ["hello world"]


def test_long_body_splits_on_paragraphs():
    body = "para one is short.\n\n" + ("para two " * 50)
    chunks = split_into_thread(body, budget=200, number_tweets=False)
    assert len(chunks) >= 2


def test_thread_numbers_when_more_than_two():
    body = "\n\n".join(["paragraph " + str(i) * 30 for i in range(5)])
    chunks = split_into_thread(body, budget=100, number_tweets=True)
    if len(chunks) > 2:
        # First chunk should have numbering
        assert any("(1/" in c for c in chunks)


def test_no_chunk_exceeds_budget():
    long = "word " * 500
    chunks = split_into_thread(long, budget=140, number_tweets=False)
    for c in chunks:
        assert len(c) <= 140


def test_build_thread_posts_returns_post_objects():
    body = "p1\n\n" + ("p2 " * 100) + "\n\np3"
    posts = build_thread_posts(body, append_url="https://example.com")
    assert all(p.platform == Platform.X for p in posts)
    # First post should have the URL appended (if it fits)
    assert posts[0].body.endswith("https://example.com") or "(1/" in posts[0].body


def test_url_only_appended_to_first():
    body = "para one\n\n" + "p two " * 80
    posts = build_thread_posts(body, append_url="https://x.com")
    assert "https://x.com" in posts[0].body
    for p in posts[1:]:
        assert "https://x.com" not in p.body
