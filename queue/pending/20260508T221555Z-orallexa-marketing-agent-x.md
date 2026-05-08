---
platform: x
project: orallexa-marketing-agent
generated_by: hybrid
generated_at: 2026-05-08T22:15:57.180724+00:00
variant_key: x:question-led
char_count: 251
---
🤔 Why generate 3 variants if you only need the top 2?

v0.20 wires predict_top_k() into the actual generation path. n=2 on a 3-variant pool → bandit scores first, then 2 LLM calls. Each Post carries predicted_mean so reviewers see why it ranked there.
