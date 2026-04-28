# Orallexa Marketing Agent

> **Submit your AI/OSS project once. Get auto-generated, platform-specific marketing content. Distribute everywhere.**

An open-source Python SDK for solo OSS founders who write code well but don't have time (or audience) to do marketing themselves.

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

## Status

**v0.1 (Phase 1)** — basic SDK, three platforms (X working, Reddit stub, LinkedIn stub), template fallback when no LLM key set. Not on PyPI yet.

Roadmap (from `marketing-agent-plan/ROADMAP.md`):
- [x] Phase 1 scaffold
- [ ] Phase 2 (weeks 3-4): reply suggester, Chinese platforms (知乎/小红书 semi-auto)
- [ ] Phase 3 (weeks 5-6): generic SDK + real-world examples
- [ ] Phase 4 (weeks 7-8): open-source launch
- [ ] Phase 5+: VibeXForge integration, Stripe, paid tiers, YC apply

---

## Layout

```
orallexa-marketing-agent/
├── marketing_agent/
│   ├── types.py             Pydantic models for Project, Post, Platform, Engagement
│   ├── content/             Content generation (Claude or template fallback)
│   ├── platforms/           Platform adapters: X (real), Reddit (stub), LinkedIn (stub)
│   └── orchestrator.py      High-level: project → posts → distribute
├── examples/
│   ├── orallexa_demo.py     Use Orallexa as the test project
│   └── generic_demo.py      Submit a fake project, see what gets generated
├── tests/                   Smoke tests, all offline
└── docs/architecture.md     1-page system diagram
```

---

## Design principles

1. **Tri-mode operation** — works with no keys (template fallback), with Claude key (LLM generation), with platform keys (real posting). Never crash for missing keys.
2. **Pydantic everywhere** — no untyped dicts crossing module boundaries.
3. **Adapters are protocols** — same interface for every platform, easy to extend.
4. **Reasonable defaults** — `make demo` works offline, no setup.
5. **No secrets in code** — `os.getenv` exclusively, `.env.example` as template.

---

## License

MIT — use it, fork it, ship it.

---

*Hand-built by Alex while waiting for his first 100 GitHub stars. Hopefully you don't need to wait that long.*
