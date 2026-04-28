"""Base PlatformAdapter Protocol. All platform adapters implement this."""
from __future__ import annotations
from typing import Protocol, runtime_checkable

from marketing_agent.types import Platform, Post


@runtime_checkable
class PlatformAdapter(Protocol):
    """Each platform adapter knows how to validate, preview, and post."""

    platform: Platform

    def is_configured(self) -> bool:
        """Return True if this adapter has the env vars to actually post."""
        ...

    def dry_run_preview(self, post: Post) -> str:
        """Render what would be posted, no side effects. Always works."""
        ...

    def post(self, post: Post) -> str:
        """Actually post. Returns the URL (or platform-specific id).

        Should raise NotConfigured if `is_configured()` is False.
        """
        ...


class NotConfigured(RuntimeError):
    """Raised when a platform adapter is asked to post but lacks credentials."""


def get_adapter(platform: Platform) -> PlatformAdapter:
    """Factory that returns the right adapter for a platform."""
    # Lazy imports avoid circular references
    from marketing_agent.platforms.x import XAdapter
    from marketing_agent.platforms.reddit import RedditAdapter
    from marketing_agent.platforms.linkedin import LinkedInAdapter
    from marketing_agent.platforms.dev_to import DevToAdapter

    mapping = {
        Platform.X: XAdapter,
        Platform.REDDIT: RedditAdapter,
        Platform.LINKEDIN: LinkedInAdapter,
        Platform.DEV_TO: DevToAdapter,
    }
    cls = mapping.get(platform)
    if cls is None:
        raise NotImplementedError(f"No adapter for platform: {platform}")
    return cls()
