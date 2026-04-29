"""Tests for Zhihu / Xiaohongshu adapter stubs."""
from __future__ import annotations

import pytest

from marketing_agent import Platform, Post
from marketing_agent.platforms import ZhihuAdapter, XiaohongshuAdapter
from marketing_agent.platforms.base import NotConfigured, get_adapter


def test_zhihu_adapter_dry_run_only():
    a = ZhihuAdapter()
    assert a.is_configured() is False
    p = Post(platform=Platform.ZHIHU, body="文章正文",
             title="一个标题").with_count()
    preview = a.dry_run_preview(p)
    assert "知乎" in preview
    assert "文章正文" in preview
    with pytest.raises(NotConfigured):
        a.post(p)


def test_xiaohongshu_adapter_dry_run_only():
    a = XiaohongshuAdapter()
    assert a.is_configured() is False
    p = Post(platform=Platform.XIAOHONGSHU, body="笔记正文").with_count()
    preview = a.dry_run_preview(p)
    assert "小红书" in preview
    with pytest.raises(NotConfigured):
        a.post(p)


def test_get_adapter_handles_chinese_platforms():
    assert isinstance(get_adapter(Platform.ZHIHU), ZhihuAdapter)
    assert isinstance(get_adapter(Platform.XIAOHONGSHU), XiaohongshuAdapter)


# v0.13: adapters now ship rich content-prep guidance, not just stubs.


def test_xiaohongshu_preview_includes_ai_disclosure_warning():
    a = XiaohongshuAdapter()
    p = Post(platform=Platform.XIAOHONGSHU,
             body="测试笔记内容,中等长度,会触发 6 张图建议").with_count()
    preview = a.dry_run_preview(p)
    # Must remind about AI disclosure (Jan 2026 platform rule)
    assert "AI" in preview
    assert "内容类型声明" in preview or "disclosure" in preview.lower()


def test_xiaohongshu_preview_warns_against_matrix_accounts():
    a = XiaohongshuAdapter()
    p = Post(platform=Platform.XIAOHONGSHU, body="x").with_count()
    preview = a.dry_run_preview(p)
    assert "矩阵" in preview or "matrix" in preview.lower()


def test_xiaohongshu_post_error_explains_why_not():
    """The error message should educate the user about WHY auto-post is bad,
    not just say 'not configured'."""
    a = XiaohongshuAdapter()
    p = Post(platform=Platform.XIAOHONGSHU, body="x").with_count()
    try:
        a.post(p)
    except NotConfigured as e:
        msg = str(e)
        assert "TLS" in msg or "fingerprint" in msg.lower() or "ban" in msg.lower()


def test_zhihu_preview_recommends_answer_over_article():
    a = ZhihuAdapter()
    p = Post(platform=Platform.ZHIHU, body="一个回答的正文",
             title="如何评价 X?").with_count()
    preview = a.dry_run_preview(p)
    # Should advise targeting a Question (回答) rather than writing a 文章
    assert "回答" in preview
    # Should suggest length range
    assert "字" in preview
    # Should warn about new-account marketing detection
    assert "节奏" in preview or "新号" in preview


def test_zhihu_preview_classifies_length():
    a = ZhihuAdapter()
    short_post = Post(platform=Platform.ZHIHU, body="x" * 500).with_count()
    long_post = Post(platform=Platform.ZHIHU, body="x" * 2500).with_count()
    assert "短答" in a.dry_run_preview(short_post)
    assert "长答" in a.dry_run_preview(long_post)
