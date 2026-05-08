---
platform: mastodon
project: orallexa-marketing-agent
generated_by: hybrid
generated_at: 2026-05-08T22:15:59.407446+00:00
char_count: 611
---
shipped v0.20.0 of orallexa-marketing-agent

v0.19 added predict_top_k() to the bandit API but nothing actually called it. v0.20 fixes that.

new: generate_variants(project, platform, n=2) — asks the bandit which N variants are worth generating, runs only those LLM calls, returns Posts tagged with predicted_mean + predicted_n_pulls so a human can see why each one ranked

concrete effect: n=2 on a 3-variant pool = 2 LLM calls instead of 3. not magic, just don't pay for generations you'd discard anyway

n=1 falls through to the existing single-call path so nothing breaks

#opensource #buildinpublic #python
