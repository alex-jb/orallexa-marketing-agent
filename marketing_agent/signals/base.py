"""Shared types for the signals module."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


@dataclass
class ScrapedItem:
    """One row of scraped signal — platform-agnostic shape.

    Goes to JSONL on disk, then either:
    - read by marketing-agent generators as "what indie founders are talking
      about this week" context, OR
    - read by customer-discovery-agent as PainPoint candidates.
    """

    source: str  # "indie_hackers" / "product_hunt" / "github_topic" / ...
    item_id: str  # source-stable id for dedup
    title: str
    url: str
    author_handle: Optional[str] = None
    posted_at: Optional[str] = None  # ISO 8601 if known
    votes: Optional[int] = None
    comments: Optional[int] = None
    tag: Optional[str] = None
    body_snippet: Optional[str] = None
    scraped_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return asdict(self)


class SignalSource:
    """Base class for a single platform scraper.

    Implementations provide:
    - source_name (class-level constant matching ScrapedItem.source)
    - fetch(...) returning list[ScrapedItem]
    """

    source_name: str = "abstract"

    def fetch(self, **kwargs) -> list[ScrapedItem]:  # pragma: no cover
        raise NotImplementedError
