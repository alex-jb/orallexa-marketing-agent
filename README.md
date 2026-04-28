# Orallexa Marketing Agent

[![Version](https://img.shields.io/badge/version-0.3.0-blue.svg)](https://github.com/alex-jb/orallexa-marketing-agent/releases)
[![Tests](https://img.shields.io/badge/tests-49%20passing-brightgreen.svg)](#)
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

## Status — v0.3.0

What works today:

| Layer | Capability |
|---|---|
| **Content** | Claude (Sonnet 4.6 / Haiku 4.5) or template fallback · auto-thread split · image-prompt suggester |
| **Platforms** | X (real, OAuth 1.0a) · Reddit (PRAW) · Bluesky (AT Protocol) · Mastodon (REST) · Dev.to (markdown) · LinkedIn (dry-run) · 知乎/小红书 (Phase 3 — Playwright) |
| **Workflow** | HITL approval queue (markdown files, Obsidian-friendly) · SQLite dedup · cost tracker (Anthropic + X per-post) · daily cron via GitHub Actions |
| **Strategy** | LaunchPlan generator (template + LLM mode) writes 30-day playbook · reply-draft suggester (scan handles → filter → draft) |
| **Analytics** | EngagementTracker pulls X metrics, ranks top posts |
| **Integrations** | VibeXForge sister-product event push (auto-advances hero-card stages) |

CLI subcommands: `generate · post · queue · history · cost · plan · replies · engage`

Roadmap:
- [x] **v0.1** — scaffold, X / Reddit / LinkedIn stubs
- [x] **v0.2** — memory + threads + queue + cost + Bluesky + Mastodon + CLI
- [x] **v0.3** — reply suggester + engagement tracker + launch planner + 知乎/小红书 stubs + VibeXForge + image prompts
- [ ] **v0.4** — A/B variant generator · best-time-to-post analyzer · GitHub release → auto-post webhook · PyPI release
- [ ] **v0.5** — Critic agent (LangGraph) · semantic dedup (embeddings) · Streamlit queue UI
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

## Deploy as a daily cron (GitHub Actions)

Once your repo is on GitHub, the included `.github/workflows/daily.yml` runs `scripts/daily_post.py` every day at 14:00 UTC and posts to X automatically.

### One-time setup

1. **Push this repo** to GitHub:
   ```bash
   gh repo create orallexa-marketing-agent --public --source . --push
   ```

2. **Add secrets** in GitHub → repo → Settings → Secrets and variables → Actions:
   - `X_API_KEY`, `X_API_KEY_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`
   - `ANTHROPIC_API_KEY` (optional — falls back to template mode if absent)
   - `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME`, `REDDIT_PASSWORD`, `REDDIT_USER_AGENT` (optional)

3. **Manual test run**: Actions tab → "Daily auto-post" → "Run workflow" → tick `dry_run=true` first.

### What gets posted

The workflow targets `alex-jb/orallexa-ai-trading-agent` by default. Edit the cron payload in `daily.yml` or add new repos to `REPO_PRESETS` in `scripts/daily_post.py` to expand coverage. Template mode produces deterministic content from commit messages; LLM mode (Claude) produces sharper, platform-tuned posts.

### Skipping rules

The script skips posting when:
- No commits in the lookback window (default 24 h)
- All commits are CI-only / docs-only / chore-only

Override with `--force` (for testing only).

---

## License

MIT — use it, fork it, ship it.

---

*Hand-built by Alex while waiting for his first 100 GitHub stars. Hopefully you don't need to wait that long.*
