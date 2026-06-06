# marketing-agent → Coze.cn Plugin Submission

**Status**: hedge play. Coze main bet = 0% per Solo Founder OS thesis. This
plugin exists to capture Chinese indie-founder traffic into the
`alex-jb/orallexa-marketing-agent` GitHub repo without forking attention
away from the Anthropic Skills main bet.

**Sunset clause** (visible — do not remove): if installs < 100 by
**2026-09-06** the plugin will be voluntarily delisted. 3-month review
window is hard-coded into `coze_manifest.json::sunset_clause`.

---

## 1. Deploy to Vercel

Prereq: `vercel` CLI logged in (`~/.local/node/bin/vercel login`).

```bash
cd ~/Desktop/orallexa-marketing-agent/coze_plugin

# One-time: pull existing env (skip if first deploy)
vercel link --yes
vercel env pull .env.local

# One-time: set production secrets. Leave Sensitive flag OFF —
# trap from VibeXForge: Sensitive locks vars + breaks NEXT_PUBLIC_*.
vercel env add ANTHROPIC_API_KEY production
vercel env add COZE_PLUGIN_TOKENS production
# v0 placeholders — not used yet but vercel.json declares them
vercel env add SUPABASE_URL production
vercel env add SUPABASE_ANON_KEY production

# Deploy
vercel deploy --prod --force --yes

# After first deploy succeeds, alias to a stable URL Coze can register:
vercel alias <deployment-id>.vercel.app marketing-agent-coze.vercel.app
```

**Tokens format**: comma-separated. Prefix `pro_` enables Pro rate-limit (50/min).
Example: `COZE_PLUGIN_TOKENS=free_t1,free_t2,pro_user_001,pro_user_002`.

**Verify deploy**:
```bash
curl https://marketing-agent-coze.vercel.app/health
# expect: {"status":"ok","anthropic_key_present":true,"tokens_configured":4,"version":"0.1.0"}
```

---

## 2. Register on Coze

