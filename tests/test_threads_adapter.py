"""Tests for the Threads (Meta) adapter — mocked Graph API."""
from __future__ import annotations
from unittest.mock import MagicMock, patch

import pytest

from marketing_agent.platforms.base import NotConfigured, get_adapter
from marketing_agent.platforms.threads import ThreadsAdapter
from marketing_agent.types import Platform, Post


def _post(body: str = "Threads launch announcement.") -> Post:
    return Post(platform=Platform.THREADS, body=body).with_count()


def _post_with_image() -> Post:
    return Post(
        platform=Platform.THREADS,
        body="Threads with banner image.",
        image_url="https://image.pollinations.ai/prompt/test",
    ).with_count()


def _ok(json_body: dict) -> MagicMock:
    """Build a fake requests Response with the given json + 2xx status."""
    resp = MagicMock()
    resp.json.return_value = json_body
    resp.raise_for_status.return_value = None
    return resp


# ──────────────── basic config / dispatch ────────────────


def test_is_configured_false_without_envs(monkeypatch):
    monkeypatch.delenv("THREADS_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("THREADS_USER_ID", raising=False)
    assert ThreadsAdapter().is_configured() is False


def test_is_configured_true_with_both(monkeypatch):
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("THREADS_USER_ID", "1234567890")
    assert ThreadsAdapter().is_configured() is True


def test_get_adapter_returns_threads(monkeypatch):
    a = get_adapter(Platform.THREADS)
    assert isinstance(a, ThreadsAdapter)


def test_dry_run_preview_includes_body():
    a = ThreadsAdapter()
    preview = a.dry_run_preview(_post("hello"))
    assert "Threads preview" in preview
    assert "hello" in preview


def test_post_raises_not_configured_without_envs(monkeypatch):
    monkeypatch.delenv("THREADS_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("THREADS_USER_ID", raising=False)
    with pytest.raises(NotConfigured):
        ThreadsAdapter().post(_post())


def test_post_raises_value_error_when_too_long(monkeypatch):
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("THREADS_USER_ID", "1234567890")
    with pytest.raises(ValueError):
        ThreadsAdapter().post(_post("x" * 600))


# ──────────────── happy-path publish ────────────────


def test_post_two_step_publish_text_only(monkeypatch):
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("THREADS_USER_ID", "1234567890")

    fake_post = MagicMock(side_effect=[
        _ok({"id": "creation-id-abc"}),       # step 1: create container
        _ok({"id": "post-id-xyz"}),           # step 2: publish
    ])
    with patch("requests.post", fake_post):
        url = ThreadsAdapter().post(_post("Hello Threads"))

    assert url.startswith("https://www.threads.net/@1234567890/post/")
    assert "post-id-xyz" in url
    assert fake_post.call_count == 2

    # Inspect payload of step 1 — must be media_type=TEXT, no image_url
    step1 = fake_post.call_args_list[0]
    assert "/threads" in step1.args[0]
    assert step1.kwargs["data"]["media_type"] == "TEXT"
    assert "image_url" not in step1.kwargs["data"]
    assert step1.kwargs["data"]["text"] == "Hello Threads"

    # Step 2 must reference the creation_id from step 1
    step2 = fake_post.call_args_list[1]
    assert "/threads_publish" in step2.args[0]
    assert step2.kwargs["data"]["creation_id"] == "creation-id-abc"


def test_post_two_step_publish_with_image(monkeypatch):
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("THREADS_USER_ID", "u9")

    fake_post = MagicMock(side_effect=[
        _ok({"id": "c-1"}),
        _ok({"id": "p-2"}),
    ])
    with patch("requests.post", fake_post):
        url = ThreadsAdapter().post(_post_with_image())

    assert "p-2" in url
    step1 = fake_post.call_args_list[0]
    assert step1.kwargs["data"]["media_type"] == "IMAGE"
    assert step1.kwargs["data"]["image_url"].startswith(
        "https://image.pollinations.ai")


def test_post_propagates_no_creation_id_error(monkeypatch):
    """If Meta returns 200 but no `id`, we surface a clear error."""
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("THREADS_USER_ID", "u9")
    bad = MagicMock()
    bad.json.return_value = {"error": "rate limited"}
    bad.raise_for_status.return_value = None
    bad.text = '{"error": "rate limited"}'

    with patch("requests.post", return_value=bad):
        with pytest.raises(RuntimeError, match="no id"):
            ThreadsAdapter().post(_post())


def test_post_propagates_no_publish_id_error(monkeypatch):
    """Step 1 OK with creation_id, step 2 returns 200 without publish id."""
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("THREADS_USER_ID", "u9")
    fake_post = MagicMock(side_effect=[
        _ok({"id": "c-1"}),
        type("R", (), {  # second response: no id, raise_for_status no-op
            "json": lambda self: {"error": "publish failed"},
            "raise_for_status": lambda self: None,
            "text": "publish failed",
        })(),
    ])
    with patch("requests.post", fake_post):
        with pytest.raises(RuntimeError, match="publish returned no id"):
            ThreadsAdapter().post(_post())
