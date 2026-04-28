# Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                       Project (Pydantic)                      │
│  name · tagline · description · github_url · recent_changes  │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                       Orchestrator                            │
│   .generate(project, platforms) → list[Post]                  │
│   .preview(post) → str                                        │
│   .post(post) → url                                           │
└──────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼                               ▼
   ┌──────────────────┐            ┌──────────────────────┐
   │ Content layer    │            │ Platform adapters    │
   │  generator.py    │            │   x.py · reddit.py   │
   │  (Claude or      │            │   linkedin.py · ...  │
   │   templates)     │            │                      │
   └──────────────────┘            └──────────────────────┘
              │                               │
              ▼                               ▼
       Post objects                    External APIs
                                              │
                                              ▼
                                     Engagement events
                                     (feedback loop)
```

## Three modes of operation

| Mode | What it needs | What it does |
|------|---------------|--------------|
| **TEMPLATE** | Nothing | Deterministic templates, predictable output, no LLM cost |
| **LLM** | `ANTHROPIC_API_KEY` | Claude generates platform-specific content. Fails fast if key missing. |
| **HYBRID** (default) | Optional Claude key | Tries Claude; falls back to templates on any failure |

`make demo` always works — no keys, no network, just templates.

## Platform adapter contract

Every platform adapter implements the `PlatformAdapter` Protocol:
- `is_configured()` — does it have what it needs to actually post?
- `dry_run_preview(post)` — render what would be posted, no side effects
- `post(post)` — actually post; raises `NotConfigured` if creds missing

Adding a new platform = create one file in `marketing_agent/platforms/`.

## Why not auto-cross-post the same content everywhere?

Because that's how you get banned. Each platform has its own voice:
- X is short and uses short-form attention hooks
- Reddit is community-first and rewards long-form value
- LinkedIn is professional with longer paragraphs
- DEV.to is technical and code-friendly

The Content layer generates platform-specific output by default. The
Reddit adapter additionally requires per-subreddit tuning to avoid spam.

## What's NOT in v0.1

- Reply suggester (Phase 2)
- Strategy Agent (decides cadence and angle) (Phase 3)
- Engagement feedback loop (Phase 3)
- Chinese platforms (知乎, 小红书) via browser automation (Phase 2)
- Stripe + paid tiers (Phase 4)
- VibeXForge integration (Phase 5)

See `marketing-agent-plan/ROADMAP.md` for the phased plan.
