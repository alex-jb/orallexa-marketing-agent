"""Signal collection — read-only scrapers for platforms without public APIs.

Borrowed pattern from clawfirm (CDP browser automation, MIT, 2026-05),
adapted to a read-only model: we never *publish* via browser, only collect
inbound signals to feed marketing-agent + customer-discovery-agent.

Why read-only:
- Publishing via browser triggers anti-bot risk control (small-red-book Ares,
  X auth gate). The ROI of automated publishing on these platforms is negative
  once account-burn is factored — see `platforms/xiaohongshu.py` for the
  Q2 2026 research that ruled this out permanently.
- Reading public profile pages / public feeds is well below the risk threshold
  on every platform we currently care about (Indie Hackers, public GitHub
  profiles linked off our stargazers, public Product Hunt comments).

v0.1 ships one source: Indie Hackers milestones (English indie founder feed,
strongest fit with Solo Founder OS audience, no public API).
"""
from marketing_agent.signals.base import ScrapedItem, SignalSource
from marketing_agent.signals.storage import SignalStore
from marketing_agent.signals.ih_scraper import (
    IndieHackersScraper,
    IHScraperConfig,
    parse_milestone_item,
)

__all__ = [
    "ScrapedItem",
    "SignalSource",
    "SignalStore",
    "IndieHackersScraper",
    "IHScraperConfig",
    "parse_milestone_item",
]
