# Orallexa Marketing Agent

**English** | [中文](README.zh-CN.md)

[![Version](https://img.shields.io/badge/version-0.15.0-blue.svg)](https://github.com/alex-jb/orallexa-marketing-agent/releases)
[![Tests](https://img.shields.io/badge/tests-300%20passing-brightgreen.svg)](#)
[![Coverage](https://img.shields.io/badge/coverage-77%25-brightgreen.svg)](#)
[![CI](https://github.com/alex-jb/orallexa-marketing-agent/actions/workflows/test.yml/badge.svg)](https://github.com/alex-jb/orallexa-marketing-agent/actions/workflows/test.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](#)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platforms](https://img.shields.io/badge/platforms-X%20%7C%20Reddit%20%7C%20LinkedIn%20%7C%20Dev.to%20%7C%20Bluesky%20%7C%20Mastodon%20%7C%20%E7%9F%A5%E4%B9%8E%20%7C%20%E5%B0%8F%E7%BA%A2%E4%B9%A6-purple.svg)](#)

> **Submit your AI/OSS project once. Get auto-generated, platform-specific marketing content. Distribute everywhere.**

An open-source Python SDK + CLI for solo OSS founders who write code well but don't have time (or audience) to do marketing themselves.

Built by [Xiaoyu (Alex) Ji](https://github.com/alex-jb) — Navy veteran, MS CS @ Yeshiva University, building [Orallexa](https://github.com/alex-jb/orallexa-ai-trading-agent) and [VibeXForge](https://github.com/alex-jb/vibex). Yes, it's named after Orallexa — that's the project that needed it most.

---

## Why this exists

You shipped a great AI/OSS project. 27 days later: 28 stars. Sound familiar?

The problem isn't the product. It's distribution. You're a builder, not a marketer. You have 3 GitHub followers and zero Twitter audience.

This is the tool I wish I had on day one of every OSS project: feed it a project description and it produces ready-to-post content tuned to each platform's voice — with a human-in-the-loop for the things that matter.

---

## Quickstart (30 seconds, no API keys)

```bash
git clone https://github.com/alex-jb/orallexa-marketing-agent.git
cd orallexa-marketing-agent
make install
make demo      # runs examples/generic_demo.py — no keys needed, all dry-run
```

You'll see X / Reddit / LinkedIn drafts for a fake project, generated locally via templates.

To enable LLM-quality content, add an Anthropic key to `.env`. To actually post, add platform keys. Both are optional — the SDK degrades gracefully.

---

## What it does

```
       Project metadata
              │
              ▼
    ┌────────────────┐
    │   Strategy     │  ← decides per-platform angle
    └────────────────┘
              │
              ▼
    ┌────────────────┐
    │   Content      │  ← Claude (or templates) writes it
    └────────────────┘
              │
    ┌─────────┼─────────┬──────────┐
    ▼         ▼         ▼          ▼
   X       Reddit    LinkedIn   (more)
    │         │         │
    └────┬────┴────┬────┘
         ▼         ▼
    Engagement events
         │
         ▼
   Feedback to strategy
```

---

## Status — v0.6.0

What works today:

| Layer | Capability |
|---|---|
| **Agentic core** | **Drafter → Critic → Rewriter supervisor** (Reflexion-lite, no LangGraph dep) · **persistent reflexion memory** (cross-session learning from past failures) · **Claude Agent SDK adapter** (uses official SDK 0.1.68+ when installed; falls back gracefully) · **prompt caching markers** on all LLM calls (cuts cost ~80% on daily cron) |
| **Content** | Claude (Sonnet 4.6 / Haiku 4.5) or template fallback · auto-thread split · image-prompt suggester · N stylistic variants per platform |
| **Platforms — auto-publish** | X (real, OAuth 1.0a) · Reddit (PRAW) · Bluesky (AT Protocol) · Mastodon (REST) |
| **Platforms — content-prep only** | Dev.to (markdown export, manual paste) · LinkedIn (API restricted) · **知乎 / 小红书 (manual publish, never auto — see [Chinese platform strategy](#chinese-platform-strategy-2026-reality))** |
| **Quality gate** | Heuristic + LLM critic (auto-rejects hype/spam/length-fail before queuing) · **hybrid retrieval dedup** (60% dense + 40% BM25, +17pp MRR vs dense-alone) — never repost a paraphrase |
| **Reliability** | Exponential-backoff retry on all platform adapters (transient errors, 429, 5xx) · structured JSON logs (Langfuse / OTel-compatible) |
| **Workflow** | HITL approval queue · 3 GitHub Actions: `daily.yml` · `release-announce.yml` · `publish.yml` · **multi-project YAML config** (one cron, N projects) |
| **Strategy** | LaunchPlan generator (30/60/90-day, PH-launch-relative timing) · reply-draft suggester · variant bandit (Thompson sampling) · best-time-to-post (hour-of-week CDF) |
| **Analytics** | EngagementTracker pulls X metrics · cost tracker (Anthropic + X per-post) · SQLite single-file storage |
| **Integrations** | VibeXForge sister-product event push · **MCP server** (`marketing-agent-mcp`) · **Claude Skill** (`skills/marketing-voice/`) · **A2A agent card** (`agent_card.json`) — discoverable by other agents |
| **Distribution** | **Dockerfile + docker-compose** (one-command self-host) · CI matrix (Python 3.11/3.12) · pytest-cov 60%+ floor · Codecov upload |

CLI: `generate · post · queue · history · cost · plan · bandit · best-time · replies · engage` — 10 subcommands.

Roadmap:
- [x] **v0.1** — scaffold, X / Reddit / LinkedIn stubs
- [x] **v0.2** — memory + threads + queue + cost + Bluesky + Mastodon + CLI
- [x] **v0.3** — reply suggester + engagement tracker + launch planner + 知乎/小红书 stubs + VibeXForge + image prompts
- [x] **v0.4** — variant bandit · best-time-to-post · MCP server · 60/90-day plans · PH-launch-relative timing
- [x] **v0.5** — critic gate + semantic dedup + retries + structured logging + GitHub release webhook + CI
- [x] **v0.6** — supervisor (Drafter→Critic→Rewriter) + reflexion memory + hybrid retrieval (BM25+dense) + Claude Agent SDK adapter + prompt caching + multi-project config + Skill + A2A card + Docker
- [x] **v0.7** — real image generation (Pollinations / Flux schnell, free, no key) · X media upload (auto-attach generated image to tweets) · `image` CLI subcommand · `Post.image_url` field
- [x] **v0.8** — Phoenix / OTel observability (opt-in `[observability]` extras) · DSPy signatures framework (4 typed Signatures, compilation hook ready) · PyPI build artifact + `publish-pypi.yml` workflow · `py.typed` marker
- [x] **v0.9** — hardening sprint: reply_suggester 0%→81% coverage · X/Bluesky/Mastodon image upload mock tests · MCP tool integration tests · BM25 single-doc fix · shared critic min-score constant · CHANGELOG.md · CI floor 60%→70%
- [x] **v0.10** — Streamlit queue UI (`marketing-agent ui`, browser/phone-friendly) · scheduled posting (`scheduled_for` frontmatter + hourly cron + `marketing-agent schedule --best-time`) · CLI smoke tests (cli.py 0% → covered) · 198 tests, 76% coverage
- [x] **v0.11** — **ICPL** (in-context preference learning from edits, no fine-tune needed) · **multi-LLM ensemble critic** via LiteLLM (Claude + GPT-5 + Gemini majority vote) · **self-consistency-3** for short-form supervisor · **Bluesky firehose listener** (free real-time engagement, vs X's $42k/yr Enterprise webhook) · 228 tests, 75% coverage
- [x] **v0.12** — **Edge inference fallback** (Cloudflare Workers AI Llama 3.3 as cheap drafter, ~80% cost reduction vs Claude) · **Voyager-style auto-skill promotion** (top-quartile posts → `skills/learned/*.md`) · **A/B variants report** (per-platform winner with 95% credible intervals) · **Failure post-mortem** (`marketing-agent autopsy --post-id X` heuristic explanation) · 269 tests, 76% coverage
- [ ] **v0.13** — DSPy compilation against engagement history · Computer Use 知乎/小红书 publishing · X engagement webhook (deferred — Enterprise tier $$) · PyPI auto-publish on tag
- [ ] **v1.0** — open-source launch · YC application

---

## Chinese platform strategy — 2026 reality

Per Q2 2026 anti-bot research, the agent **deliberately does not auto-publish** to 小红书 (Xiaohongshu) or 知乎 (Zhihu). Here's why and what we do instead.

**Why no auto-post**:
- 小红书's 阿瑞斯 risk system uses TLS fingerprinting + behavioral telemetry. Playwright + stealth defeats client-side fingerprints but **not** TLS or behavioral models. Detection is behavioral.
- New 小红书 accounts need 2-4 weeks of 养号 before they can publish without shadow-bans. Jan 2026 sweep: 37 matrix accounts banned in one operator.
- 小红书 requires self-disclosure of AI-assisted content (高级选项 → 内容类型声明). Failing to disclose triggers limit/ban.
- 知乎 has no public publishing API since 2020. Multi-account automation gets caught fast.
- Anthropic Computer Use works functionally but adds **no detection advantage** over Playwright (same browser surface) and costs ~$0.30-1/post in screenshot tokens.
- Official 小红书 开放平台 is whitelist-only (蒲公英 / 聚光 / 千帆 — brands, not indie devs).

**What the agent DOES do for these platforms**:
1. **Generates platform-tuned content prep** via `marketing_agent.platforms.zhihu.dry_run_preview()` and `xiaohongshu.dry_run_preview()` — formatted body + AI-disclosure reminder + algorithm-friendly hooks + length classifier (短答/中等/长答 for 知乎, 配图建议 for 小红书).
2. **Reminds you of every 2026 platform rule** before you paste manually.
3. **Routes you to the right place**: 知乎 to a target question (回答 ≫ 文章 for SEO), 小红书 to `creator.xiaohongshu.com` with the AI checkbox checked.

**The 80/20 path for an indie OSS founder in 2026**:
- One real warmed account per platform. Manual publish, 2-3x/week.
- 知乎 = highest leverage. Long-form 回答 with code blocks ranks on Baidu for years.
- Skip 微信视频号 (April 2026 banned all third-party automated publishing).
- For video content, use Bilibili (official open platform supports uploads with a real dev account).
- Reserve automation for **read-only**: trend scraping, comment monitoring, competitor 笔记 analysis.

> **Bottom line**: Automate the writing pipeline, not the publish button. The agent is doing this because the 2026 ROI of automated Chinese-platform posting is **negative** once account-burn is factored.

---

## Layout

```
orallexa-marketing-agent/
├── marketing_agent/
│   ├── types.py             Pydantic models for Project, Post, Platform, Engagement
│   ├── content/             Content generation + image prompt suggester
│   ├── platforms/           8 adapters (X, Reddit, LinkedIn, Dev.to, Bluesky, Mastodon, 知乎, 小红书)
│   ├── integrations/        VibeXForge event push
│   ├── orchestrator.py      High-level: project → posts → distribute
│   ├── memory.py            SQLite dedup
│   ├── queue.py             Markdown-file approval queue (Obsidian-friendly)
│   ├── threads.py           Auto-split long posts into threads
│   ├── cost.py              Per-call Anthropic + X cost tracking
│   ├── engagement.py        Pull X metrics, rank top posts
│   ├── reply_suggester.py   Scan handles → filter → draft replies → queue
│   ├── strategy.py          LaunchPlan generator (template + LLM)
│   └── cli.py               argparse CLI: generate/post/queue/history/cost/plan/replies/engage
├── examples/                Offline demos (no API keys needed)
├── scripts/daily_post.py    Cron-friendly: GitHub commits → posts
├── .github/workflows/       Daily auto-post Action
└── tests/                   49 tests, all offline
```

---

## Design principles

1. **Tri-mode operation** — works with no keys (template fallback), with Claude key (LLM generation), with platform keys (real posting). Never crash for missing keys.
2. **Pydantic everywhere** — no untyped dicts crossing module boundaries.
3. **Adapters are protocols** — same interface for every platform, easy to extend.
4. **Reasonable defaults** — `make demo` works offline, no setup.
5. **No secrets in code** — `os.getenv` exclusively, `.env.example` as template.

---

## Automation — HITL pipeline (GitHub Actions)

Two workflows form a **draft → review → publish** loop. The agent never posts to social media without your approval, but everything else is automatic.

```
        ┌─────────────────────┐
        │ daily.yml @14:00 UTC│  scrapes GitHub commits → drafts → queue/pending/
        └──────────┬──────────┘  → opens "📥 Daily drafts ready" Issue
                   │
                   ▼
        ┌─────────────────────┐
        │  YOU review         │  on github.com or after `git pull`
        │  • approve  →  git mv pending/X.md approved/X.md
        │  • reject   →  git mv pending/X.md rejected/X.md
        └──────────┬──────────┘
                   ▼
        ┌─────────────────────┐
        │ publish.yml         │  triggered by push to queue/approved/
        └──────────┬──────────┘  → posts to X / Reddit / Bluesky / etc.
                   │             → moves to queue/posted/, commits state back
                   ▼
              real social media
```

### One-time setup

1. **Add secrets** at `https://github.com/<you>/<repo>/settings/secrets/actions`:
   - `ANTHROPIC_API_KEY` (optional — falls back to template mode)
   - `X_API_KEY`, `X_API_KEY_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`
   - `REDDIT_*`, `BLUESKY_*`, `MASTODON_*` (any platform you want enabled)

2. **Trigger first run** manually: Actions → "Daily draft generator (HITL)" → Run workflow.

3. **Approve a draft** to test publish.yml:
   ```bash
   git pull
   git mv queue/pending/<file>.md queue/approved/<file>.md
   git commit -m "approve: test" && git push
   ```

### Skipping rules

`daily_post.py` skips when:
- No commits in the lookback window (default 24h)
- All commits are CI-only / docs-only / chore-only

Override with `--force` (testing only).

### Targets

`daily.yml` defaults to `alex-jb/orallexa-ai-trading-agent`. Add new repos to `REPO_PRESETS` in `scripts/daily_post.py`, or pass `--repo` via workflow_dispatch.

---

## License

MIT — use it, fork it, ship it.

---

*Hand-built by Alex while waiting for his first 100 GitHub stars. Hopefully you don't need to wait that long.*
