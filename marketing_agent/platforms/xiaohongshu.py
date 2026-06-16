"""小红书 (Xiaohongshu / RED) adapter — **content prep only, NEVER auto-post**.

Per Q2 2026 + 2026-06-16 spike (xhs海外 IP geofence + Ares risk system):

- 阿瑞斯 (Ares) risk system uses TLS fingerprinting, device fingerprint,
  behavioral telemetry. Playwright+stealth defeats fingerprint surfaces
  but NOT TLS fingerprints or behavioral models. Detection is behavioral.
- New accounts need 2-4 weeks of 养号 (lifestyle posts, no marketing) before
  they can publish without triggering shadow-bans.
- Jan 2026 matrix-account sweep: 37 accounts banned in one operator.
- AI-generated content must be self-disclosed via 高级选项 → 内容类型声明.
- Official 开放平台 is whitelist-only (蒲公英/聚光/千帆 — brands only).
- **2026-06-16 verified**: creator.xiaohongshu.com 显式 block 海外 IP 登录
  ("系统升级中，暂不支持海外用户登录"). signer 'mnsv2' 在 window 上 callable,
  但是 IP geofence 是上游 hard block。Aitoearn 21k stars 那 1704 行 TypeScript
  也绕不过，他们用国内 server proxy。

**Conclusion**: don't try to automate POSTING. Automate content PREP.
This adapter:

1. Refuses to post (raises NotConfigured permanently)
2. Generates a properly-formatted 小红书 笔记 ready for manual paste
3. Renders an HTML preview (phone-shape) and auto-opens in browser
4. Auto-copies title + body + hashtags to clipboard for phone-paste
5. Reminds you about the AI-disclosure requirement

The 80/20 path for an indie OSS founder is **one warmed account, manual
posting 2-3x/week, AI-assisted writing pipeline**. This adapter gives you
the writing pipeline + a one-button "ready to paste" workflow. The publish
button stays human.
"""
from __future__ import annotations

import html
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from marketing_agent.types import Platform, Post
from marketing_agent.platforms.base import NotConfigured


# 小红书 笔记 prefer hooks like these (per 2026 platform-voice research).
RECOMMENDED_HOOKS = (
    "聊聊我做的 {project}",
    "30 天用 {project} 学到的 5 件事",
    "为什么我放弃 {alt} 改用 {project}",
    "做 {project} 之前我以为... 做完才发现...",
    "周末 fork 了 {project},发现一个超好用的功能",
)

# Default hashtag library — narrow, indie-OSS-flavored. Augmented by Claude
# suggest_tags() when ANTHROPIC_API_KEY is set; falls back to these otherwise.
DEFAULT_TAGS = (
    "#独立开发",
    "#AIagent",
    "#vibecoding",
    "#开源项目",
    "#一人公司",
    "#solofounder",
    "#claude",
    "#AI写作",
)


