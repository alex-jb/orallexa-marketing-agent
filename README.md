# Orallexa Marketing Agent

**English** | [中文](README.zh-CN.md)

[![Version](https://img.shields.io/badge/version-0.18.6-blue.svg)](https://github.com/alex-jb/orallexa-marketing-agent/releases)
[![Tests](https://img.shields.io/badge/tests-408%20passing-brightgreen.svg)](#)
[![PyPI](https://img.shields.io/pypi/v/orallexa-marketing-agent.svg)](https://pypi.org/project/orallexa-marketing-agent/)
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

## Status — v0.18.6 (PyPI live, full bandit feedback loop running)

408 tests passing · 77% coverage · CI green Python 3.11 / 3.12 · live on PyPI: `pip install "orallexa-marketing-agent[mcp]"`

| Layer | What works today |
|---|---|
| **Generator** | HYBRID = Cloudflare Workers AI edge tier (Llama 3.3, ~$0.011/1M tokens) → Anthropic Sonnet 4.6 fallback. Falls through to deterministic templates if both fail (with warning log so silent failure is impossible). Prompt caching cuts cost ~80% on daily cron. |
| **Quality gate** | Heuristic + LLM critic (auto-rejects hype words, length overflow, hashtag spam). **Hybrid retrieval dedup** (60% dense + 40% BM25, +17pp MRR vs dense-alone) — never reposts a paraphrase. **3-layer X 280-char overflow defense** (small hook + strict prompt + post-LLM retry/truncate). |
| **Self-evolving stack** | **Variant bandit** (Thompson Beta-conjugate over emoji/question/stat-led; pre-LLM hint selection so 1 LLM call per platform). **Reflexion memory** (cross-session critic patterns). **ICPL preference store** (5-shot exemplars from human edits). **Voyager auto-skill promotion** (top-quartile posts → `skills/learned/*.md` AND `~/.solo-founder-os/skills/<slug>.md` for cross-agent reuse). |
| **Proactive loop** | **Trends module** scans GitHub / HN / Reddit (free, stdlib HTTP only) + **VibeX top-of-feed source** (your own platform's hot projects via Supabase Management API, $0). **`trends_to_drafts`** turns top N into platform-specific drafts. **Per-(project, URL) cooldown** (default 7d) prevents writing about the same hot story 4 days in a row. |
| **Cost guards** | **`MARKETING_AGENT_DAILY_BUDGET_USD`** soft cap (reads `~/.marketing-agent/usage.jsonl`, prices via `cost.PRICES`, sums today UTC; skips proactive pass when over). Cross-provider usage logging into a single JSONL the cost-audit-agent reads. |
| **Platforms — auto-publish** | X (OAuth 1.0a + Bearer for reads) · Reddit (PRAW) · Bluesky (AT Protocol) · Mastodon (REST) · Threads (Meta Graph API, production April 2026) |
| **Platforms — content-prep only** | Dev.to (markdown export) · LinkedIn (API restricted) · **知乎 / 小红书** (manual paste, never auto — see [Chinese platform strategy](#chinese-platform-strategy-2026-reality)) |
| **Workflow** | HITL approval queue (Obsidian-friendly markdown). 6 GitHub Actions: `daily.yml` (commit-driven + trends drafts), `publish.yml` (push to approved/), `scheduled.yml` (hourly publish-due), `test.yml`, `lint.yml`, `mcp-install-check.yml`. **Multi-project YAML config** (one cron, N projects). PyPI Trusted Publishing via OIDC. |
| **Cross-agent (SFOS interop)** | Reflexions, skill promotions, and ICPL pairs are mirrored to `~/.orallexa-marketing-agent/*.jsonl` and `~/.solo-founder-os/skills/` so `solo-founder-os` v0.19+ tools (sfos-evolver, sfos-retro, sfos-eval) see marketing-agent's data. Bandit + autopsy promoted to SFOS core for the rest of the stack. |
| **Automation** | Local launchd jobs: **daily 06:30 EDT** auto-pulls X engagement → updates bandit posterior. **Sunday 09:00** runs `sfos-retro` cross-agent digest. PH-day reminder + trend-perf retro launchd plists ship as scripts. |
| **Integrations** | **MCP server** (`marketing-agent-mcp` for Claude Code / Desktop / Cursor / Zed) · **Claude Skill** (`skills/marketing-voice/`) · **A2A agent card** (`agent_card.json`) · VibeXForge event push · DSPy signatures framework |
| **Distribution** | **PyPI** (`pip install orallexa-marketing-agent[mcp]`) · **Dockerfile + docker-compose** · CI matrix Python 3.11/3.12 · pytest-cov 70% floor · Codecov |

**CLI (17 subcommands):** `generate · post · history · cost · queue · plan · schedule · ui · trends · trends-to-drafts · autopsy · skills · image · bandit · best-time · replies · engage`

**Roadmap (recent + upcoming):**
- [x] **v0.10-0.12** — Streamlit UI · scheduled posting · ICPL · LiteLLM ensemble critic · Bluesky firehose · Cloudflare edge inference · Voyager skill promotion · A/B variants report · autopsy
- [x] **v0.13-0.14** — solo-founder-os AnthropicClient migration · cross-provider usage logging
- [x] **v0.15-0.16** — Trends module (GitHub/HN/Reddit) · Threads (Meta) auto-publish
- [x] **v0.17.x** — `trends_to_drafts` proactive loop · per-project trend dedup · daily LLM budget cap · daily issue body breakdown
- [x] **v0.18.x** — VibeX top-of-feed → TrendItem source (`$0` Supabase) · cross-agent SFOS sinks (reflections / skills / preference) · bandit + autopsy promoted to `solo-founder-os` core · LLM-mode variant_key tagging · trends 280-char overflow 3-layer fix · daily engagement → bandit launchd · weekly sfos-retro launchd · PyPI live (Trusted Publishing OIDC)
- [ ] **v0.19** — DSPy compilation against engagement history · MCP marketplace listing (post-PH) · cross-agent bandit data exchange
- [ ] **v1.0** — public OSS launch · YC application

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
│   ├── types.py                  Pydantic models — Project, Post, Platform, Engagement
│   ├── content/                  Generator (HYBRID = edge → Anthropic → template) + templates + images
│   ├── platforms/                9 adapters (X, Reddit, LinkedIn, Dev.to, Bluesky, Mastodon, Threads, 知乎, 小红书)
│   ├── llm/                      anthropic_compat shim · edge_provider (Cloudflare Workers AI)
│   ├── listeners/                Bluesky firehose (free real-time engagement)
│   ├── integrations/             VibeXForge event push
│   ├── orchestrator.py           High-level: project → posts → distribute
│   ├── supervisor.py             Drafter → Critic → Rewriter (Reflexion-lite)
│   ├── critic.py · ensemble_critic.py    Heuristic + LLM + multi-LLM majority vote
│   ├── reflexion_memory.py       Cross-session critic findings (+SFOS JSONL sink)
│   ├── preference.py             ICPL store (+SFOS JSONL mirror)
│   ├── skill_promoter.py         Voyager auto-skill (+SFOS shared dir mirror)
│   ├── bandit.py                 Thompson Beta-conjugate over X variants
│   ├── trends.py                 GitHub / HN / Reddit aggregator (stdlib HTTP)
│   ├── trends_to_drafts.py       Proactive loop: trends → multi-platform drafts
│   ├── trend_memory.py           Per-(project, URL) cooldown
│   ├── vibex_trends.py           Self-source from your platform's top-of-feed
│   ├── budget.py                 Daily LLM-spend soft cap
│   ├── autopsy.py                Engagement-vs-peers post-mortem
│   ├── multiproject.py           marketing-agent.yml + trends.yml parser
│   ├── memory.py · queue.py · threads.py · schedule.py    Core HITL plumbing
│   ├── cost.py · engagement.py · best_time.py             Analytics
│   ├── reply_suggester.py        Timeline scan → reply drafts → queue
│   ├── strategy.py               30/60/90-day LaunchPlan generator
│   ├── mcp_server.py             7-tool MCP server for Claude Code / Desktop
│   ├── web_ui.py                 Streamlit queue UI (`marketing-agent ui`)
│   ├── observability.py          Phoenix / OTel tracing (opt-in)
│   ├── dspy_signatures.py        4 typed Signatures, compile hook ready
│   └── cli.py                    argparse — 17 subcommands
├── examples/                     Offline demos (no API keys needed)
├── scripts/
│   ├── daily_post.py             Cron entry: commit-driven + trends drafts
│   ├── trend_perf_report.py      Compare trend-anchored vs commit-driven engagement
│   ├── reject_today_cron.sh      Bulk-reject pending drafts by date
│   ├── run_daily_engagement.sh   launchd: auto-pull X engagement + feed bandit
│   ├── run_ph_day_reminder.sh    launchd: PH-day manual-paste reminder
│   └── run_trend_perf_report.sh  launchd: weekly trend-perf retro
├── .github/workflows/            6 actions: daily / publish / scheduled / test / lint / mcp-install-check
├── docs/                         vibex-launch material · mcp-listing kit · future/saas-design
├── skills/marketing-voice/       Curated voice guide (loadable Claude Skill)
└── tests/                        408 tests passing, ~77% coverage, all offline
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

## Future / paid offering — *speculative*

A managed-SaaS layer on top of `marketing-agent` (running inside [VibeXForge](https://vibexforge.com)) is fully designed but **not yet built**. See [`docs/future/saas-design.md`](docs/future/saas-design.md) for the architecture, pricing, and the explicit demand-signal threshold that would trigger Phase-1 work.

Today's promise stays the same: the OSS tool here is the whole product, and it always will be free. The SaaS doc exists so an interested founder / investor / collaborator can understand the scaling story without me having to retell it.

The MCP-server side of distribution (Anthropic marketplace + `modelcontextprotocol/servers` registry) is shipping post-PH 2026-05-04 — see [`docs/mcp-listing/`](docs/mcp-listing/) for the kit.

---

## License

MIT — use it, fork it, ship it.

---

*Hand-built by Alex while waiting for his first 100 GitHub stars. Hopefully you don't need to wait that long.*
