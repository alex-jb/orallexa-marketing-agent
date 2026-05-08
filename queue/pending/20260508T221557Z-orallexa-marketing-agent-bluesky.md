---
platform: bluesky
project: orallexa-marketing-agent
generated_by: hybrid
generated_at: 2026-05-08T22:15:58.139928+00:00
char_count: 474
---
shipped orallexa-marketing-agent v0.20.0

v0.19 added predict_top_k() to the API. v0.20 actually routes the orchestrator through it.

new: generate_variants(project, platform, n=2) — returns top-N posts for a platform, ranked by bandit score. each Post gets predicted_mean + predicted_n_pulls attached so humans can see why the ranker picked it.

cost side: n=2 on a 3-variant pool means 2 LLM calls, not 3. n=1 falls back to the existing single-call path so nothing breaks.
