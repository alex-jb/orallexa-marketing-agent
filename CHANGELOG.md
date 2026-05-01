# Changelog

All notable changes to this project. Format roughly follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.18.0] — 2026-04-30

**VibeX top-of-feed → TrendItem source: the agent now self-sources from your own platform.**

### Added
- `marketing_agent.vibex_trends.trending_vibex_projects()` — pulls top recent VibeXForge projects from Supabase (last 24-72h, ranked by evolution stage Myth → Seed) and emits them as `TrendItem` entries with `source="vibex"`. Same shape as GitHub/HN/Reddit trending → lands naturally in the existing `trends_to_drafts` proactive loop.
- Pure SQL through Supabase Management API. **$0 API cost.** No third-party SDK; stdlib `urllib` only.
- Auth: `SUPABASE_PERSONAL_ACCESS_TOKEN` + `VIBEX_PROJECT_REF` (or fall back to `SUPABASE_PROJECT_REF` for the common one-project case).
- 6 new tests covering happy path, missing creds short-circuit, network failure, evolution-stage ordering.

### Why this matters
The most authentic "what's interesting in AI today" content for *your* audience comes from your own users. A project hitting Breakout/Legend/Myth on VibeXForge in the last 24h is the exact signal worth amplifying. Beats generic GitHub trending for relevance, beats Reddit scraping for signal-to-noise.

### Changed
- `scripts/trend_perf_report.py` — ruff cleanup (12 empty f-strings).

### Tests
- 365 → **371 tests** (+6)
- Coverage steady at 77%

## [0.17.2] — 2026-04-30

**Three foot-guns the proactive loop kept stepping on, fixed in one release.**

### Added — A. Trend-URL dedup memory (`marketing_agent.trend_memory`)
The post-content semantic-dedup gate inside `ApprovalQueue.submit` only catches near-duplicate WRITING. It cannot see that the same hot HN story (or top GitHub repo of the week) is being drafted about for the 4th day in a row. v0.17.2 closes this hole.

- New `TrendMemory` class — SQLite table `drafted_trends (url, project_name, drafted_at)`, stored alongside the existing post-history DB. Key methods: `was_drafted_recently(url, project, days=7)`, `filter_fresh(items, project)`, `mark_drafted()`, `purge_older_than(days=90)`.
- `trends_to_drafts()` now takes `dedup_days` (default 7) and `memory` overrides. Stale trends are filtered BEFORE the LLM is called — zero token cost on a re-seen URL.
- After at least one platform's draft makes it into `pending/`, the trend URL is marked. If every platform's generation fails for that trend, the URL stays *unmarked* so retry tomorrow is still possible.
- 11 new tests covering core memory + filter + mark-on-success-only behavior.

### Added — C. Soft daily LLM-spend cap (`marketing_agent.budget`)
`top_n=3 × 3 projects × M platforms` is fine. `top_n=20 × 3 projects × 8 platforms` is not. Without a guard, a misconfigured run would happily burn through budget with no notice.

- New `budget.daily_spend_usd()` — reads `~/.marketing-agent/usage.jsonl` (the cross-provider log written by every Anthropic / Cloudflare-edge / LiteLLM call), prices each row using `cost.PRICES`, sums today (UTC) only. Robust to corrupt lines and missing files (returns 0.0, never raises).
- `is_over_budget()` + `configured_cap_usd()` — opt-in via env var `MARKETING_AGENT_DAILY_BUDGET_USD`. Unset → unlimited (no behavior change for current users).
- `_run_trends_for_projects` checks the cap before the proactive pass starts AND between projects mid-loop, so any partial work already queued is preserved.
- Conservative pricing: unknown models priced as Sonnet (over-estimate spend = under-shoot the cap = safer).
- 15 new tests.

### Changed — B. Daily issue body breakdown
The GitHub issue created at end of cron used to say only "📥 N drafts ready". Now it splits commit-driven vs trend-anchored counts and inlines the trend titles per project so review can be triaged at a glance.

- `daily_post.py` now emits `commit_count` and `trends_count` as separate `GITHUB_OUTPUT` rows (the existing `queued_count` is preserved for back-compat).
- New helper `_write_trends_summary()` writes `queue/_today_trends_summary.md` with a per-project bulleted list of (source, title, URL) — committed with the rest of `queue/` and inlined into the issue body via the workflow.
- `daily.yml` issue body template updated to show the breakdown + `cat` the summary file.