class XiaohongshuAdapter:
    """Content-prep adapter — never auto-posts."""

    platform = Platform.XIAOHONGSHU

    # Permanently False. Even if a future env var is set we should NOT
    # flip this — auto-posting is a tax (account churn + IP geofence)
    # per Q2 2026 + 2026-06-16 海外 IP block research.
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
            f"1. 复制粘贴到 小红书 APP (海外 IP 在 creator.xiaohongshu.com 被 block)\n"
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

    # ─────────────────────────────────────────────────────────────────────
    # v0.2 (2026-06-16) — paste-ready workflow
    # ─────────────────────────────────────────────────────────────────────

    def suggest_tags(self, post: Post, *, project_name: str = "") -> list[str]:
        """Return 5-8 hashtag suggestions. Uses Claude if ANTHROPIC_API_KEY set,
        else falls back to DEFAULT_TAGS.

        Output always includes a leading # and is dedup-safe.
        """
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            return list(DEFAULT_TAGS)
        try:
            from anthropic import Anthropic
        except ImportError:
            return list(DEFAULT_TAGS)

        client = Anthropic(api_key=key)
        prompt = (
            f"为下面这条小红书笔记建议 6-8 个 hashtag,中文优先,每个 ≤8 字,"
            f"不带空格,带 # 开头。优先选目前小红书 trending 的独立开发 / AI / "
            f"vibecoding / OPC 相关标签。只输出 hashtag 列表,每行一个,"
            f"不要其他文字。\n\n"
            f"项目名: {project_name or '未指定'}\n"
            f"标题: {post.title or '(无)'}\n"
            f"正文 (前 500 字):\n{post.body[:500]}\n"
        )
        try:
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text if resp.content else ""
            tags = []
            seen = set()
            for line in text.splitlines():
                t = line.strip().lstrip("-•· ").strip()
                if not t:
                    continue
                if not t.startswith("#"):
                    t = "#" + t
                # 去掉空格 / 长度限制
                t = t.replace(" ", "")
                if 2 < len(t) <= 12 and t not in seen:
                    tags.append(t)
                    seen.add(t)
                if len(tags) >= 8:
                    break
            return tags or list(DEFAULT_TAGS)
        except Exception:
            return list(DEFAULT_TAGS)

    def clipboard_payload(self, post: Post, tags: list[str]) -> str:
        """Build the single string that goes on clipboard — title + body + tags,
        ready to paste into the 小红书 APP composer.
        """
        title = post.title or ""
        body = post.body.strip()
        tag_line = " ".join(tags)
        parts = []
        if title:
            parts.append(title)
            parts.append("")
        parts.append(body)
        parts.append("")
        parts.append(tag_line)
        return "\n".join(parts)

    def copy_to_clipboard(self, payload: str) -> bool:
        """Copy payload to system clipboard. macOS uses pbcopy (no extra dep);
        other platforms fall back to pyperclip if available.

        Returns True on success.
        """
        try:
            if sys.platform == "darwin":
                proc = subprocess.run(
                    ["pbcopy"], input=payload.encode("utf-8"), check=True
                )
                return proc.returncode == 0
            # Linux / Windows fallback
            try:
                import pyperclip  # type: ignore
            except ImportError:
                return False
            pyperclip.copy(payload)
            return True
        except Exception:
            return False

    def render_html_preview(
        self,
        post: Post,
        tags: list[str],
        *,
        project_name: str = "",
        suggested_imgs: int | None = None,
    ) -> str:
        """Return a self-contained HTML string showing a phone-shape preview
        on the left + markdown source + paste payload on the right.

        Safe for `open` via subprocess: no JS, no external CDN, no analytics.
        """
        body = post.body
        title = html.escape(post.title or "(请加一个 ≤20 字的标题)")
        body_html = html.escape(body).replace("\n", "<br>")
        n_chars = len(body)
        if suggested_imgs is None:
            suggested_imgs = 9 if n_chars > 400 else 6 if n_chars > 200 else 3
        tag_chips = "".join(
            f'<span class="tag">{html.escape(t)}</span>' for t in tags
        )
        gen_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payload = html.escape(self.clipboard_payload(post, tags))

        return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>小红书 笔记 preview — {title}</title>
