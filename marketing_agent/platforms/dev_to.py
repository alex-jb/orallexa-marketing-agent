"""DEV.to adapter — STUB for v0.1 (dry-run only).

DEV.to has a public API but auto-posting articles is rate-limited and
better treated as a manual review step. v0.1 just renders a preview the
user can copy/paste.

TODO(alex): implement DEV.to API integration in Phase 2.
"""
from __future__ import annotations

from marketing_agent.types import Platform, Post
from marketing_agent.platforms.base import NotConfigured


class DevToAdapter:
    platform = Platform.DEV_TO

    def is_configured(self) -> bool:
        return False  # Phase 2

    def dry_run_preview(self, post: Post) -> str:
        return (
            f"--- DEV.to preview ---\n"
            f"Title: {post.title or '(untitled)'}\n\n"
            f"{post.body}\n"
            f"--- end ---\n"
            f"(Markdown body — paste into dev.to/new manually. API integration in Phase 2.)"
        )

    def post(self, post: Post) -> str:
        raise NotConfigured(
            "DEV.to auto-posting not implemented in v0.1 — use dry_run_preview() and paste manually."
        )