### Tests / hygiene
- New `tests/conftest.py` autouse fixture — every test now writes to a per-test tmp dir for `MARKETING_AGENT_DB_PATH`, `MARKETING_AGENT_QUEUE`, and `cost.USAGE_LOG_PATH`. Fixes a latent leak where `TrendMemory` and `PostMemory` defaults could touch the developer's real `~/.marketing_agent/`.
- 331 → **365 tests** (+34: 11 trend_memory + 15 budget + 4 trends_to_drafts dedup + 1 budget integration + 2 issue body summary + minor)

## [0.17.1] — 2026-04-30

**Wire trends → drafts into the daily cron — proactive loop is now end-to-end on autopilot.**

### Added
- New top-level `trends:` block in `marketing-agent.yml` — opt-in (default off). Schema:
  ```yaml
  trends:
    enabled: true
    languages: [python]
    hn_query: agent
    subreddits: [MachineLearning, LocalLLaMA, IndieHackers]
    top_n: 3
    hours: 168
  ```
- `marketing_agent.multiproject.TrendsConfig` dataclass + `load_trends_config()` parser. The minimal-YAML loader now exposes a shared `_load_raw()` so both project list and trends block read from the same parse pass.
- New `--trends-too` flag on `scripts/daily_post.py`. When set (and the config has `trends.enabled: true`), after the per-project commit loop it runs a second proactive pass: aggregate trends ONCE, then for each enabled project fan out per-platform drafts that connect the project's angle to each top trend. Per-project granularity is preserved — `subreddit` config carries through to the Reddit adapter.
- `.github/workflows/daily.yml` now passes `--trends-too` automatically — no further setup needed beyond flipping `trends.enabled: true` in `marketing-agent.yml`.
- Real default trends config in this repo's `marketing-agent.yml` (enabled=true, langs=python, HN query=agent, 3 subreddits, top_n=3, 1-week window) — the agent is now self-hosting its own proactive loop.
- 9 new tests: `TrendsConfig` defaults / disabled / explicit-block parsing, project list robust under added trends block, `_run_trends_for_projects` fan-out math, empty-items short-circuit, subreddit_target pass-through, single-aggregate-call invariant for N projects.

### Why this matters
v0.17.0 added the `trends_to_drafts` plumbing but it was hand-invoked. v0.17.1 wires it into the daily cron, so the morning queue review now contains BOTH commit-driven drafts AND trend-anchored drafts — without anyone having to remember to run the trends command.

### Tests
- 322 → **331 tests** (+9)
- Coverage steady at 77%

## [0.17.0] — 2026-04-30

**Trends → drafts: closing the proactive loop.**

v0.15 added `trends.py` (scan GitHub / HN / Reddit → markdown digest). That was reactive — the human still had to open the digest and decide what to write. v0.17 closes the loop: the agent now turns top trends into platform-specific drafts and pushes them into the approval queue automatically.

### Added
- `marketing_agent.trends_to_drafts` module (`trends_to_drafts(...)` + `DraftResult`). Pipeline:
  1. Aggregate trends across configured GitHub languages / HN query / subreddits (or accept pre-built `items=`).
  2. Take top N by score.
  3. For each trend, build a synthetic `Project` whose `recent_changes[0]` is a "Trending now (source): title — summary [url]" hook and whose `description` carries an explicit framing instruction telling the LLM to connect the project's angle to the trend (without claiming the trend as the project's own).
  4. Fan out across requested platforms via the existing `content/generator.generate_posts` pipeline — reuses ICPL preference few-shots, Cloudflare edge tier, prompt caching, per-platform voice guides, cross-provider usage logging, and the critic + semantic-dedup gate inside `ApprovalQueue.submit()`.
  5. Drafts land in `pending/` with `generated_by: trends`.
- New CLI: `marketing-agent trends-to-drafts --name <p> --tagline <t> --languages python --hn-query agent --subreddits MachineLearning --platforms x linkedin --top-n 5`.
- 12 new tests covering: synthetic-project shape (hook position, framing instruction, missing-description fallback, URL inclusion), happy path (3 trends × 2 platforms = 6 drafts), `generated_by=trends` marker, `top_n` clamping, empty-trends short-circuit, aggregator argument forwarding, per-trend failure isolation, subreddit_target pass-through.
- Per-trend generator failure no longer aborts the whole batch — failed trends just produce empty `queued_paths` and the loop continues.

