# Marketing Agent as SaaS — design doc (FUTURE, NOT DEPLOYED)

**Status:** Speculative design only. Do not implement until VibeXForge has crossed 50 active makers (≈ 4-8 weeks post-PH 2026-05-04). This file exists so the design is locked while context is fresh, not because we're shipping it next.

**Author:** Alex (Xiaoyu) Ji + Claude · 2026-05-01

---

## 1. Why this exists

`marketing-agent` is open-source and well-architected, but the OSS install path has high friction (clone repo, set 16 env vars, configure cron, manage queue files). Most indie makers won't pay that activation cost.

`VibeXForge` already has the audience (AI makers actively trying to grow their projects) and the dashboard. The natural next move: **"Auto-promote this project — $X/mo"** as a checkbox at submission time. The agent goes "out to work" for the maker.

This doc captures the architecture that would let us flip that switch when the demand signal is real.

## 2. North-star user story

> Maker submits an AI project on VibeXForge. After Claude scores it (existing flow), they see:
>
> > "Auto-promote this project across X, LinkedIn, and Bluesky — $19/mo. Each morning we draft posts from your repo's commits, you approve in your VibeX dashboard, we auto-publish."
>
> They click yes → Stripe checkout → connect their X / LinkedIn OAuth → next morning, drafts are in their dashboard.

## 3. Architecture

### 3.1 Multi-tenant config

Today: `marketing-agent.yml` is a flat list of projects, single repo.
SaaS: per-tenant config rows in Supabase, schema:

```sql
CREATE TABLE marketing_subscriptions (
  id              uuid PRIMARY KEY,
  user_id         uuid REFERENCES auth.users(id),
  vibex_project_id uuid REFERENCES projects(id),
  -- Source
  github_repo     text NOT NULL,
  github_token_encrypted bytea,  -- per-tenant
  -- Targets
  platforms       text[] NOT NULL DEFAULT ARRAY['x'],
  x_oauth_token   bytea,
  linkedin_oauth_token bytea,
  bluesky_handle  text,
  bluesky_app_password_encrypted bytea,
  -- Behavior
  trends_enabled  bool DEFAULT true,
  daily_budget_usd numeric DEFAULT 1.00,
  -- Billing
  stripe_subscription_id text,
  status          text NOT NULL DEFAULT 'active',  -- active | paused | canceled
  created_at      timestamptz DEFAULT now()
);
```

Per-tenant draft queue lives in `drafts` table (not in markdown files — moot at scale):

```sql
CREATE TABLE drafts (
  id              uuid PRIMARY KEY,
  subscription_id uuid REFERENCES marketing_subscriptions(id),
  platform        text NOT NULL,
  body            text NOT NULL,
  variant_key     text,
  generated_by    text,            -- 'commit' | 'trends'
  status          text DEFAULT 'pending', -- pending | approved | posted | rejected
  external_id     text,
  posted_at       timestamptz,
  created_at      timestamptz DEFAULT now()
);
```

### 3.2 Daily generation worker

Single Vercel Cron (or Inngest job) at 14:00 UTC iterates all active subscriptions, calls into the existing marketing-agent SDK with per-tenant Project + queue. Stays the same code path — just `ApprovalQueue` swaps for a Postgres-backed implementation behind the same interface.

```python
# marketing_agent/queue.py becomes a Protocol
class ApprovalQueue(Protocol):
    def submit(self, post, project_name, generated_by, *, gate=True) -> Reference: ...
    def list_approved(self) -> list[Reference]: ...
    ...

# OSS implementation: file-based (existing)
class FileApprovalQueue: ...

# SaaS implementation: Supabase-backed
class SupabaseApprovalQueue:
    def __init__(self, subscription_id: str): ...
```

### 3.3 HITL UI inside VibeXForge

New tab on each project's dashboard: `Marketing → Drafts`. Lists pending drafts with platform badge + body + "approve / edit / reject" buttons. Approval flips `status` to `approved`; a separate cron runs every 5 min and posts approved items via the platform OAuth tokens.

UI is just one page — reuses VibeX's existing card components. ~1 day of frontend work.

### 3.4 Billing

Stripe subscription per project (not per user — important: a maker with 3 VibeX projects can subscribe each independently).

Pricing tiers:
- **$0/mo (Free)** — 1 platform, 3 drafts/week, no auto-publish (HITL via VibeX UI only). Funnel for paid.
- **$19/mo (Solo)** — 3 platforms, daily drafts, auto-publish.
- **$49/mo (Maker)** — all 9 platforms, daily drafts + trends pass, image generation, auto-publish, engagement tracking.

Stripe webhook → flips `status` field on subscription cancel/pause.

## 4. Cost model

Per-subscription per-month:

