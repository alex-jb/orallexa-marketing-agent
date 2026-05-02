# dev.to article — orallexa-marketing-agent

**Where to submit:** https://dev.to/new

## Cover image

Use the Pollinations URL the agent already generates, or any 1000×420 banner. dev.to auto-fits.

## Tags (max 4)

```
ai, opensource, python, mcp
```

(`mcp` may not be a recognized tag yet — fall back to `claude` or `agents` if dev.to rejects it.)

## Canonical URL

```
https://github.com/alex-jb/orallexa-marketing-agent
```

## Series

Don't start a series; one-shot post.

---

## Title (60 chars max — current: 58)

```
I built an MCP server that markets my OSS repo from git log
```

Alternates:
- `Why my AI marketing agent uses a Thompson-sampling bandit` (technical-curiosity angle, 56 chars)
- `9 platforms, 1 git push: how I auto-market my OSS projects` (concrete-promise angle, 58 chars)
- `An open-source agent that drafts your launch posts from commits` (problem-led, 60 chars)

**Recommended:** the first one — most click-worthy on the dev.to homepage where MCP is currently spiking in interest.

---

## Article body (paste below the title)

```markdown
My last OSS project shipped to 28 stars in a month. The product wasn't the bottleneck. Distribution was.

I'm a builder, not a marketer. I have 3 followers on X and zero email list. Every release I'd promise myself I'd "do the marketing this time" — and every release that promise lasted until I looked at a blank tweet box and switched to writing the next feature.

So I built `orallexa-marketing-agent` — an open-source Python SDK + MCP server that turns my git log into platform-specific marketing drafts and learns from real engagement which framings actually win.

Repo: https://github.com/alex-jb/orallexa-marketing-agent
PyPI: `pip install "orallexa-marketing-agent[mcp]"`

This post is the build-in-public retrospective — what's in it, what's surprising, what failed twice before working.

## What it actually does

You point it at a GitHub repo. It runs on a daily cron (or you trigger it manually). For each enabled project, it:

1. Pulls recent commits via `gh api`
2. Drafts platform-tuned posts for X, Reddit, LinkedIn, Bluesky, Mastodon, Threads, and Dev.to
3. Each draft gets passed through a heuristic + LLM critic that auto-rejects hype words ("revolutionary", "cutting-edge"), length overflows, and hashtag spam
4. Survivors land as markdown files in `queue/pending/`

You review them in your editor (Obsidian works great), then `git mv pending/X.md approved/X.md` to publish. A second GitHub Action picks up `approved/` pushes and actually posts. The agent never posts without you saying yes.

```bash
$ marketing-agent generate \\
    --name Orallexa \\
    --tagline "Self-tuning multi-agent AI trading system" \\
    --platforms x linkedin reddit \\
    --to-queue
