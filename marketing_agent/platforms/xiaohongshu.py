"""小红书 (Xiaohongshu / RED) adapter — **content prep only, NEVER auto-post**.

Per Q2 2026 research (anti-bot reality on 小红书):

- 阿瑞斯 (Ares) risk system uses TLS fingerprinting, device fingerprint,
  behavioral telemetry. Playwright+stealth defeats fingerprint surfaces
  but NOT TLS fingerprints or behavioral models. Detection is behavioral.
- New accounts need 2-4 weeks of 养号 (lifestyle posts, no marketing) before
  they can publish without triggering shadow-bans.
- Jan 2026 matrix-account sweep: 37 accounts banned in one operator.
- AI-generated content must be self-disclosed via 高级选项 → 内容类型声明.
  Failing to disclose triggers limit/ban.
- Official 开放平台 is whitelist-only (蒲公英/聚光/千帆 — brands only).

**Conclusion**: don't try to automate POSTING. Automate content PREP.
This adapter:

1. Refuses to post (raises NotConfigured permanently)
2. Generates a properly-formatted 小红书 笔记 ready for manual paste
3. Reminds you about the AI-disclosure requirement
4. Suggests image carousel structure (笔记 needs visuals to perform)

The 80/20 path for an indie OSS founder is **one warmed account, manual
posting 2-3x/week, AI-assisted writing pipeline**. This adapter gives you
the writing pipeline part. The publish button stays human.
"""
from __future__ import annotations

from marketing_agent.types import Platform, Post
from marketing_agent.platforms.base import NotConfigured


# 小红书 笔记 prefer hooks like these (per 2026 platform-voice research).
# Used by render_xiaohongshu() in templates if/when we add 小红书-specific
# templates. For now they're documentation hints.
RECOMMENDED_HOOKS = (
    "聊聊我做的 {project}",
    "30 天用 {project} 学到的 5 件事",
    "为什么我放弃 {alt} 改用 {project}",
    "做 {project} 之前我以为... 做完才发现...",
    "周末 fork 了 {project},发现一个超好用的功能",
)


class XiaohongshuAdapter:
    """Content-prep adapter — never auto-posts."""

    platform = Platform.XIAOHONGSHU

    # Permanently False. Even if a future env var is set we should NOT
    # flip this — auto-posting is a tax (account churn) per Q2 2026 research.
    def is_configured(self) -> bool:
        return False

    def dry_run_preview(self, post: Post) -> str:
        body = post.body
        title = post.title or "(请加一个 ≤20 字的标题)"
        n_chars = len(body)
        suggested_imgs = 9 if n_chars > 400 else 6 if n_chars > 200 else 3

        return (
            f"━━━━━━━━━━ 小红书 笔记 · {n_chars} 字 ━━━━━━━━━━\n"
            f"\n"
            f"标题: {title}\n"
            f"\n"
            f"{body}\n"
            f"\n"
            f"━━━━━━━━━━ 配图建议 ━━━━━━━━━━\n"
            f"建议 {suggested_imgs} 张图轮播(小红书算法偏好图文)。\n"
            f"封面用大字标题 + emoji,后续是分点截图/示意图。\n"
            f"用 `marketing-agent image --platform x` 生成单图,或用\n"
            f"https://creator.xiaohongshu.com 自带的模板。\n"
            f"\n"
            f"━━━━━━━━━━ ⚠ 发布前检查 ━━━━━━━━━━\n"
            f"1. 复制粘贴到 https://creator.xiaohongshu.com (移动端阅读量更高)\n"
            f"2. **必填** 高级选项 → 内容类型声明 → 选 \"使用了 AI 工具辅助\"\n"
            f"   (不勾选会被风控限流或 ban)\n"
            f"3. 账号:用真实养号 ≥2 周的账号 (新号会被 shadow-ban)\n"
            f"4. 节奏:每周 2-3 篇,别一天连发\n"
            f"5. 评论区互动 5+ 条,这是算法 weight\n"
            f"\n"
            f"━━━━━━━━━━ 算法友好的 hook 示例 ━━━━━━━━━━\n"
            + "\n".join(f"  · {h}" for h in RECOMMENDED_HOOKS)
            + "\n\n"
            "❌ 不要矩阵账号同步发同一篇 — Jan 2026 风控大扫荡封了 37 个账号\n"
            "❌ 不要写得太\"营销\" — 小红书的 voice 是个人化、casual、有故事感\n"
        )

    def post(self, post: Post) -> str:
        raise NotConfigured(
            "小红书 auto-posting is permanently disabled — see Q2 2026 research:\n"
            "  - TLS fingerprinting + behavioral risk control can't be defeated\n"
            "  - New accounts need 4 weeks 养号 before publishing\n"
            "  - Matrix automation triggers Jan 2026 sweep-style bans\n"
            "  - AI content must be self-disclosed (manual checkbox)\n"
            "Use dry_run_preview() to format the 笔记 for manual paste at\n"
            "https://creator.xiaohongshu.com instead. ROI of automation is "
            "negative once account-burn is factored."
        )
