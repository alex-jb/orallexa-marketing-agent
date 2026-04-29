# Changelog

All notable changes to this project. Format roughly follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.9.0] — 2026-04-30

**Hardening sprint — no new features, all reviews + tests + cleanups.**

### Tests + coverage
- New `tests/test_reply_suggester.py` — 14 tests, brings module from 0% → 81% coverage
- New `tests/test_image_upload.py` — 6 tests for X / Bluesky / Mastodon image upload paths (mocked)
- `tests/test_mcp_server.py` — added 8 integration tests against extracted tool functions
- Coverage 63% → 70%; CI floor raised from 60% → 70%

### Code-level cleanups
- **Critic min-score is now a single shared constant** (`marketing_agent.critic.DEFAULT_MIN_SCORE`); both `critique()` and `queue.submit()` reference it. Override one place and the other follows.
- **BM25 single-doc edge case fixed**: `_normalize_bm25([single_score])` now returns `[0.5]` (neutral midpoint) instead of `[1.0]`. Avoids over-confident dedup flagging when the corpus has only one document.
- **MCP server tools refactored** — extracted from inside `main()` to module-level `tool_*` functions. Same `mcp.tool()` registration in `main()`, but now unit-testable without a `fastmcp` install.

### Image upload extended
- **Bluesky adapter** now uploads `Post.image_url` via `com.atproto.repo.uploadBlob`, attaches via `record.embed.images`. 1MB blob cap respected.
- **Mastodon adapter** now uploads via `/api/v2/media`, attaches via `media_ids[]`. 8MB cap.
- X adapter (already in v0.7) — unchanged but now mock-tested.

## [0.8.0] — 2026-04-30

### Added
- `marketing_agent.observability` — opt-in OpenTelemetry / Phoenix tracing. Auto-instruments Anthropic SDK via `openinference` when present. `init_tracing()`, `span()`, `@traced` no-op when extras missing.
- `marketing_agent.dspy_signatures` — 4 typed DSPy `Signature`s (`DraftPost`, `CritiquePost`, `RewritePost`, `GenerateLaunchPlan`). `compile_if_keyed()` is a v0.9 stub for future engagement-history compilation.
- PyPI build artifact: `python -m build` produces wheel + sdist; `py.typed` marker included; both pass `twine check`.
- `.github/workflows/publish-pypi.yml` — auto-builds on every `v*.*.*` tag; uploads iff `PYPI_API_TOKEN` secret is set.
- New extras: `[observability]`, `[dspy]`. `[dev]` now includes `build` + `twine`.

## [0.7.0] — 2026-04-30

### Added
- `marketing_agent.content.images.generate_image()` — real cover image URL via Pollinations.ai (Flux schnell), free, no key, no rate limit. Per-platform dimensions.
- `Post.image_url` field — X adapter downloads + uploads via `media/upload.json` before tweet. Graceful fallback to text-only on upload failure.
- New `image` CLI subcommand (11 total now).
- VibeXForge PH-day banner generated and attached to launch X thread.

## [0.6.0] — 2026-04-29

### Added — agentic core
- `marketing_agent.supervisor` — Drafter → Critic → Rewriter loop (Reflexion-lite, no LangGraph dep). `heuristic_rewrite()` strips hype, de-shouts caps, caps hashtags, trims overshoot.
- `marketing_agent.reflexion_memory` — persistent SQLite log of critic findings. Next generation prepends recent low-score patterns as steering hint.
- `marketing_agent.multiproject` + `marketing-agent.yml` — multi-project YAML config. `daily.yml` cron iterates enabled projects.
- Hybrid retrieval in `semantic_dedup.py` — 60% dense + 40% BM25 (+17pp MRR per Q1 2026 retrieval bench). Pure-Python BM25 inline.
- Prompt caching markers in `content/generator.py` — system prompts marked `cache_control={"type":"ephemeral"}` for 1h TTL (no-op without key, ~80% input-token savings when keyed).
- Claude Agent SDK 0.1.68 adapter in `supervisor.py` — uses official SDK when installed (`[agent_sdk]` extra), falls back to local loop.
- `skills/marketing-voice/SKILL.md` — Claude Skills package (loadable via `skills="all"`).
- `agent_card.json` — Google A2A v1.2 discovery card.
- Multi-stage `Dockerfile` + `docker-compose.yml` (~150MB final image, non-root, JSON logs default).