### Why this matters
v0.15 was a one-way street (digest → human eyes → maybe a draft). The loop is now end-to-end: cron → trends.aggregate → top N → multi-platform drafts → human approval → publish. On a daily run with `--top-n 5 --platforms x linkedin`, that's 10 trend-anchored drafts in your inbox each morning — alongside the commit-driven drafts — without you ever opening the digest.

### Tests
- 310 → **322 tests** (+12)
- Coverage steady at 77%

## [0.16.0] — 2026-04-30

**Threads (Meta) auto-publish — first-mover window vs indie-OSS competitors.**

### Added
- `marketing_agent.platforms.threads` — Threads (Meta Graph API) auto-publish adapter. Production API as of April 2026, 250 posts/24h/user. Two-step Meta-style flow: `/v1.0/{user-id}/threads` (create container) → `/v1.0/{user-id}/threads_publish`. Image upload via `image_url` parameter (reuses Pollinations URLs from v0.7).
- New env vars in `.env.example`: `THREADS_ACCESS_TOKEN`, `THREADS_USER_ID`.
- `publish.yml` and `scheduled.yml` workflows now forward THREADS secrets.
- 10 tests covering happy path (text-only + image), missing creds, char-limit overshoot, malformed Meta responses.

### Why now
Per April 2026 landscape research (4th deep-research dispatch this session): Threads API graduated to GA in April with 300M MAU. None of the existing indie-OSS marketing competitors (Postiz / Buffer / Hypefury) have native Threads integration. First-mover window.

### Changed
- `[agent_sdk]` extras bumped from `claude-agent-sdk>=0.1.68` to `>=0.1.71` (April 28-29 releases add `SessionStore` adapter protocol, `skills=[...]` option, in-process MCP fix, `SandboxNetworkConfig` domain allow/deny).

### Tests
- 300 → **310 tests** (+10)
- Coverage 77% (steady)

## [0.15.0] — 2026-04-30

**Reactive → proactive: trends module for content ideation.**

The agent has been *reactive* — given a project + commits, generate posts. v0.15 adds the proactive complement: scan what's trending in your niche right now so you can write fresh angles, not just rehash recent commits.

### Added
- `marketing_agent.trends` module with three free public sources (no API keys, stdlib HTTP only):
  - `trending_github_repos(language, since)` — scrapes `github.com/trending` HTML, returns repos with stars + descriptions.
  - `trending_hn_posts(query, hours, min_points)` — Hacker News Algolia API (`hn.algolia.com/api/v1/search`).
  - `trending_subreddit_posts(subreddit, hours, min_score)` — Reddit's public `/.json` (no auth needed for read).
- `aggregate(...)` — one call across all three, dedupes by URL, sorts by score.
- `render_markdown(items)` — Markdown digest grouped by source with emoji headers + per-item stats.
- New CLI: `marketing-agent trends --languages python --hn-query agent --subreddits MachineLearning IndieHackers --hours 168 --out trends.md`
- 12 new tests verify each scraper's parsing + graceful network-failure fallback + aggregator dedup + markdown rendering.

### Why this matters
Closes the loop: agent now suggests **what** to post about, not just **how**. Especially valuable for the manually-published 中文 platforms (知乎 / 小红书) where you want to write about topics actually getting traction this week.

### Tests
- 287 → **300 tests** (+13)
- Coverage 76% → **77%**

## [0.14.0] — 2026-04-30

**Cross-provider usage logging — cost-audit-agent now sees 100% of LLM spend.**

### Added
- `marketing_agent.llm.anthropic_compat.log_usage` — re-exports the real `solo_founder_os.anthropic_client.log_usage` when installed, otherwise provides a hand-rolled twin with the identical JSONL schema (`{ts, model, input_tokens, output_tokens, **extra}`).
- **Cloudflare Workers AI calls now log** to `USAGE_LOG_PATH` with `provider=cloudflare-workers-ai` tag. Previously bypassed the audit.
- **LiteLLM ensemble critic calls now log** with `provider=litellm-ensemble` tag — captures GPT-5 + Gemini spend alongside Anthropic.
- 5 new tests verify the schema + per-provider tagging + that failures don't break callers.

### Why this matters
v0.13 brought Anthropic spend into the cross-agent audit pipeline. v0.14 closes the remaining holes: every paid LLM call from marketing-agent — Anthropic via solo-founder-os, Cloudflare via direct edge_provider, GPT-5/Gemini via LiteLLM — now lands in the same JSONL feed that `cost-audit-agent` reads for the monthly cross-agent cost report.

