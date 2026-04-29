# Orallexa Marketing Agent

[![Version](https://img.shields.io/badge/version-0.6.0-blue.svg)](https://github.com/alex-jb/orallexa-marketing-agent/releases)
[![Tests](https://img.shields.io/badge/tests-116%20passing-brightgreen.svg)](#)
[![CI](https://github.com/alex-jb/orallexa-marketing-agent/actions/workflows/test.yml/badge.svg)](https://github.com/alex-jb/orallexa-marketing-agent/actions/workflows/test.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](#)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](#)
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
| **Platforms** | X (real, OAuth 1.0a) · Reddit (PRAW) · Bluesky (AT Protocol) · Mastodon (REST) · Dev.to (markdown) · LinkedIn (dry-run) · 知乎/小红书 (Phase 3) |
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
- [ ] **v0.7** — Phoenix/OTel observability · Imagen 4 / Nano Banana 2 image gen · DSPy prompt compilation · PyPI release
- [ ] **v1.0** — open-source launch · YC application

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
