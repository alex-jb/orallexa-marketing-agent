"""Core domain types — Pydantic models that flow between modules.

Design rule: nothing untyped crosses module boundaries. If you need a dict,
make a Pydantic model first.
"""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class Platform(str, Enum):
    """Supported distribution platforms."""
    X = "x"
    REDDIT = "reddit"
    LINKEDIN = "linkedin"
    HACKER_NEWS = "hacker_news"      # post URL only, manual submit
    SUBSTACK = "substack"            # via RSS / email
    DEV_TO = "dev_to"                # API
    BLUESKY = "bluesky"              # AT Protocol — fastest-growing X alt 2026
    MASTODON = "mastodon"            # ActivityPub — open Twitter alt
    THREADS = "threads"              # Meta — Phase 2
    ZHIHU = "zhihu"                  # 知乎 — semi-auto via browser
    XIAOHONGSHU = "xiaohongshu"      # 小红书 — semi-auto


class GenerationMode(str, Enum):
    """How content is produced."""
    LLM = "llm"            # Claude / GPT generates
    TEMPLATE = "template"  # Deterministic template fallback
    HYBRID = "hybrid"      # LLM with template fallback on error


class Project(BaseModel):
    """An AI/OSS project to market.

    Minimal required fields are name + tagline. Everything else helps the
    content generator produce better output but is optional.
    """
    name: str = Field(..., description="Short product name, e.g. 'Orallexa'")
    tagline: str = Field(..., max_length=200,
                          description="One-line pitch, e.g. 'Self-tuning multi-agent AI trading system'")
    description: Optional[str] = Field(None, max_length=2000,
                                         description="Longer description, README-style")
    github_url: Optional[str] = Field(None, description="GitHub repo URL")
    website_url: Optional[str] = Field(None, description="Live demo or product URL")
    tags: list[str] = Field(default_factory=list,
                             description="Topical tags, e.g. ['agents', 'trading', 'llm']")
    target_audience: Optional[str] = Field(None,
                                             description="e.g. 'quant developers', 'AI researchers'")
    recent_changes: list[str] = Field(default_factory=list,
                                        description="Recent commit messages or release notes")


class Post(BaseModel):
    """A piece of content destined for a single platform."""
    platform: Platform
    body: str = Field(..., description="The actual text to post")
    title: Optional[str] = Field(None, description="Used by Reddit, HN, Substack")
    target: Optional[str] = Field(None,
                                    description="Subreddit name, LinkedIn audience, etc.")
    in_reply_to: Optional[str] = Field(None,
                                         description="ID of post being replied to (for threads)")
    char_count: Optional[int] = Field(None, description="Rendered length")
    variant_key: Optional[str] = Field(
        None,
        description="Stable identifier of the stylistic variant for bandit selection, "
                    "e.g. 'x:emoji-led', 'x:question-led', 'reddit:value-first'.",
    )
    image_url: Optional[str] = Field(
        None,
        description="Optional cover image URL. Pollinations / Gemini-generated. "
                    "X adapter downloads & uploads via media/upload.json before posting.",
    )

    def with_count(self) -> "Post":
        """Return a copy with char_count populated."""
        return self.model_copy(update={"char_count": len(self.body)})


class Engagement(BaseModel):
    """A real engagement event from a platform — used to feed back into strategy."""
    platform: Platform
    post_id: str
    metric: str = Field(..., description="like / share / reply / click / save / follow")
    count: int = Field(default=1, ge=0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    actor: Optional[str] = Field(None, description="Platform username if available")
