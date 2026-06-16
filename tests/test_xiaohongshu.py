"""Tests for the 小红书 adapter — content-prep + paste-ready workflow.

Verifies: never auto-posts, dry_run_preview shape, clipboard payload structure,
HTML preview rendering, paste_ready end-to-end (no clipboard, no browser).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from marketing_agent.platforms.base import NotConfigured
from marketing_agent.platforms.xiaohongshu import (
    DEFAULT_TAGS,
    XiaohongshuAdapter,
)
from marketing_agent.types import Platform, Post


def _post(title="测试标题", body="正文 1\n正文 2") -> Post:
    return Post(platform=Platform.XIAOHONGSHU, title=title, body=body)


def test_adapter_never_configured():
    """is_configured() must return False permanently. xhs has IP geofence
    + behavioral risk + 养号 requirements that make autonomous posting -EV."""
    assert XiaohongshuAdapter().is_configured() is False


def test_post_raises_notconfigured():
    """Calling .post() must always raise — no env var should re-enable it."""
    with pytest.raises(NotConfigured) as exc:
        XiaohongshuAdapter().post(_post())
    msg = str(exc.value)
    # Must explain WHY auto-post is off, not just refuse
    assert "auto-posting is permanently disabled" in msg
    assert "海外 IP" in msg  # 2026-06-16 geofence finding referenced


def test_dry_run_preview_contains_required_warnings():
    """Pre-publish checklist must mention: AI disclosure, 养号, 海外 IP."""
    out = XiaohongshuAdapter().dry_run_preview(_post(body="x" * 250))
    assert "AI 工具辅助" in out
    assert "养号" in out
    assert "海外 IP" in out
    # Char-count-derived image count: 250 chars → 6 imgs
    assert "6 张图轮播" in out


def test_clipboard_payload_includes_title_body_tags():
    a = XiaohongshuAdapter()
    p = _post(title="hello", body="body line")
    tags = ["#tag1", "#tag2"]
    payload = a.clipboard_payload(p, tags)
    assert "hello" in payload
    assert "body line" in payload
    assert "#tag1 #tag2" in payload


def test_render_html_preview_has_phone_shape_and_payload():
    a = XiaohongshuAdapter()
    p = _post(title="<script>", body="hello & world")
    tags = ["#solofounder"]
    html = a.render_html_preview(p, tags, project_name="MyProj")
    # HTML escaping (don't leak <script>)
    assert "&lt;script&gt;" in html
    assert "<script>" not in html.replace("<script>", "")  # only in escaped form
    # Phone-shape marker present
    assert "phone-inner" in html
    # Tag chip rendered
    assert "#solofounder" in html
    # AI disclosure warning rendered
    assert "AI 工具辅助" in html
    # Payload textarea includes body
    assert "hello &amp; world" in html


def test_suggest_tags_falls_back_to_default_when_no_key(monkeypatch):
    """Without ANTHROPIC_API_KEY, must return DEFAULT_TAGS — never raise."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    tags = XiaohongshuAdapter().suggest_tags(_post())
    assert tags == list(DEFAULT_TAGS)
    assert all(t.startswith("#") for t in tags)


def test_paste_ready_writes_html_to_desktop(monkeypatch, tmp_path):
    """paste_ready() should write an HTML file under ~/Desktop/xhs-posts/<date>/
    even when clipboard + browser are disabled."""
    # Redirect home to tmp so we don't pollute Alex's real Desktop
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    a = XiaohongshuAdapter()
    # Force clipboard no-op
    monkeypatch.setattr(a, "copy_to_clipboard", lambda payload: False)
    result = a.paste_ready(_post(), open_browser=False)

    assert result["clipboard_copied"] is False
    assert result["preview_opened"] is False
    assert result["tags"] == list(DEFAULT_TAGS)
    html_path = Path(result["html_path"])
    assert html_path.exists()
    assert html_path.suffix == ".html"
    content = html_path.read_text(encoding="utf-8")
    assert "phone-inner" in content
    assert "测试标题" in content