## [0.5.0] — 2026-04-29

### Added — production hardening
- `marketing_agent.critic` — heuristic + LLM critic with auto-reject. Penalizes hype words, char overshoots, all-caps shouting, hashtag spam.
- `marketing_agent.semantic_dedup` — sentence-transformers MiniLM (CPU, free) + Voyage-3 backend. Catches paraphrased reposts.
- `marketing_agent.retry` — exponential backoff + jitter decorator on all platform adapters. Retries on `ConnectionError`, `Timeout`, 429, 5xx.
- `marketing_agent.logging` — structured JSON logs (Langfuse / Datadog / OTel compatible). Opt-in via `MARKETING_AGENT_LOG=json`.
- `queue.submit()` gate — auto-rejects bad drafts to `queue/rejected/` with reason logged.
- `.github/workflows/test.yml` — Python 3.11/3.12 matrix, pytest-cov 60%+ floor (later 70%).
- `.github/workflows/release-announce.yml` — fires on GitHub Release, drafts thread to `queue/pending/`, opens review issue.

## [0.4.0] — 2026-04-29

### Added
- `marketing_agent.bandit` — Thompson sampling over post stylistic variants. Beta(α, β) per arm.
- `marketing_agent.best_time` — hour-of-week empirical CDF. Falls back to industry defaults under sample threshold.
- `marketing_agent.mcp_server` — FastMCP server (`marketing-agent-mcp` script). 7 tools.
- 60/90-day launch plans + Product-Hunt-relative timing in `strategy.py`. HN action shifts relative to PH-day.
- New CLI subcommands: `bandit`, `best-time`. Total 10.
- Extras: `[mcp]`.

## [0.3.0] — 2026-04-28

### Added
- `marketing_agent.engagement` — `EngagementTracker` pulls X public_metrics, ranks top posts.
- `marketing_agent.reply_suggester` — scan handles → filter relevant tweets → draft replies → approval queue.
- `marketing_agent.strategy` — `LaunchPlan` Pydantic + `default_plan()` + `llm_plan()` + `write_plan()`.
- 知乎 / 小红书 platform adapters (dry-run only; Phase 3 = Playwright).
- `marketing_agent.integrations.vibexforge` — sister-product event push.
- `marketing_agent.content.images` — Midjourney/DALL-E prompt suggester.

## [0.2.0] — 2026-04-28

### Added
- `marketing_agent.memory` — SQLite content-hash dedup.
- `marketing_agent.threads` — auto-split long content; URL only on first chunk.
- `marketing_agent.queue` — markdown-file approval queue (Obsidian-friendly).
- `marketing_agent.cost` — per-call Anthropic + per-X-post cost tracking.
- Bluesky + Mastodon adapters.
- Full argparse CLI (`generate / post / queue / history / cost`).
- Daily cron via GitHub Actions (`scripts/daily_post.py`).

## [0.1.0] — 2026-04-28

### Added
- Initial scaffold. Pydantic types (`Project`, `Post`, `Platform`, `Engagement`).
- X (real, OAuth 1.0a), Reddit (PRAW stub), LinkedIn (dry-run) adapters.
- Template + Claude content generator with HYBRID fallback.
- `Orchestrator` — high-level `project → posts → distribute`.

[0.9.0]: https://github.com/alex-jb/orallexa-marketing-agent/releases/tag/v0.9.0
[0.8.0]: https://github.com/alex-jb/orallexa-marketing-agent/releases/tag/v0.8.0
[0.7.0]: https://github.com/alex-jb/orallexa-marketing-agent/releases/tag/v0.7.0
[0.6.0]: https://github.com/alex-jb/orallexa-marketing-agent/releases/tag/v0.6.0
[0.5.0]: https://github.com/alex-jb/orallexa-marketing-agent/releases/tag/v0.5.0
[0.4.0]: https://github.com/alex-jb/orallexa-marketing-agent/releases/tag/v0.4.0
[0.3.0]: https://github.com/alex-jb/orallexa-marketing-agent/releases/tag/v0.3.0
