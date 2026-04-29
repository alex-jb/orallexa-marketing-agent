# Orallexa Marketing Agent

[English](README.md) | **中文**

[![Version](https://img.shields.io/badge/version-0.6.0-blue.svg)](https://github.com/alex-jb/orallexa-marketing-agent/releases)
[![Tests](https://img.shields.io/badge/tests-116%20passing-brightgreen.svg)](#)
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

## 当前状态 — v0.6.0

| 层 | 能力 |
|---|---|
| **Agent 内核** | **Drafter → Critic → Rewriter supervisor**（Reflexion-lite，无需 LangGraph 依赖）· **持久化 reflexion memory**（跨 session 学习历史失败模式）· **Claude Agent SDK 适配器**（装了就用官方 SDK 0.1.68+，否则降级）· **Prompt caching 标记**（key 配上后 daily cron 省 ~80% 输入 token） |
| **内容生成** | Claude Sonnet 4.6 / Haiku 4.5 或模板降级 · 自动拆 thread · 配图 prompt suggester · 每平台 N 个风格变体 |
| **支持平台** | X (OAuth 1.0a) · Reddit (PRAW) · Bluesky (AT Protocol) · Mastodon (REST) · Dev.to (markdown) · LinkedIn (dry-run) · 知乎 / 小红书 (Phase 3 — Playwright) |
| **质量门** | Heuristic + LLM critic 自动拒废稿（hype 词、字数超限、全大写、hashtag 灌水）· **混合检索去重**（60% 稠密 + 40% BM25，比纯稠密 +17pp MRR） |
| **可靠性** | 平台 adapter 指数退避重试（429 / 5xx / 网络抖动） · 结构化 JSON 日志（Langfuse / OTel 兼容） |
| **工作流** | HITL 审批 queue · 4 个 GitHub Actions：`daily.yml` · `release-announce.yml` · `publish.yml` · `test.yml` · **多项目 YAML 配置** |
| **策略** | 30/60/90 天 launch plan（Product-Hunt-相对时序）· reply-draft suggester · 变体 bandit（Thompson 采样）· 最佳发帖时间（hour-of-week 经验 CDF） |
| **集成** | VibeXForge 事件回推 · **MCP server**（Claude Code / Desktop / Cursor / Zed）· **Claude Skill**（`skills/marketing-voice/`）· **A2A agent card**（被其他 agent 发现） |
| **分发** | **Dockerfile + docker-compose**（一行自托管） · CI Python 3.11/3.12 · pytest-cov 60%+ |

CLI 子命令（10 个）：`generate · post · queue · history · cost · plan · bandit · best-time · replies · engage`

Roadmap：

- [x] **v0.1** — 脚手架，X / Reddit / LinkedIn stub
- [x] **v0.2** — memory + threads + queue + cost + Bluesky + Mastodon + CLI
- [x] **v0.3** — reply suggester + engagement tracker + launch planner + 知乎/小红书 stub + VibeXForge + 配图 prompt
- [x] **v0.4** — 变体 bandit · 最佳发帖时间 · MCP server · 60/90 天 plan · PH-相对时序
- [x] **v0.5** — critic gate + 语义去重 + 重试 + 结构化日志 + GitHub release webhook + CI
- [x] **v0.6** — supervisor (Drafter→Critic→Rewriter) + reflexion memory + 混合检索 (BM25+稠密) + Claude Agent SDK 适配器 + prompt caching + 多项目 config + Skill + A2A card + Docker
- [ ] **v0.7** — Phoenix / OTel observability · Imagen 4 / Nano Banana 2 配图生成 · DSPy prompt 编译 · PyPI 发布
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

## 协议

MIT —— 用它，fork 它，发出去。

---

*作者一边等他第一个 100 GitHub stars 一边手搓出来的。希望你不用等那么久。*
