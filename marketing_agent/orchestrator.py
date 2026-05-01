"""High-level orchestrator: project → posts → distribution.

This is the main entry point users interact with.
"""
from __future__ import annotations
from typing import Optional

from marketing_agent.types import (
    GenerationMode, Platform, Post, Project,
)
from marketing_agent.content import generate_posts
from marketing_agent.platforms.base import (
    PlatformAdapter, get_adapter,
)


class Orchestrator:
    """High-level facade for generating + distributing project content.

    Typical usage:
        orch = Orchestrator()
        posts = orch.generate(project, [Platform.X, Platform.REDDIT])
        for post in posts:
            print(orch.preview(post))
        # When ready:
        # urls = [orch.post(p) for p in posts]
    """

    def __init__(self, *, mode: GenerationMode = GenerationMode.HYBRID):
        self.mode = mode
        self._adapter_cache: dict[Platform, PlatformAdapter] = {}

    def generate(
        self,
        project: Project,
        platforms: list[Platform],
        *,
        subreddit: Optional[str] = None,
        n_variants: int = 1,
    ) -> list[Post]:
        """Generate one Post per platform.

        n_variants > 1: produce N stylistic variants and pick one via bandit
        (currently only X has multiple variants).
        """
        return generate_posts(project, platforms, mode=self.mode,
                                subreddit=subreddit, n_variants=n_variants)

    def preview(self, post: Post) -> str:
        """Return the dry-run preview from the matching adapter."""
        return self._adapter(post.platform).dry_run_preview(post)

    def post(self, post: Post) -> str:
        """Actually post. Raises NotConfigured if platform credentials missing."""
        return self._adapter(post.platform).post(post)

    def is_ready(self, platform: Platform) -> bool:
        """Whether the adapter for this platform has credentials to post."""
        return self._adapter(platform).is_configured()

    def _adapter(self, platform: Platform) -> PlatformAdapter:
        if platform not in self._adapter_cache:
            self._adapter_cache[platform] = get_adapter(platform)
        return self._adapter_cache[platform]
