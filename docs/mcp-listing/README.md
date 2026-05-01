# Marketing Agent — MCP Server Listing

**For:** Anthropic MCP marketplace + Claude Skills directory submission (post-PH 2026-05-04).

This folder is the listing kit. Submit by copying the relevant fields below into the marketplace form when it opens / after we get featured.

---

## Tagline (1 line, ≤80 chars)

> AI marketing agent for OSS founders — draft platform posts from your repo's commits.

## Short description (≤200 chars, for card UI)

> Tell Claude "draft today's posts for my repo" and get tweet-ready X / LinkedIn / Reddit / Bluesky drafts pulled from your latest commits, with a built-in HITL approval queue and engagement-aware variant bandit.

## Long description (≤2000 chars, for detail page)

> Marketing Agent turns a GitHub repo into platform-tuned launch copy. Point it at a repo + project name; it pulls recent commits via `gh api`, runs them through Claude with platform-specific voice guides, and produces drafts ready to ship across X, LinkedIn, Reddit, Dev.to, Bluesky, Mastodon, Threads, and Hacker News.
>
> What makes it different:
>
> - **HITL by default** — drafts land in `queue/pending/` as plain markdown files. You review (in your editor or Obsidian), `git mv` to `queue/approved/`, and a separate publish step actually posts. No surprise tweets.
> - **Critic + dedup gate** — every draft passes a heuristic + LLM critic and a hybrid (BM25 + dense) semantic dedup index before queuing. Hype words, near-duplicates, and bad CTAs auto-reject.
> - **Thompson-sampling bandit** — multiple stylistic variants per draft (emoji-led / question-led / stat-led for X). Bandit picks winners from real engagement.
> - **Reflexion supervisor** — past critic patterns are remembered cross-session and injected as "things to avoid" in future prompts. Cross-run learning.
> - **Trends-driven proactive loop** — daily cron also surfaces trending GitHub / HN / Reddit topics and drafts posts connecting your project's angle to what's hot. Per-(project, URL) dedup memory prevents writing about the same hot story 4 days in a row.
>
> Designed for indie OSS founders who already live in Claude Code / Claude Desktop. The MCP server exposes the same tools you'd hit from the CLI, so a one-sentence ask in Claude becomes a real workflow.

## Tools exposed (7)

| Tool | What it does |
|---|---|
| `draft_posts` | Generate per-platform drafts for a project (commits → posts). |
| `submit_to_queue` | Save a draft to `queue/pending/` for human review. |
| `list_queue` | List items in pending/approved/posted/rejected. |
| `engagement_top` | Show top-performing past posts by like / repost / reply. |
| `optimal_time` | Best hour-of-week to post per platform (CDF over engagement history). |
| `bandit_stats` | Per-variant Thompson posterior — which framings actually win? |
| `launch_plan` | Generate a 30/60/90-day launch plan with PH-relative timing. |

## Install

```bash
pip install "orallexa-marketing-agent[mcp]"
```

Add to Claude Desktop / Claude Code config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "marketing-agent": {
      "command": "marketing-agent-mcp"
    }
  }
}
```

Restart Claude. In any conversation:

> "Use the marketing-agent to draft today's X + LinkedIn posts for my repo `alex-jb/my-cool-project`."

…and Claude will invoke `draft_posts` directly.

## Optional config (env vars)

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Unlocks LLM-mode (vs deterministic templates) |
| `X_API_KEY` + 3 X keys | Real auto-publish (otherwise `submit_to_queue` is HITL-only) |
| `MARKETING_AGENT_DAILY_BUDGET_USD` | Soft cap on daily LLM spend |
| `NTFY_TOPIC` | Push notifications when drafts are ready |

## Use cases

- "Draft a LinkedIn announcement for v0.18 of my repo, focusing on the new memory module."
- "What's my best variant on X right now? Should I emoji-led or question-led?"
- "Make me a 30-day PH launch plan, anchor day = next Monday."
- "Show me my top-3 most-liked posts from the last quarter."

## Compatibility

| Client | Status |
|---|---|
| Claude Desktop | ✅ Verified |
| Claude Code | ✅ Verified |
| Cursor | ✅ Verified (MCP standard) |
| Zed | ✅ Verified (MCP standard) |

## Cost

- The MCP server itself is free + open source (MIT, GitHub)
- LLM calls flow through your own `ANTHROPIC_API_KEY` (no middle-tier markup)
- Optional Pollinations image generation is also free

## Repo + docs

- GitHub: https://github.com/alex-jb/orallexa-marketing-agent
- CHANGELOG: https://github.com/alex-jb/orallexa-marketing-agent/blob/main/CHANGELOG.md
- Bilingual READMEs: EN + 中文

## Submission checklist (post-PH)

- [ ] Verify `pip install "orallexa-marketing-agent[mcp]"` from a fresh venv on macOS
- [ ] Verify `pip install ...[mcp]` on a fresh venv on Linux (CI Ubuntu image)
- [ ] Capture 3 screenshots (Claude Desktop showing the tools menu, an end-to-end "draft → approve → post", a launch_plan output)
- [ ] Record a 60-second demo video (drafting + approving in 1 take)
- [ ] Submit at https://anthropic.com/mcp (when registry opens) AND list at https://github.com/modelcontextprotocol/servers
- [ ] Cross-post on X with the launch screenshot pinned for a week
