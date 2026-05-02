# Orallexa Marketing Agent

[English](README.md) | **中文**

[![Version](https://img.shields.io/badge/version-0.18.6-blue.svg)](https://github.com/alex-jb/orallexa-marketing-agent/releases)
[![Tests](https://img.shields.io/badge/tests-408%20passing-brightgreen.svg)](#)
[![PyPI](https://img.shields.io/pypi/v/orallexa-marketing-agent.svg)](https://pypi.org/project/orallexa-marketing-agent/)
[![Coverage](https://img.shields.io/badge/coverage-77%25-brightgreen.svg)](#)
[![CI](https://github.com/alex-jb/orallexa-marketing-agent/actions/workflows/test.yml/badge.svg)](https://github.com/alex-jb/orallexa-marketing-agent/actions/workflows/test.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](#)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platforms](https://img.shields.io/badge/platforms-X%20%7C%20Reddit%20%7C%20LinkedIn%20%7C%20Dev.to%20%7C%20Bluesky%20%7C%20Mastodon%20%7C%20%E7%9F%A5%E4%B9%8E%20%7C%20%E5%B0%8F%E7%BA%A2%E4%B9%A6-purple.svg)](#)

> **项目信息提交一次，自动生成各平台专属营销内容，多端分发。**

为独立 OSS 开发者打造的 Python SDK + CLI —— 你写代码不写营销，我们帮你写。

由 [Xiaoyu (Alex) Ji](https://github.com/alex-jb) 构建 —— 美军老兵、Yeshiva University 计算机硕士在读。同时维护 [Orallexa](https://github.com/alex-jb/orallexa-ai-trading-agent)（量化 AI 交易系统）和 [VibeXForge](https://vibexforge.com)（AI 创作者增长平台）。这个工具是因为 Orallexa 当时最需要它，所以以它命名。

---

## 为什么做这个

你做了个不错的 AI / OSS 项目，27 天后只有 28 个 star。你不缺产品，缺的是 distribution。你是 builder 不是 marketer，X 上 3 个粉丝，Twitter 没受众。

这是我希望我每个 OSS 项目第一天就有的工具：喂给它项目描述，它产出各平台调过音的可发文案 —— 关键决策保留 human-in-the-loop。

---

## 30 秒快速开始（无需 API key）

```bash
git clone https://github.com/alex-jb/orallexa-marketing-agent.git
cd orallexa-marketing-agent
make install
make demo      # 跑 examples/generic_demo.py — 全离线，模板模式
```

会输出一个虚构项目的 X / Reddit / LinkedIn 草稿（本地模板生成）。

要 LLM 级文案：在 `.env` 加 `ANTHROPIC_API_KEY`。
要真发到平台：再加各平台密钥。两者都是可选 —— SDK 优雅降级。

---

## 它能做什么

```
       项目元数据
          │
          ▼
    ┌────────────┐
    │  Strategy  │  ← 决定每个平台的角度
    └────────────┘
          │
          ▼
    ┌────────────┐
    │  Content   │  ← Claude（或模板）写文案
    └────────────┘
          │
    ┌─────┼─────┬──────────┐
    ▼     ▼     ▼          ▼
   X   Reddit LinkedIn  （更多）
    │     │     │
    └──┬──┴──┬──┘
       ▼     ▼
    Engagement events
       │
       ▼
   反馈到 Strategy
```

---

## 当前状态 — v0.18.6（PyPI 已上线、bandit 反馈闭环已自动化）

408 tests passing · 77% coverage · CI Python 3.11 / 3.12 全绿 · PyPI:`pip install "orallexa-marketing-agent[mcp]"`

| 层 | 能力 |
|---|---|
| **生成器** | HYBRID = Cloudflare Workers AI 边缘层（Llama 3.3,~$0.011/1M tokens）→ Anthropic Sonnet 4.6 fallback。两者都挂会降级模板(并打 warning,杜绝静默失败)。Prompt caching 让 daily cron 输入 token 成本省 ~80% |
| **质量门** | Heuristic + LLM critic 自动拒废稿(hype 词/字数/hashtag 灌水)。**混合检索去重**(60% 稠密 + 40% BM25,比纯稠密 +17pp MRR) — 永不重发释义。**X 280-char 三层防御**(小 hook + 严 prompt + LLM-后 retry/截断) |
| **自我进化栈** | **Variant bandit**(Thompson Beta-conjugate emoji/question/stat-led;LLM 调用前选 hint,1 次 LLM call/平台)。**Reflexion memory**(跨 session critic 模式)。**ICPL 偏好库**(从人工编辑提取 5-shot)。**Voyager 自动技能晋升**(top-quartile 帖 → `skills/learned/*.md` 同时镜像 `~/.solo-founder-os/skills/<slug>.md` 给跨 agent 用) |
| **主动循环** | **Trends 模块** 扫 GitHub / HN / Reddit(免费,纯 stdlib HTTP)+ **VibeX top-of-feed source**(自家平台热门 project,通过 Supabase Management API 拉,$0)。**`trends_to_drafts`** 把 top N 转成多平台 drafts。**(project, URL) 冷却**(默认 7 天)防止连续 4 天写同一条 hot 故事 |
| **成本守门** | **`MARKETING_AGENT_DAILY_BUDGET_USD`** 软上限(读 `~/.marketing-agent/usage.jsonl`、按 `cost.PRICES` 计价、当日 UTC 累计;超额跳过主动 pass)。跨 provider usage 日志统一写入一个 JSONL,cost-audit-agent 直接读 |
| **平台 — 自动发布** | X (OAuth 1.0a + Bearer 用于读) · Reddit (PRAW) · Bluesky (AT Protocol) · Mastodon (REST) · Threads (Meta Graph API,2026 年 4 月正式开放) |
| **平台 — 内容准备** | Dev.to (markdown 导出) · LinkedIn (API 限制严) · **知乎 / 小红书**(手动粘,永远不自动 — 见[中文平台策略](#中文平台策略--2026-反爬现实)) |
| **工作流** | HITL 审批 queue(Obsidian 友好 markdown)。6 个 GitHub Actions:`daily.yml`(commit + trends drafts)、`publish.yml`(push 触发发布)、`scheduled.yml`(每小时发已 due 的)、`test.yml`、`lint.yml`、`mcp-install-check.yml`。**多项目 YAML 配置**(一个 cron N 个项目)。PyPI Trusted Publishing OIDC |
| **跨 agent 互通(SFOS interop)** | Reflexions、技能晋升、ICPL 对都镜像到 `~/.orallexa-marketing-agent/*.jsonl` 和 `~/.solo-founder-os/skills/`,让 `solo-founder-os` v0.19+ 工具(sfos-evolver、sfos-retro、sfos-eval)看见 marketing-agent 数据。Bandit + autopsy 已晋升到 SFOS core 给整个 stack 共用 |
| **自动化** | 本地 launchd:**每天 06:30 EDT** 自动拉 X engagement → 更新 bandit posterior。**周日 09:00** 跑 `sfos-retro` 跨 agent 周报。PH-day 提醒 + trend-perf 复盘 plist 也在 scripts/ 里 |
| **集成** | **MCP server**(`marketing-agent-mcp` 给 Claude Code / Desktop / Cursor / Zed)· **Claude Skill**(`skills/marketing-voice/`)· **A2A agent card**(`agent_card.json`)· VibeXForge 事件回推 · DSPy signatures 框架 |
| **分发** | **PyPI**(`pip install orallexa-marketing-agent[mcp]`)· **Dockerfile + docker-compose** · CI matrix Python 3.11/3.12 · pytest-cov 70% floor · Codecov |

**CLI(17 个子命令):** `generate · post · history · cost · queue · plan · schedule · ui · trends · trends-to-drafts · autopsy · skills · image · bandit · best-time · replies · engage`

**Roadmap(近期 + 下一步):**

- [x] **v0.10-0.12** — Streamlit UI · 定时发布 · ICPL · LiteLLM ensemble critic · Bluesky firehose · Cloudflare 边缘推理 · Voyager 技能晋升 · A/B 报告 · autopsy
- [x] **v0.13-0.14** — solo-founder-os AnthropicClient 迁移 · 跨 provider usage 日志
- [x] **v0.15-0.16** — Trends 模块(GitHub/HN/Reddit)· Threads(Meta)自动发布
- [x] **v0.17.x** — `trends_to_drafts` 主动循环 · 项目级 trend 去重 · 每日 LLM 预算 · 每日 issue body 拆分
- [x] **v0.18.x** — VibeX top-of-feed → TrendItem source(`$0` Supabase)· 跨 agent SFOS sinks(reflections / skills / preference)· bandit + autopsy 晋升到 `solo-founder-os` core · LLM 路径 variant_key 标签 · trends 280-char 三层修复 · 每日 engagement → bandit launchd · 周 sfos-retro launchd · PyPI 上线(Trusted Publishing OIDC)
- [ ] **v0.19** — DSPy 用 engagement 历史编译 · MCP marketplace 上架(PH 后)· 跨 agent bandit 数据交换
- [ ] **v1.0** — 公开 OSS launch · YC 申请

---

## 中文平台策略 — 2026 反爬现实

研究表明,**永远不要自动发到 小红书 / 知乎**。这个 agent 故意不做这件事。理由：

**为什么不自动发**:
- 小红书的"阿瑞斯"风控系统用 TLS 指纹 + 行为遥测。Playwright + stealth 能绕过浏览器指纹,但**绕不过** TLS 指纹和行为模型。检测是行为级的。
- 小红书新号需要 2-4 周养号才能正常发布。2026 年 1 月一次扫荡封了 37 个矩阵账号。
- 小红书要求 AI 内容必须自己声明（高级选项 → 内容类型声明）,不勾选会限流或 ban。
- 知乎 自 2020 年起没有公开发布 API。多账号自动化抓得很快。
- Anthropic Computer Use 功能上能做但**没有检测优势**（同样的 browser surface）,而且每条帖要 ~$0.30-1 的截图 token。
- 小红书官方开放平台是白名单（蒲公英/聚光/千帆 — 品牌方,独立开发者用不了）。

**这个 agent 做了什么 instead**:
1. **生成平台调过音的内容**：`zhihu.dry_run_preview()` / `xiaohongshu.dry_run_preview()` 给你格式化好的正文 + AI 声明提醒 + 算法友好的 hook 模板 + 长度分类（短答/中等/长答 / 图片建议）
2. **每条 2026 平台规则提前提醒** 在你手动粘贴前
3. **指引到正确入口**: 知乎 → 找一个现有问题点"写回答"（回答 ≫ 文章 for SEO）；小红书 → `creator.xiaohongshu.com` + 勾 AI 选项

**OSS 独立开发者 2026 年的 80/20 路径**:
- 每个平台一个真养号的真账号,手动每周发 2-3 条
- 知乎是中文最高 ROI 的渠道：长文回答 + 代码块,百度 SEO 能排几年
- 跳过微信视频号（2026 年 4 月 banned 所有第三方自动发布）
- 视频内容走 Bilibili（开放平台支持上传,需要真开发者账号）
- 自动化用在**只读**：趋势抓取、评论监控、竞品笔记分析

> **底线**：把写文 pipeline 自动化,不要把"发布"按钮自动化。2026 年自动发中文平台的 ROI 把账号烧损算进去就是负的。
- [ ] **v1.0** — 开源公开 launch · YC 申请

---

## 自动化 — HITL 流水线

两个 workflow 形成 **草稿 → 审核 → 发布** 闭环。Agent 在没有你点头的情况下绝对不会发到社交媒体；其他一切自动。

```
        ┌─────────────────────┐
        │ daily.yml @14:00 UTC│  抓 GitHub commits → 草稿 → queue/pending/
        └──────────┬──────────┘  → 开 "📥 Daily drafts ready" Issue
                   │
                   ▼
        ┌─────────────────────┐
        │  你 review          │  在 github.com 或 `git pull` 之后
        │  • 通过  →  git mv pending/X.md approved/X.md
        │  • 拒绝  →  git mv pending/X.md rejected/X.md
        └──────────┬──────────┘
                   ▼
        ┌─────────────────────┐
        │ publish.yml         │  push 到 queue/approved/ 触发
        └──────────┬──────────┘  → 真发到 X / Reddit / Bluesky / etc.
                   │             → 移到 queue/posted/，state 提交回来
                   ▼
              真社交媒体平台
```

### 一次性配置

1. **加 secrets**（`https://github.com/<你>/<repo>/settings/secrets/actions`）：
   - `ANTHROPIC_API_KEY`（可选 —— 没有就降级到模板模式）
   - `X_API_KEY`、`X_API_KEY_SECRET`、`X_ACCESS_TOKEN`、`X_ACCESS_TOKEN_SECRET`
   - `REDDIT_*`、`BLUESKY_*`、`MASTODON_*`（你想启用哪个平台就配哪个）

2. **手动触发首次跑**：Actions → "Daily draft generator (HITL)" → Run workflow

3. **审核草稿** 测试 publish.yml：
   ```bash
   git pull
   git mv queue/pending/<file>.md queue/approved/<file>.md
   git commit -m "approve: test" && git push
   ```

### 跳过规则

`daily_post.py` 在以下情况会跳过：
- 时间窗（默认 24h）内没有 commit
- 所有 commit 都是 CI / docs / chore-only

`--force` 强制覆盖（仅测试用）。

### 多项目目标

`marketing-agent.yml` 列出所有要营销的项目；cron 会迭代每一个 enabled 的：

```yaml
projects:
  - name: Orallexa
    repo: alex-jb/orallexa-ai-trading-agent
    tagline: 自我调优的多 agent AI 交易系统
    platforms: [x]
    enabled: true
  - name: VibeXForge
    repo: alex-jb/vibex
    tagline: AI 创作者打造的游戏化增长平台
    platforms: [x]
    enabled: true
```

---

## 设计原则

1. **三模式运行** —— 没有 key 也能跑（模板降级），有 Claude key 走 LLM，有平台 key 真发。永远不会因为缺 key 而 crash。
2. **类型严格** —— 模块边界用 Pydantic，从不传未类型化的 dict。
3. **Adapter 是 Protocol** —— 每个平台同一接口，扩展新平台很容易。
4. **合理默认** —— `make demo` 离线就能跑，零配置。
5. **代码里没有秘密** —— 全用 `os.getenv`，`.env.example` 是模板。

---

## 可选依赖

```bash
pip install "orallexa-marketing-agent[mcp]"          # MCP server
pip install "orallexa-marketing-agent[embeddings]"   # 本地 sentence-transformers
pip install "orallexa-marketing-agent[agent_sdk]"    # Anthropic Agent SDK 0.1.68+
```

---

## 未来 / 付费方案 —— *推测中*

把 `marketing-agent` 包装成跑在 [VibeXForge](https://vibexforge.com) 里的 **托管 SaaS**,架构已经全设计好了但**还没动一行代码**。详细架构、定价、以及触发 Phase-1 实作的「需求信号阈值」见 [`docs/future/saas-design.md`](docs/future/saas-design.md)。

承诺没变:这里的 OSS 工具就是产品本身,而且永远免费。SaaS 设计文档放在那里只是为了让感兴趣的创业者 / 投资人 / 合作者能直接看明白增长故事,不需要我再讲一遍。

MCP server 上架(Anthropic marketplace + `modelcontextprotocol/servers` 注册表)等 PH 2026-05-04 之后再发 —— 包装套件见 [`docs/mcp-listing/`](docs/mcp-listing/)。

---

## 协议

MIT —— 用它，fork 它，发出去。

---

*作者一边等他第一个 100 GitHub stars 一边手搓出来的。希望你不用等那么久。*