### Tests
- 282 → **287 tests** (+5)
- Coverage steady at 76%

## [0.13.0] — 2026-04-30

**Joining the Solo Founder OS shared base.**

### Added
- Hard dependency on `solo-founder-os>=0.1.0` — the shared agent stack base, same package now used by `build-quality-agent` v0.4 and `customer-discovery-agent` v0.2.
- `marketing_agent.cost.USAGE_LOG_PATH` — every Anthropic call writes token usage to `~/.marketing-agent/usage.jsonl`. `cost-audit-agent` reads from there for the cross-agent monthly cost report.
- Honest 知乎 / 小红书 content-prep adapters (locked in v0.12.1 commit, formalized here): `dry_run_preview` outputs include AI-disclosure reminders, hook templates, length classifiers, and platform-rule checklists per Q2 2026 anti-bot research.

### Changed
- **All 6 LLM call sites migrated** from `from anthropic import Anthropic` to `from solo_founder_os.anthropic_client import AnthropicClient`:
  - `content/generator.py` (Tier-2 Claude Sonnet draft path)
  - `content/images.py` (Midjourney/DALL-E prompt suggester via Haiku)
  - `critic.py` (LLM critic via Haiku)
  - `strategy.py` (LaunchPlan generator via Haiku)
  - `reply_suggester.py` (reply drafter via Sonnet)
  - `supervisor.py` (Drafter loop LLM mode via Sonnet)
- All migrated calls return `(resp, err)` tuples; graceful template/heuristic fallback on `err is not None` or `client.configured == False`.
- Hardcoded model strings replaced with `DEFAULT_HAIKU_MODEL` / `DEFAULT_SONNET_MODEL` constants.

### Tests
- Updated `tests/test_reply_suggester.py::test_llm_reply_calls_anthropic_when_keyed` to mock `solo_founder_os.anthropic_client.AnthropicClient` instead of `anthropic.Anthropic`.
- All **274 tests pass**.

## [0.12.0] — 2026-04-30

**Cost lever + analytics surface + agent-self-improvement.**

### Added
- `marketing_agent.llm.edge_provider` — **Cloudflare Workers AI Llama 3.3** as a cheap first-draft tier. When `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID` are set, `_generate_with_llm` routes there before falling back to Claude. ~$0.011/1M tokens vs Claude Sonnet ~$3/1M = ~80% cost reduction on the daily-cron drafter path. Critic + rewriter still hit Claude when keyed. 10 tests.
- `marketing_agent.skill_promoter` — **Voyager-style auto-skill promotion**. When a post lands top-quartile by engagement, extract its structural fingerprint (opening pattern, length, hashtag count, etc.) into `skills/learned/<slug>.md`. Heuristic-only — no LLM call needed. New CLI `marketing-agent skills promote`. 16 tests.
- `marketing_agent.bandit.report()` — **per-platform A/B winner** with 95% Beta credible intervals. New CLI `marketing-agent bandit report`. Surfaces which X variant style ("emoji-led" / "question-led" / "stat-led") is actually winning over the last N pulls. 6 tests.
- `marketing_agent.autopsy` — **failure post-mortem analyzer**. `marketing-agent autopsy --post-id X` compares one post against platform median, runs heuristic critic on its body, checks posting hour vs. best-time CDF, flags short-body issues. Markdown output. 9 tests.

### Tests + coverage
- 228 → **269 tests** (+41)
- Coverage 75% → **76%**

## [0.11.0] — 2026-04-30

**Frontier upgrades surfaced by Q1-Q2 2026 SOTA research.**

### Added
- `marketing_agent.preference` — **In-Context Preference Learning (ICPL)** from human edits. SQLite `edits` table logs `(original_body, edited_body, edit_ratio)` whenever the human saves a body change in the Streamlit UI. The LLM generator pulls last 5 high-ratio edits as few-shot exemplars. No fine-tuning. Per Q1 2026 ICPL paper: cheaper than DPO/LoRA below ~500 pairs. 12 tests.
- `marketing_agent.ensemble_critic` — **Multi-LLM ensemble critic** via LiteLLM. Optional fanout to Claude + GPT-5 + Gemini; majority-vote on `auto_reject`, harshest score wins. Catches model-specific blind spots. Graceful fallback ladder (3 → 2 → 1 → heuristic). 8 tests.
- `marketing_agent.supervisor` — **Self-consistency-3** for short-form platforms (X / Bluesky / Mastodon). Off by default; opt-in via `use_self_consistency=True`. Per Q1 2026 paper: ~80% of Tree-of-Thoughts lift at 25% the cost on short content.
- `marketing_agent.listeners.bluesky_firehose` — **Free real-time engagement stream** via AT Protocol's public WebSocket firehose. Records likes / reposts / replies into `EngagementTracker` as they happen. Replaces the (unaffordable, $42k/yr) X Account Activity API. New script `marketing-agent-firehose-bsky`. 8 tests.

