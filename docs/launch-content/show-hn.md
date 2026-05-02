# Show HN — orallexa-marketing-agent

**Where to submit:** https://news.ycombinator.com/submit

## When to fire

**Best time slot:** Tuesday-Thursday, 09:00-10:00 EST (14:00-15:00 UTC).

Why: HN front-page algorithm rewards early upvotes; US workday morning gets the most engaged audience. Avoid Mondays (everyone catches up on weekend backlog) and Fridays (post-lunch exodus). Don't fire on holidays.

**Soak window:** the post stays "new" for ~30 min. Need ≥5 upvotes from non-anon sources in that window to have a shot at the front page. Have 2-3 trusted dev friends on standby to upvote in the first 10 min.

**Don't ask for upvotes** in the post body — HN punishes voting rings.

## Title (80 chars max — current: 75)

```
Show HN: Marketing agent for OSS founders – commit-driven X / Reddit drafts
```

Alternates if the above feels off:
- `Show HN: I built an MCP server that markets my OSS repo from git log` (66 chars — meta angle, dev-resonant)
- `Show HN: Thompson-sampling bandit picks my tweet style — open source` (68 chars — leads with novel ML)
- `Show HN: I let Claude post for me on 7 platforms (with HITL queue)` (65 chars — most accessible)

**Recommended:** the first one — concrete, specific, names the audience.

## URL field

```
https://github.com/alex-jb/orallexa-marketing-agent
```

(Not the PyPI page — HN cohort prefers the GitHub repo for OSS projects.)

## Optional "text" field (HN's "what" body)

Leave EMPTY. Show HN convention is: URL alone is the post. A "text" body comes off as ad copy. The first comment slot (which you write yourself, immediately after submitting) is where the context goes.

## First-comment template (post this immediately as the FIRST comment after submitting)

```text
Hi HN — author here.

I built this because my last OSS project shipped to 28 stars in a month. The product wasn't the bottleneck; distribution was. I'm a builder, not a marketer, and writing platform-specific posts for every release got tedious enough that I just stopped.

What it does:
- Pulls recent commits from a GitHub repo
- Drafts platform-tuned posts (X, Reddit, LinkedIn, Bluesky, Mastodon, Threads, Dev.to)
- Drafts land as markdown files in queue/pending/ — git mv to approved/ to publish
- Built-in MCP server (7 tools) so it works inside Claude Code / Desktop / Cursor / Zed
- Thompson-sampling variant bandit picks emoji-led / question-led / stat-led framings; learns from real engagement which one wins per channel
- Voyager-style auto-skill promotion: top-quartile-engagement posts auto-distill into reusable Claude Skill markdown
- Reflexion memory: cross-session critic findings prepended to next prompt as "patterns to avoid"
- Cloudflare Workers AI edge tier (~80% cheaper) before Anthropic Sonnet 4.6 fallback

The whole thing is dogfooded — the agent's own daily marketing posts come from the daily.yml cron, queue/pending/ → human review → publish. Past 48 hours: 5 production posts written by it, 3 of them with proper variant_key tags so the bandit's actually learning. First-week posterior: emoji-led n=4 mean 0.259, stat-led n=2 mean 0.250, question-led n=1 mean 0.333 — way too early to call but the loop runs.

What I'd love feedback on:
1. Is the variant_key bandit useful, or should it just always pick the historically best one? Thompson sampling explores, which means you "waste" some posts on under-tried framings — unclear if that's worth it at the volumes a solo founder posts.
2. The Voyager auto-skill promotion bothers some people philosophically (machine learning your voice and reusing it). Is that creepy or useful?
3. I deliberately do NOT auto-publish to 知乎 / 小红书 (Chinese platforms) — anti-bot risk per Q2 2026 research is too high. Honest-prep only. Curious if anyone has a different read.

Repo: https://github.com/alex-jb/orallexa-marketing-agent
PyPI: pip install "orallexa-marketing-agent[mcp]"
408 tests, 77% coverage, MIT.
```

## After submitting

1. Open the post URL in a new tab and **write the first comment immediately** (the template above). The first-comment slot disproportionately drives engagement.
2. Don't reply to your own comment for the first 2 hours; let others get a word in.
3. Reply to **every** top-level comment within 4 hours. HN rewards visible authors. Substantive replies > "thanks!".
4. If a hostile comment lands, respond ONCE with the most charitable reading of their concern + your actual counter-evidence. Never argue twice with one person.
5. **Don't share the link on Twitter for 6 hours.** HN moderators downweight cross-promoted posts.

## Realistic expectations

- 70% chance: no front-page hit, ~30-50 stars over the week, a few "this is cool" replies. Worth it as warm-up.
- 25% chance: hits "/newest" → 50-200 upvotes → front-page tail → +200-500 stars in 24-48h.
- 5% chance: hits front-page top-10 → 500+ upvotes → +1000-3000 stars + 1-3 inbound emails ("can I pay for this") + 1-2 acquisition feelers.

## Don'ts

- Don't link to your X/LinkedIn in the first comment (looks spammy)
- Don't say "please upvote" anywhere
- Don't reply to comments with marketing language
- Don't repost if it dies — HN auto-flags repeats
- Don't fire while another big OSS launch is on the front page (check beforehand)
