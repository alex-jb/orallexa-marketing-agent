"""Compat shim — use solo_founder_os.AnthropicClient when present, else
fall back to direct `anthropic.Anthropic` with the same API surface.

Why a shim? `solo-founder-os` is the shared agent-stack base used by
`build-quality-agent` and `customer-discovery-agent`. When installed in
the user's env, marketing-agent benefits from cross-agent token usage
logging (read by `cost-audit-agent`'s monthly report). But:

  - `solo-founder-os` isn't on PyPI yet (private dev package)
  - CI runners don't have it
  - First-time `pip install orallexa-marketing-agent` users won't have it

This shim makes the usage seamless: when the real package is installed,
we re-export its symbols. When it's not, we provide a zero-dep fallback
that wraps `anthropic.Anthropic` with the same `(resp, err)` tuple API.

Behavior summary:
  - `AnthropicClient(usage_log_path=...)` — if real solo-founder-os
    present, logs to that path; otherwise no-op (just calls anthropic).
  - `.configured` — True iff `ANTHROPIC_API_KEY` env var set.
  - `.messages_create(...)` — returns `(resp, err)` tuple.
  - `AnthropicClient.extract_text(resp)` — handles both shapes.
  - `DEFAULT_HAIKU_MODEL` / `DEFAULT_SONNET_MODEL` — current default ids.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Optional


# ─── Try the real solo-founder-os client first ───
try:
    from solo_founder_os.anthropic_client import (  # type: ignore
        AnthropicClient,
        DEFAULT_HAIKU_MODEL,
        DEFAULT_SONNET_MODEL,
        log_usage,
    )
    _USING_SHARED_BASE = True
except ImportError:
    _USING_SHARED_BASE = False

    DEFAULT_HAIKU_MODEL = "claude-haiku-4-5"
    DEFAULT_SONNET_MODEL = "claude-sonnet-4-6"

    # Hand-rolled twin of solo_founder_os.anthropic_client.log_usage so
    # downstream callers (edge_provider, ensemble_critic) can write to the
    # same JSONL format whether or not solo-founder-os is installed.
    import json as _json
    from datetime import datetime as _datetime, timezone as _timezone
    from pathlib import Path as _Path

    def log_usage(*, log_path: "_Path", model: str,
                    input_tokens: int, output_tokens: int,
                    extra: "dict | None" = None,
                    now: "_datetime | None" = None) -> None:
        """Append one usage row to log_path. Best-effort — never raises.

        Schema matches solo_founder_os.anthropic_client.log_usage:
            {ts, model, input_tokens, output_tokens, **extra}
        """
        now = now or _datetime.now(_timezone.utc)
        row = {
            "ts": now.isoformat(),
            "model": model,
            "input_tokens": int(input_tokens),
            "output_tokens": int(output_tokens),
        }
        if extra:
            row.update(extra)
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a") as f:
                f.write(_json.dumps(row) + "\n")
        except Exception:
            pass

    class AnthropicClient:  # type: ignore[no-redef]
        """Fallback: thin wrapper around anthropic.Anthropic with the same
        (resp, err) tuple API as solo_founder_os.AnthropicClient."""

        def __init__(self, *, usage_log_path: Optional[Path] = None,
                       env_key: str = "ANTHROPIC_API_KEY"):
            self.usage_log_path = usage_log_path  # noqa: F841 (no-op in fallback)
            self.env_key = env_key
            self._client: Any = None

        @property
        def configured(self) -> bool:
            return bool(os.getenv(self.env_key))

        def _ensure_client(self) -> Any:
            if self._client is None:
                from anthropic import Anthropic
                self._client = Anthropic()
            return self._client

        def messages_create(self, **kwargs):
            """Returns (resp, err) — err is None on success, else an
            Exception instance."""
            try:
                resp = self._ensure_client().messages.create(**kwargs)
                return resp, None
            except Exception as e:  # pragma: no cover (network-dependent)
                return None, e

        @staticmethod
        def extract_text(resp: Any) -> str:
            """Pull the text content from an Anthropic response object."""
            if resp is None:
                return ""
            try:
                return "".join(b.text for b in resp.content if b.type == "text")
            except Exception:
                return ""


def is_using_shared_base() -> bool:
    """True iff the real solo_founder_os.AnthropicClient is in use."""
    return _USING_SHARED_BASE