### Optional dependencies
- `[ensemble]` — `litellm>=1.55` for multi-LLM critic fanout
- `[firehose]` — `atproto>=0.0.55` for Bluesky firehose

### Tests + coverage
- 198 → **228 tests** (+30)
- Coverage 76% → **75%** (slight regression as new modules' optional-dep paths can't run in CI without the optional packages installed)

## [0.10.0] — 2026-04-30

**UX + scheduling — make the queue phone-friendly and time-aware.**

### Added
- `marketing_agent.web_ui` — Streamlit queue UI. Browse pending/approved/posted/rejected, edit body inline, click approve/reject. Image preview when `attach_image_url` or `image_url` is set in frontmatter. Run via `marketing-agent ui` (port 8501) or `marketing-agent-ui` script. Optional dep `[ui] = streamlit>=1.40`.
- `marketing_agent.schedule` — `scheduled_for` ISO datetime in queue file frontmatter. `is_due()` / `filter_due()` partition approved items. `marketing_agent post` now skips items whose `scheduled_for` is still in the future, prints a "waiting" list. `next_occurrence_of_hour()` + `schedule_via_best_time()` auto-pick the next instance of the optimal hour-of-week from the engagement CDF.
- New CLI subcommands: `ui` (open browser), `schedule` (set `scheduled_for` either via `--at <iso>` or `--best-time --platform x`).
- `.github/workflows/scheduled.yml` — hourly cron that publishes any approved items past their `scheduled_for`. Runs at HH:05 UTC.
- New extras: `[ui]`. New script entry point: `marketing-agent-ui`.

### Tests + coverage
- `tests/test_web_ui.py` — 5 smoke tests (module imports, env override, graceful no-streamlit exit).
- `tests/test_schedule.py` — 16 tests: ISO parsing (Z-suffix / offset / naive), set/get/replace `scheduled_for`, `is_due`/`filter_due`, `next_occurrence_of_hour`, `schedule_via_best_time` fallback to industry default.
- `tests/test_cli.py` — 17 CLI smoke tests covering generate/queue/plan/best-time/bandit/image/schedule/ui paths. `cli.py` coverage 0% → covered.
- **Total: 198 tests passing (was 160). Coverage 70% → 76%.**

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

[0.16.0]: https://github.com/alex-jb/orallexa-marketing-agent/releases/tag/v0.16.0
[0.15.0]: https://github.com/alex-jb/orallexa-marketing-agent/releases/tag/v0.15.0
[0.14.0]: https://github.com/alex-jb/orallexa-marketing-agent/releases/tag/v0.14.0
[0.13.0]: https://github.com/alex-jb/orallexa-marketing-agent/releases/tag/v0.13.0
[0.12.0]: https://github.com/alex-jb/orallexa-marketing-agent/releases/tag/v0.12.0
[0.11.0]: https://github.com/alex-jb/orallexa-marketing-agent/releases/tag/v0.11.0
[0.10.0]: https://github.com/alex-jb/orallexa-marketing-agent/releases/tag/v0.10.0
[0.9.0]: https://github.com/alex-jb/orallexa-marketing-agent/releases/tag/v0.9.0
[0.8.0]: https://github.com/alex-jb/orallexa-marketing-agent/releases/tag/v0.8.0
[0.7.0]: https://github.com/alex-jb/orallexa-marketing-agent/releases/tag/v0.7.0
[0.6.0]: https://github.com/alex-jb/orallexa-marketing-agent/releases/tag/v0.6.0
[0.5.0]: https://github.com/alex-jb/orallexa-marketing-agent/releases/tag/v0.5.0
[0.4.0]: https://github.com/alex-jb/orallexa-marketing-agent/releases/tag/v0.4.0
[0.3.0]: https://github.com/alex-jb/orallexa-marketing-agent/releases/tag/v0.3.0
