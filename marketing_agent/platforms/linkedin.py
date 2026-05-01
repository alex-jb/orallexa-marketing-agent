"""LinkedIn adapter — STUB for v0.1.

LinkedIn's API is heavily restricted: posting on behalf of a user requires
LinkedIn Marketing Developer Platform approval, which is a manual review
process taking weeks. For v0.1 we ship dry-run only and let users copy/paste
the generated content into LinkedIn manually.

TODO(alex): apply for LinkedIn Marketing Developer access; integrate
linkedin-api or similar; revisit in Phase 2.
"""
from __future__ import annotations

from marketing_agent.types import Platform, Post
from marketing_agent.platforms.base import NotConfigured


class LinkedInAdapter:
    platform = Platform.LINKEDIN

    def is_configured(self) -> bool:
        # In v0.1 we never claim to be configured — always dry-run.
        return False

    def dry_run_preview(self, post: Post) -> str:
        return (
            f"--- LinkedIn preview · {len(post.body)} chars ---\n"
            f"{post.body}\n"
            f"--- end ---\n"
            f"(Copy and paste into LinkedIn manually. Auto-posting awaits API approval — see Phase 2.)"
        )

    def post(self, post: Post) -> str:
        raise NotConfigured(
            "LinkedIn auto-posting not implemented in v0.1 — use dry_run_preview() "
            "and paste manually. See marketing_agent/platforms/linkedin.py docstring."
        )
