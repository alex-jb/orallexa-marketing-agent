"""LLM provider abstraction.

v0.12 routes draft-time generation away from Anthropic when cheaper
providers are configured. Critic + rewriter still go to Claude when keyed.

Per Q1 2026 pricing:
  - Anthropic Claude Sonnet 4.6: ~$3/1M input, $15/1M output
  - Cloudflare Workers AI Llama 3.3 70B: $0.011/1M tokens
  - Groq Qwen 2.5 72B: similar
This cuts daily-cron cost ~80% with negligible quality drop on first-draft.
"""
from marketing_agent.llm.edge_provider import (
    EdgeLLM, complete_via_edge, is_edge_configured,
)

__all__ = ["EdgeLLM", "complete_via_edge", "is_edge_configured"]
