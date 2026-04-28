"""小红书 adapter — content formatter only (semi-auto via browser).

小红书 (RedNote) has no public posting API. Same Phase 3 plan as 知乎:
Playwright + cookies for true automation. v0.2 ships formatter that
respects 小红书's content style:

  - Short body (~500-800 字)
  - 1 strong hook in first 2 lines
  - Numbered/emoji list structure
  - Hashtags at the end (#AI #编程)
  - Image-friendly (we don't render images yet)

Common 小红书 voice for tech content:
  "聊聊我做的 X" / "30 天用 X 学到的 Y" / "为什么我放弃 X 改用 Y"
"""
from __future__ import annotations

from marketing_agent.types import Platform, Post
from marketing_agent.platforms.base import NotConfigured


class XiaohongshuAdapter:
    platform = Platform.XIAOHONGSHU

    def is_configured(self) -> bool:
        return False  # Phase 3

    def dry_run_preview(self, post: Post) -> str:
        return (
            f"--- 小红书 preview · {len(post.body)} chars ---\n"
            f"标题: {post.title or '(无标题)'}\n\n"
            f"{post.body}\n"
            f"--- end ---\n"
            f"(粘贴到 xiaohongshu.com → 发布笔记 · 浏览器自动化 Phase 3)"
        )

    def post(self, post: Post) -> str:
        raise NotConfigured(
            "小红书 auto-posting requires Playwright + cookie session — Phase 3. "
            "Use dry_run_preview() to format the body for manual posting."
        )