**China region (coze.cn)** — primary target:
1. Go to https://www.coze.cn/open/ and sign in with 字节跳动 / 抖音 / 飞书 account.
2. Open 「开发者中心」 → 「插件」 → 「创建插件」.
3. Choose 「以 API 方式」 (NOT 「以 IDE 方式」 — we're hosting our own server).
4. Plugin name (中文): `marketing-agent 多平台文案生成器`.
5. Plugin name (英文): `marketing-agent multi-platform copywriter`.
6. Category: 「工具」 → 「营销 / 内容创作」.

**International (coze.com)** — secondary, same flow at https://www.coze.com/open/.
Submit the SAME OpenAPI spec; rate limits + price unchanged.

---

## 3. Submit OpenAPI spec

In the Coze plugin console:

1. 「API 配置」 → 「导入 OpenAPI 文档」.
2. Upload `coze_plugin/openapi.yaml`.
3. Server URL: `https://marketing-agent-coze.vercel.app`.
4. Auth: choose 「Bearer Token」. Token field: `Authorization`. Format:
   `Bearer {{token}}`.
5. Test the `/generate` endpoint inside Coze's test panel with
   `example_inputs[0]` from `coze_manifest.json` (VibeXForge sample).
   - Expect ≤ 30s response, 5 drafts returned, `model: claude-sonnet-4-6`.
   - If you see `template-fallback` in the response, the
     `ANTHROPIC_API_KEY` env wasn't picked up by Vercel — re-check.

---

## 4. Payment (Coze handles billing)

Coze 2.0 ships a built-in transaction layer — **do NOT integrate Stripe**.

1. 「定价配置」 → enable 「订阅模式」.
2. Free tier:
   - 名称: 免费档
   - 限额: 5 次/天 (Coze enforces, our /min limit is a defensive ceiling)
   - 价格: ¥0
3. Pro tier:
   - 名称: Pro
   - 限额: 不限量
   - 价格: ¥19/月
   - 周期: 包月续订
4. Revenue share: Coze takes 30% → author receives **¥13.3/sub/mo**.
5. Token issuance: enable 「自动下发 token」. Coze will POST to a webhook
   you can register in 「Webhook 配置」 with `{user_id, tier}` whenever a
   user subscribes. **v0 skips this** — we manually rotate the
   `COZE_PLUGIN_TOKENS` env weekly until install count justifies the
   webhook plumbing (~> 20 paying users).

---

## 5. Review timeline

| Phase | Typical | Worst case |
|---|---|---|
| Auto-lint (schema / HTTPS / OpenAPI 3.1 valid) | < 5 min | 1h |
| Human review (CN — content + 关键词) | 1-2 business days | 5 days |
| Pricing review (if you set a paid tier) | +1 business day | +3 days |
| Live in store | 3-5 business days total | 8-10 days |

If rejected, the most common causes:
- Server URL not HTTPS or returns 5xx on `/health` → fix and re-submit (no penalty).
- Description trips 「敏感词」 — avoid words like `破解` / `绕过` / `刷` / `引流`.
- Pricing tier without clear value differential → make Pro limits explicit.

---

## 6. Post-launch metrics

Track these weekly. Source: Coze 开发者中心 → 「数据看板」 + our own logs.

| Metric | Source | Target by 2026-07-06 (1 mo) | Sunset trigger |
|---|---|---|---|
| Installs | Coze dashboard | ≥ 30 | < 100 by 2026-09-06 |
| Daily generations | server log `generate ok` count | ≥ 50/day | — |
| Pro conversion % | Coze dashboard | ≥ 3% | — |
| GitHub repo stars (`alex-jb/orallexa-marketing-agent`) attributed via ?ref=coze | GitHub Insights | +30 | — |
| LLM cost / generation | usage_log.json from solo-founder-os | ≤ $0.005 | > $0.02 (kill) |
| Error rate (5xx) | Vercel logs | < 1% | > 5% |

Add to weekly retro: `~/Desktop/Interview-Prep/Projects/alex-brain/me-todo-when-back.md`.

---

## 7. Sunset criteria (HARD)

**Date**: 2026-09-06 (90 days from anticipated launch ~2026-06-06).

**Rules** — all OR-ed:
- Installs < 100 → delist.
- Pro conversion < 1% → delist.
- LLM cost > $50/month with < 20 paying subs → delist (negative margin).
- Coze platform policy change that breaks the wrapper → delist within 7d.

**How to delist**:
1. Coze console → plugin → 「下架」.
2. Vercel: `vercel rm marketing-agent-coze --yes`.
3. Update `coze_manifest.json::sunset_clause.review_date` to "delisted".
4. Log learning in `alex-brain/research/2026-09-XX-coze-sunset.md`.

**If it works** (installs ≥ 100, Pro conv ≥ 3%):
- Skip sunset. Add to active agents list in `alex-brain/index.md`.
- Consider Coze plugin for **one** other agent (customer-discovery is
  the most user-facing candidate). Do NOT ship 11 plugins — stay focused
  per the brief.

---

## Getting a token (for end users)

End users requesting access:
1. Install the plugin in Coze console → Coze auto-issues token.
2. (Until Coze webhook is wired) manually email `xji1@mail.yu.edu` with
   subject `marketing-agent token request` to be added to the
   `COZE_PLUGIN_TOKENS` env. Manual issuance is acceptable while monthly
   active < 20.

---

## Local dev / preview

```bash
cd ~/Desktop/orallexa-marketing-agent/coze_plugin
pip install -r requirements.txt
pip install -e ..                        # install marketing_agent locally
export ANTHROPIC_API_KEY=sk-ant-...
export COZE_PLUGIN_TOKENS=test-free,pro_test-pro
python3 server.py
# → http://127.0.0.1:8000/docs (Swagger UI for quick test)
```

Quick test:
```bash
curl -X POST http://127.0.0.1:8000/generate \
  -H 'Authorization: Bearer test-free' \
  -H 'Content-Type: application/json' \
  -d '{
    "project_url": "https://github.com/alex-jb/orallexa-marketing-agent",
    "project_name": "marketing-agent",
    "project_description": "Open-source AI marketing agent for solo founders.",
    "platforms": ["x", "reddit", "小红书"],
    "language": "zh"
  }' | jq .
```
