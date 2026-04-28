"""知乎 adapter — content formatter only (semi-auto via browser).

知乎 has no public posting API for individuals. Real posting requires
browser automation (Playwright + your logged-in cookie). v0.2 ships
content formatting only — the human copy-pastes the output into 知乎's
new-answer page.

Phase 2 plan: ship a Playwright-based publish() that uses a stored
cookies.json session to navigate to a question + click "写回答" + paste
the body + submit. That's deferred until v0.3.

Output style follows 知乎 norms:
  - Long-form (2000-5000 字 ideal)
  - Structured with H2/H3 headings
  - Code blocks welcomed
  - First paragraph must hook the reader
"""
from __future__ import annotations

from marketing_agent.types import Platform, Post
from marketing_agent.platforms.base import NotConfigured


class ZhihuAdapter:
    platform = Platform.ZHIHU

    def is_configured(self) -> bool:
        return False  # Phase 3

    def dry_run_preview(self, post: Post) -> str:
        return (
            f"--- 知乎 preview · {len(post.body)} chars ---\n"
            f"标题: {post.title or '(无标题)'}\n\n"
            f"{post.body}\n"
            f"--- end ---\n"
            f"(粘贴到 zhihu.com → 写回答 / 写文章 · 浏览器自动化 Phase 3)"
        )

    def post(self, post: Post) -> str:
        raise NotConfigured(
            "知乎 auto-posting requires Playwright + cookie session — Phase 3. "
            "Use dry_run_preview() to format the body for manual posting."
        )
