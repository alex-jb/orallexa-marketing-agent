"""知乎 (Zhihu) adapter — **content prep only, manual publish**.

Per Q2 2026 research, 知乎 is the **highest-leverage Chinese platform for
OSS founders** — but only via human posting:

- No public publishing API since 2020 lockdown
- `x-zse-96` request signing + ~5-min IP bans on >1 req/s
- Editorial moderation lighter than 小红书 for long-form technical content
- A real engineering 回答 with code rarely gets pulled
- Long-tail SEO: one good 回答 ranks on Baidu for years
- Multi-account automation gets caught fast

**Conclusion**: one warmed account, manual paste, AI-assisted writing. Long-
form 回答 with concrete code is the format. This adapter formats the body
for that workflow — including a hint about which question to target.

The 80/20 path: target high-traffic 回答 questions in your niche (search
"Show HN" / "如何评价" / "{tech} 推荐" type questions), drop a 1500-3000 字
answer with code blocks, link your repo. One viral 回答 = 6 months of
ambient distribution.
"""
from __future__ import annotations

from marketing_agent.types import Platform, Post
from marketing_agent.platforms.base import NotConfigured


# Question patterns where an OSS-tool 回答 commonly performs well on 知乎.
# Used for documentation; render_zhihu() in templates can suggest one.
QUESTION_PATTERNS = (
    "如何评价 {project}?",
    "{tech} 领域有哪些值得关注的开源工具?",
    "想做 {use_case},有什么推荐的工具?",
    "{competitor} 之外还有什么替代品?",
    "做 {project} 这种项目应该怎么入门?",
)


class ZhihuAdapter:
    """Content-prep adapter — never auto-posts."""

    platform = Platform.ZHIHU

    # Permanently False — see module docstring. We do NOT plan to flip
    # this to a Playwright auto-post flow; the ban-risk vs upside math
    # doesn't pencil for an indie founder.
    def is_configured(self) -> bool:
        return False

    def dry_run_preview(self, post: Post) -> str:
        body = post.body
        title = post.title or "(请加一个回答标题或目标问题)"
        n_chars = len(body)
        target_length = (
            "短答" if n_chars < 800 else
            "中等" if n_chars < 2000 else
            "长答 ✅" if n_chars < 5000 else
            "过长 ⚠ 拆成两篇可能更好"
        )

        return (
            f"━━━━━━━━━━ 知乎 回答 / 文章 · {n_chars} 字 · {target_length} ━━━━━━━━━━\n"
            f"\n"
            f"标题/目标问题: {title}\n"
            f"\n"
            f"{body}\n"
            f"\n"
            f"━━━━━━━━━━ 发布建议 ━━━━━━━━━━\n"
            f"1. **回答而非文章**:回答的 SEO 长尾价值远高于文章\n"
            f"   去搜你领域已有的高赞问题,把这篇 paste 过去\n"
            f"2. 长度: 1500-3000 字最佳。<800 字偏短答,>5000 字考虑拆\n"
            f"3. **首段必须 hook**:第一段直接给结论或反常识的事实\n"
            f"4. 中间放代码块、截图、图表 — 知乎算法偏好结构化\n"
            f"5. 末段加一句轻量 CTA + 项目链接\n"
            f"\n"
            f"━━━━━━━━━━ 高 ROI 问题模式 ━━━━━━━━━━\n"
            + "\n".join(f"  · {q}" for q in QUESTION_PATTERNS)
            + "\n\n"
            "━━━━━━━━━━ ⚠ 发布前检查 ━━━━━━━━━━\n"
            "1. 用真实账号(知乎对新号写 marketing 内容很警惕)\n"
            "2. 节奏:每周 1-2 篇,不要灌水\n"
            "3. 评论区认真回 5+ 条,触发推荐\n"
            "4. 链接放最后,前 80% 是真实信息价值\n"
            "5. 不勾外链审核,知乎对外链审较严\n"
            "\n"
            "知乎 是 OSS 工具在中文圈最高 ROI 的渠道之一 — 一篇好 回答 在百度上能排几年。\n"
            "花 30 分钟人工粘贴 + 优化,远比自动发被 ban 强。\n"
        )

    def post(self, post: Post) -> str:
        raise NotConfigured(
            "知乎 auto-posting is permanently disabled — see Q2 2026 research:\n"
            "  - x-zse-96 request signing + ~5-min IP bans on >1 req/s\n"
            "  - No public publishing API since 2020\n"
            "  - Multi-account automation caught fast\n"
            "  - Single human-warmed account at human pace is the only path\n"
            "Use dry_run_preview() to format the answer body for manual paste\n"
            "at https://www.zhihu.com (target a question, click 写回答)."
        )