| Component | Cost |
|---|---|
| Anthropic Sonnet draft (~3 platforms × 30 days × 600 tokens) | $0.20 |
| Anthropic Sonnet critic + reflexion overhead | $0.10 |
| Cloudflare edge tier (when configured) | $0.05 |
| Pollinations images (free) | $0 |
| Supabase row storage | ~$0.02 |
| Vercel function exec | ~$0.10 |
| **Total variable cost** | **~$0.50/mo** |

At $19/mo retail: 97% gross margin per subscriber. Comfortable enough that we can absorb a few abusive accounts without thinking.

Break-even: 3 paying subscribers covers Anthropic API floor (no minimums per Q2 2026). 50 paying = $950 MRR, real budget for ads / X engagement growth experiments.

## 5. Tech stack decisions

| Concern | Decision |
|---|---|
| Backend | Existing marketing-agent SDK (no rewrite) |
| Job runner | Inngest (Vercel-native, queues + retries) — or Vercel Cron for simple case |
| DB | Supabase (already powering VibeX, share auth) |
| Frontend | VibeXForge Next.js app (new tab in existing dashboard) |
| Billing | Stripe (already supported by VibeX-style projects) |
| Secrets storage | Supabase Vault for OAuth tokens |
| Observability | Reuse Phoenix/OTel from marketing-agent v0.8 |

No new infra to learn. Everything reuses what VibeX already runs.

## 6. Phased rollout (after demand signal)

**Phase 0 (current):** OSS-only. Demand signal = 50+ unique installs from PyPI in a month + at least 2 unsolicited "I'd pay for this" replies on X/HN.

**Phase 1 (week 1-2 of build):** Single-tenant SaaS. Hardcoded to my own VibeX. Adapter pattern lets me run both file-based (local dev) and Supabase-backed (deployed) without code changes. Validates the abstraction.

**Phase 2 (week 3-4):** Multi-tenant. Add the `marketing_subscriptions` table, per-tenant secrets via Supabase Vault. Open closed beta to 5 hand-picked VibeX makers (free).

**Phase 3 (week 5-6):** Stripe + landing page. Open public signup. Free tier active. Monitor cost/sub ratio.

**Phase 4 (week 7+):** Iterate based on actual usage. Trend tuning, platform additions, image upgrade.

Each phase is shippable on its own — no big-bang launch.

## 7. Risks

| Risk | Mitigation |
|---|---|
| **OAuth maintenance** — X / LinkedIn tokens rotate, expire, get revoked. Per-tenant token refresh = real engineering. | Build it once for X (highest demand), defer LinkedIn/Bluesky to Phase 4. Show clear UI when a token expires. |
| **Quality of auto-drafts at scale** — fine for my own projects, untested when 50 different repos hit the same generator. | Keep critic gate strict. Make gate threshold a per-tier config (paid tiers get stricter). Reserve manual takeover. |
| **Spam classification on X** — repeated similar posts from many accounts could fingerprint as bot. | Per-tenant variant pool diversification. Stagger posting times across the hour. Already have `optimal_post_time` per tenant. |
| **Anthropic rate limits** — fan-out across 50 tenants × 3 platforms = 150 calls in 5 min window. | Batch API for non-time-sensitive drafts (50% off + bypasses tier limits). Stagger generation across the day. |
| **VibeX dashboard becomes the bottleneck** — every paid maker needs to log in daily to approve. | Optional auto-approve for tier 3 with critic score > 8/10. Plus weekly digest email. |
| **Customer support load** — even 50 subs at 1 ticket/mo each = 50 tickets/mo. | Defer Phase 4 → 5; free tier has no SLA. |

## 8. Out of scope (intentional)

- **Reddit / HN posting** — too account-shape-sensitive for managed publishing. Keep HITL-only forever.
- **Chinese platforms (知乎 / 小红书)** — anti-bot risk too high (per existing brain rule). Forever opt-in manual paste.
- **White-labeling** — different agency-style product. Not us.
- **Cross-tenant insights** — privacy hazard. Each subscription is its own silo.

## 9. Why not just ship this now?

PH 5/4 is in 3 days. Building a multi-tenant SaaS layer in 3 days while also (a) executing PH launch, (b) supporting Chenxi's 5/4 interview, (c) keeping all 8 OSS agents healthy is irrational. **PH outcome is the demand signal that decides whether this design even gets executed.** If PH clears 200 upvotes and we get 5+ "where do I sign up" replies, this becomes Tier-1 work. If PH lands at 50 upvotes with no signal, we keep it OSS forever.

## 10. Decision criteria (when to flip the switch)

Trigger Phase 1 work IF (within 30 days of PH):
- ≥ 50 unique PyPI downloads of `orallexa-marketing-agent` AND
- ≥ 2 unsolicited "I'd pay" replies on X / HN OR
- ≥ 1 maker on VibeXForge using marketing-agent OSS asks "can you just run this for me"

Otherwise: keep this doc on ice, focus on growing OSS adoption first.

---

*This is intentionally a frozen design doc. Don't update it incrementally — if reality diverges, write `saas-design-v2.md` and link this one as ancestor.*