<style>
  :root {{ --red: #ff2742; --bg: #fafafa; --card: #fff; --ink: #1a1a1a; --muted: #888; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif;
         background: var(--bg); color: var(--ink); padding: 24px; }}
  h1 {{ font-size: 18px; margin: 0 0 16px; color: var(--muted); font-weight: 500; }}
  .grid {{ display: grid; grid-template-columns: 380px 1fr; gap: 32px; max-width: 1200px; }}
  .phone {{ width: 380px; border-radius: 36px; padding: 16px;
            background: #111; box-shadow: 0 20px 60px rgba(0,0,0,.2); }}
  .phone-inner {{ background: var(--card); border-radius: 24px; padding: 20px;
                  min-height: 600px; }}
  .phone-header {{ display: flex; align-items: center; gap: 8px; font-size: 12px;
                   color: var(--muted); margin-bottom: 16px; }}
  .phone-title {{ font-size: 20px; font-weight: 700; line-height: 1.3; margin: 8px 0 16px; }}
  .phone-body {{ font-size: 15px; line-height: 1.7; word-wrap: break-word; }}
  .phone-tags {{ margin-top: 16px; }}
  .tag {{ display: inline-block; background: rgba(255,39,66,.08); color: var(--red);
          padding: 2px 8px; border-radius: 12px; font-size: 12px; margin: 2px; }}
  .phone-meta {{ margin-top: 20px; padding-top: 12px; border-top: 1px solid #eee;
                 font-size: 12px; color: var(--muted); }}
  .side {{ display: flex; flex-direction: column; gap: 20px; }}
  .card {{ background: var(--card); border-radius: 12px; padding: 20px;
           box-shadow: 0 2px 8px rgba(0,0,0,.04); }}
  .card h2 {{ font-size: 14px; margin: 0 0 12px; color: var(--muted);
              font-weight: 500; text-transform: uppercase; letter-spacing: .05em; }}
  textarea {{ width: 100%; height: 200px; font: 13px / 1.6 ui-monospace, monospace;
              border: 1px solid #ddd; border-radius: 6px; padding: 12px;
              resize: vertical; background: #fdfdfd; }}
  .copy-hint {{ font-size: 12px; color: var(--muted); margin-top: 8px; }}
  .checklist li {{ font-size: 13px; line-height: 1.7; margin: 4px 0; }}
  .warn {{ color: var(--red); font-weight: 500; }}
  .ok {{ color: #22c55e; }}
</style></head><body>
  <h1>marketing-agent · 小红书 笔记 preview ·
      <span style="color:var(--ink)">{title}</span> · {n_chars} 字 · {gen_at}</h1>

  <div class="grid">
    <div class="phone"><div class="phone-inner">
      <div class="phone-header">📱 小红书 APP · 笔记预览</div>
      <div class="phone-title">{title}</div>
      <div class="phone-body">{body_html}</div>
      <div class="phone-tags">{tag_chips}</div>
      <div class="phone-meta">建议配图 {suggested_imgs} 张 · AI 工具辅助声明 ⚠</div>
    </div></div>

    <div class="side">
      <div class="card">
        <h2>📋 已复制到剪贴板 (paste-ready)</h2>
        <textarea readonly onclick="this.select()">{payload}</textarea>
        <div class="copy-hint">手机端长按粘贴框,把剪贴板内容贴到小红书 APP 笔记编辑器</div>
      </div>

      <div class="card">
        <h2>🚦 发布前 checklist</h2>
        <ul class="checklist">
          <li>1. 用 <span class="warn">小红书 APP</span> 发,不要用 creator.xiaohongshu.com (海外 IP block)</li>
          <li>2. <span class="warn">必填</span> 高级选项 → 内容类型声明 → 使用了 AI 工具辅助</li>
          <li>3. 账号 ≥ 2 周养号,新号会被 shadow-ban</li>
          <li>4. 节奏:每周 2-3 篇,别一天连发</li>
          <li>5. 发布后 30 min 内自己回复 5+ 评论,这是算法 weight</li>
          <li>6. 配图 {suggested_imgs} 张图轮播 — 封面大字标题 + emoji,后续分点截图</li>
        </ul>
      </div>

      <div class="card">
        <h2>💡 算法友好的 hook 示例</h2>
        <ul class="checklist">
{"".join(f'          <li>· {html.escape(h.format(project=project_name or "你的项目", alt="alt"))}</li>' for h in RECOMMENDED_HOOKS)}
        </ul>
      </div>
    </div>
  </div>
</body></html>
"""

    def paste_ready(
        self,
        post: Post,
        *,
        project_name: str = "",
        open_browser: bool = True,
    ) -> dict[str, object]:
        """One-shot v0.2 workflow:
        1. Suggest tags (Claude if available, else default lib)
        2. Build clipboard payload (title + body + tags)
        3. Copy payload to clipboard
        4. Render HTML preview, save to ~/Desktop/xhs-posts/<date>/<slug>.html
        5. Open HTML in default browser (macOS `open`)

        Returns dict with paths + tags + copied-bool, for CLI to print.
        """
        tags = self.suggest_tags(post, project_name=project_name)
        payload = self.clipboard_payload(post, tags)
        copied = self.copy_to_clipboard(payload)

        out_dir = Path.home() / "Desktop" / "xhs-posts" / datetime.now().strftime("%Y-%m-%d")
        out_dir.mkdir(parents=True, exist_ok=True)
        slug = (post.title or "untitled").strip()[:20].replace("/", "_") or "untitled"
        ts = datetime.now().strftime("%H%M%S")
        html_path = out_dir / f"{ts}-{slug}.html"
        html_text = self.render_html_preview(post, tags, project_name=project_name)
        html_path.write_text(html_text, encoding="utf-8")

        opened = False
        if open_browser and sys.platform == "darwin":
            try:
                subprocess.run(["open", str(html_path)], check=False)
                opened = True
            except Exception:
                opened = False

        return {
            "tags": tags,
            "html_path": str(html_path),
            "clipboard_copied": copied,
            "preview_opened": opened,
            "payload_chars": len(payload),
        }

    def post(self, post: Post) -> str:
        raise NotConfigured(
            "小红书 auto-posting is permanently disabled — see Q2 2026 + 2026-06-16 research:\n"
            "  - TLS fingerprinting + behavioral risk control can't be defeated\n"
            "  - New accounts need 4 weeks 养号 before publishing\n"
            "  - Matrix automation triggers Jan 2026 sweep-style bans\n"
            "  - AI content must be self-disclosed (manual checkbox)\n"
            "  - creator.xiaohongshu.com blocks 海外 IP at the server level (2026-06-16 verified)\n"
            "Use paste_ready() for the one-button workflow:\n"
            "  - copies title + body + hashtags to clipboard\n"
            "  - opens HTML phone-shape preview in browser\n"
            "  - lists pre-publish checklist (AI disclosure, 养号, 节奏)\n"
            "Then paste into 小红书 APP on phone. ROI of automation is negative."
        )
