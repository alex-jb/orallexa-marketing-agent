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
