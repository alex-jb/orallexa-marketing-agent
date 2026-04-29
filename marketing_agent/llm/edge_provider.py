"""Edge inference provider — Cloudflare Workers AI as a cheap drafter.

Cloudflare offers `@cf/meta/llama-3.3-70b-instruct-fp8-fast` at $0.011/1M
input tokens, ~200ms cold start. Quality is "good enough for first-draft"
on short-form content; we still send through the critic + rewriter on
Claude when keyed for the final-pass tier.

Auth: 2 env vars (CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID). Without
them, this module is dormant — generator.py falls through to Claude.

No SDK dependency: stdlib `urllib` only. Keeps install footprint small.
"""
from __future__ import annotations
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

from marketing_agent.logging import get_logger

log = get_logger(__name__)


# Default model. Override per-call via EdgeLLM(model=...).
DEFAULT_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"

REQUIRED_ENVS = ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID")


def is_edge_configured() -> bool:
    """True iff Cloudflare creds are present in env."""
    return all(os.getenv(k) for k in REQUIRED_ENVS)


@dataclass
class EdgeLLMResponse:
    """Single completion result. Stays small — we don't yet stream."""
    text: str
    model: str
    usage_in_tokens: int = 0
    usage_out_tokens: int = 0


@dataclass
class EdgeLLM:
    """Thin Cloudflare Workers AI client.

    Use complete_via_edge() for the no-instance helper, or instantiate
    this class for repeated calls with shared model + system_prompt.
    """
    model: str = DEFAULT_MODEL
    timeout_s: int = 30

    def complete(self, *, system_prompt: str, user_prompt: str,
                   max_tokens: int = 600) -> Optional[EdgeLLMResponse]:
        """Run one chat completion. Returns None on any failure."""
        if not is_edge_configured():
            return None
        token = os.getenv("CLOUDFLARE_API_TOKEN")
        account = os.getenv("CLOUDFLARE_ACCOUNT_ID")
        url = (f"https://api.cloudflare.com/client/v4/accounts/"
                f"{account}/ai/run/{self.model}")
        body = json.dumps({
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
        }).encode("utf-8")
        req = urllib.request.Request(
            url, data=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            log.warning("edge LLM call failed: %s", e)
            return None
        # Cloudflare wraps result in {"result": {"response": "..."}, "success": ...}
        if not data.get("success"):
            log.debug("edge LLM returned success=false: %s",
                       data.get("errors"))
            return None
        result = data.get("result", {})
        text = result.get("response", "")
        usage = result.get("usage") or {}
        return EdgeLLMResponse(
            text=text.strip(),
            model=self.model,
            usage_in_tokens=int(usage.get("prompt_tokens", 0)),
            usage_out_tokens=int(usage.get("completion_tokens", 0)),
        )


def complete_via_edge(*, system_prompt: str, user_prompt: str,
                        model: Optional[str] = None,
                        max_tokens: int = 600) -> Optional[str]:
    """Convenience: returns just the text, or None on any failure / no creds.

    Drop-in for the generator's "give me a draft" call when
    `is_edge_configured()` is true.
    """
    client = EdgeLLM(model=model or DEFAULT_MODEL)
    resp = client.complete(
        system_prompt=system_prompt, user_prompt=user_prompt,
        max_tokens=max_tokens,
    )
    return resp.text if resp else None