📥 queue/pending/20260502T214309Z-orallexa-x.md
📥 queue/pending/20260502T214315Z-orallexa-linkedin.md
📥 queue/pending/20260502T214322Z-orallexa-reddit.md
```

## Why MCP

I run a daily reading + planning loop in Claude Desktop already. Adding "ask Claude to draft today's posts for me" without leaving the conversation removed enough friction that I actually do it. The MCP server exposes 7 tools:

| Tool | What |
|---|---|
| `draft_posts` | Generate per-platform drafts for a project |
| `submit_to_queue` | Save a draft for human review |
| `list_queue` | List pending/approved/posted/rejected counts |
| `engagement_top` | Show top-performing past posts |
| `optimal_time` | Best hour-of-week to post per platform |
| `bandit_stats` | Per-variant Thompson posterior — which framings win |
| `launch_plan` | Generate a 30/60/90-day plan with PH-relative timing |

Install once, add to `claude_desktop_config.json`, restart Claude. Then in any conversation:

> Use marketing-agent to draft today's X and LinkedIn posts for my repo `alex-jb/orallexa-marketing-agent`. Use template mode (no LLM key needed).

## The interesting part: a Thompson-sampling bandit picks the framing

Most "AI marketing" tools just generate. They don't close the feedback loop. So you ship 50 generated tweets, one of them happens to do well, and you have no clue whether the win was the topic, the time, the framing, or noise.

This one tags each X draft with a `variant_key` — currently `x:emoji-led`, `x:question-led`, or `x:stat-led`. Before each LLM call, a Thompson Beta-conjugate bandit samples one variant; the LLM gets a one-line style hint matching that variant; the resulting post carries the tag. After 24 hours, a launchd job pulls X engagement metrics and feeds the like count back through `bandit.update_from_engagement(variant_key, …)`.

After my first week (n=7 across 3 variants), the posterior looks like:

```
x:question-led    n=1    mean=0.333    [0.00, 0.80]
x:emoji-led       n=4    mean=0.259    [0.00, 0.58]
x:stat-led        n=2    mean=0.250    [0.00, 0.63]
```

The 95% credible intervals overlap completely — too early to call. But the loop runs. By month-end I should know whether my audience actually responds to one framing more than the others, with statistical evidence, not vibes.

## What broke that I didn't expect

**1. GitHub Actions secrets that look set but are empty.** `gh secret list` shows the timestamp but not the value. Twice I set `X_API_KEY_SECRET` by hitting Enter without pasting. The publish workflow ran for 5 days "successfully" while my actually-approved drafts sat in `queue/approved/` collecting dust because the X adapter said "missing env vars". Fix: always check the workflow run's masked env block. A real secret renders `***`; an empty one renders blank.

**2. PyPI Trusted Publishing requires a tag-anchored ref.** My first attempt to publish v0.18.1 used `gh workflow run --ref v0.18.1` (workflow_dispatch). That triggers from `refs/heads/main`, not `refs/tags/v0.18.1`. PyPI's Trusted Publisher matches on the ref, so it rejected with `invalid-publisher`. The fix is `git push --tags` and let the tag-push event trigger the workflow.

**3. LLM mode silently fell through to template mode for a month.** ANTHROPIC_API_KEY was set as a GH secret but stored with surrounding quotes and a trailing `\n` (because the .env file format had it that way and I copy-pasted). Anthropic returned 401, the generator caught the exception, fell back to template mode, returned ugly output, and didn't log anything. Fix in v0.18.2: when the HYBRID path falls back to template, it now logs `LLM generation failed for x, falling back to template: <ExceptionType>: <message>`. Silent fallbacks are an antipattern; if you're writing one, log loudly.

**4. The trends-driven path produced 30-50 chars more output than the commit path.** v0.18.5 fixed a systematic 280-char overflow on trends drafts (7/9 went over the X publish gate). Root cause: the synthetic Project's `recent_changes[0]` carried a verbose hook (full title + summary + URL ≈ 120 chars) that the LLM echoed. Three-layer fix: shrink the hook, tighten the prompt, add a post-LLM retry/truncate safety net. LLM word counts are best treated as advisory, not constraints.

## What's deliberately NOT in there

- **No 知乎 / 小红书 auto-publish.** Per Q2 2026 anti-bot research, both platforms detect AI-account behavior at the TLS/behavioral layer that Playwright + stealth cannot defeat. The agent has `dry_run_preview()` for both — it generates platform-formatted content with AI-disclosure reminders and routes you to the right manual paste UI. The 2026 ROI of automated posting on Chinese platforms, after factoring account-burn, is negative.
- **No "buy more impressions" features.** The bandit + critic + dedup gate are about post quality, not paid promotion.
- **No multi-account orchestration.** One author per project. Sock-puppet detection is real and the platforms are getting better.

## Stack + numbers

- Python 3.11+, `pyproject.toml`, no Poetry
- 408 tests passing, 77% coverage, CI matrix Python 3.11/3.12
- Anthropic Sonnet 4.6 default, Cloudflare Workers AI Llama 3.3 as cheap drafter (~80% cost reduction)
- SQLite single-file storage (memory + cost + engagement + bandit + reflexion + preference all in one db)
- Pydantic models everywhere — no untyped dicts crossing module boundaries
- MIT license

## Where to go next

```bash
pip install "orallexa-marketing-agent[mcp]"
```

The README has a 30-second offline demo (`make demo`) that needs zero API keys. The MCP integration adds `marketing-agent-mcp` to your Claude Desktop config in 3 lines.

If you want to talk shop about variant bandits, Reflexion-lite, or the failure modes I haven't found yet — issues / discussions are open. I'd especially love to hear from anyone running `solo-founder-os` (the shared agent base) or building their own MCP server in the marketing-adjacent space.

---

Built by [alex-jb](https://github.com/alex-jb). Shipped 18 versions in 4 days during the pre-PH sprint for [VibeXForge](https://vibexforge.com); marketing-agent is what writes VibeXForge's launch material now.
```

---

## Posting checklist

1. Have the cover image URL ready (1000×420)
2. Title locked (60 chars)
3. Body pasted, cover added, tags filled
4. Hit "Publish" (not "Save draft")
5. Within 5 min: cross-post the dev.to URL on X with one-line context: `"Just wrote this up — what I learned building an MCP server that markets my OSS repo from git log: <dev.to url>"`. dev.to traffic disproportionately comes from Twitter/X referrals.
6. Reply to dev.to comments within 24h. dev.to community is more polite than HN; the bar for substantive replies is lower.

## Realistic expectations

- 80% chance: 50-300 reads, 5-15 reactions, +2-10 stars to the repo over the week
- 15% chance: trends to dev.to homepage → 1k-5k reads → +20-50 stars
- 5% chance: featured by dev.to mods or quoted by a newsletter → 5k-20k reads → +100-300 stars

dev.to is lower-variance than HN; expectations are smaller but more reliable. Best as a complement to Show HN, not a replacement.
