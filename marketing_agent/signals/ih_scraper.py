"""Indie Hackers milestone scraper — uses Scrapling for Cloudflare bypass.

Architecture:
- Scrapling (BSD-3, D4Vinci/Scrapling, 48.9k stars) handles the Cloudflare
  bypass + browser fingerprint + retry logic. We don't reimplement any
  of that — we just configure it.
- HTML parsing is done with Scrapling's CSS/XPath adapters against the
  IH milestone feed page. The schema is stable enough that selectors can
  stay in this file; if IH redesigns, we fix here.
- Output: list[ScrapedItem] handed to SignalStore.append() for dedup.

We deliberately do NOT scrape login-required pages or profile data. The
public milestone feed is enough signal for marketing-agent context and
customer-discovery-agent pain-point clustering.

Install:
    pip install "scrapling[fetchers]"
    scrapling install  # downloads Camoufox browser bundle

Reference: https://github.com/D4Vinci/Scrapling
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from marketing_agent.signals.base import ScrapedItem, SignalSource


@dataclass
class IHScraperConfig:
    """Tunables. Defaults are conservative — public pages only, polite delays."""
    base_url: str = "https://www.indiehackers.com"
    feed_path: str = "/milestones"
    max_items: int = 50
    page_load_wait_sec: float = 2.5     # let lazy-loaded items render
    headless: bool = True                # IH does not need a visible browser
    user_agent: Optional[str] = None     # Scrapling picks a fresh fingerprint if None


def parse_milestone_item(raw_html_dict: dict) -> Optional[ScrapedItem]:
    """Pure function: one IH milestone DOM record → ScrapedItem.

    Receives a dict shape like:
        {
            "item_id": "stable-id-from-href",
            "title": "Hit $1k MRR this week",
            "url": "https://www.indiehackers.com/milestone/...",
            "author_handle": "@username",
            "posted_at": "2026-05-10T14:32:00Z",
            "votes": 42,
            "comments": 7,
            "tag": "ai",
            "body_snippet": "First..." (truncated to ~200 chars),
        }

    Defensive: returns None if required fields missing rather than crashing
    the entire batch. Fixture-tested.
    """
    item_id = raw_html_dict.get("item_id")
    title = raw_html_dict.get("title")
    url = raw_html_dict.get("url")
    if not (item_id and title and url):
        return None

    def _int_or_none(x) -> Optional[int]:
        if x is None:
            return None
        try:
            return int(x)
        except (TypeError, ValueError):
            return None

    return ScrapedItem(
        source="indie_hackers",
        item_id=str(item_id),
        title=str(title),
        url=str(url),
        author_handle=raw_html_dict.get("author_handle"),
        posted_at=raw_html_dict.get("posted_at"),
        votes=_int_or_none(raw_html_dict.get("votes")),
        comments=_int_or_none(raw_html_dict.get("comments")),
        tag=raw_html_dict.get("tag"),
        body_snippet=raw_html_dict.get("body_snippet"),
    )


def _extract_from_scrapling_page(page) -> list[dict]:
    """Pull milestone DOM records from a loaded Scrapling page object.

    Selectors are best-effort against the current IH layout (2026-05). If
    IH redesigns, this is the function to fix. Returns dict records ready
    for parse_milestone_item().

    NOTE: This function exercises the Scrapling adapter API and is not
    fixture-testable without a live page. Tests cover parse_milestone_item()
    independently.
    """
    records: list[dict] = []
    # Scrapling's CSS adapter, with adaptive auto-match if the class name changes
    for card in page.css(".milestone-card", auto_match=True):
        href = card.css_first("a.milestone-link::attr(href)")
        if not href:
            continue
        records.append({
            "item_id": href.rsplit("/", 1)[-1],
            "title": card.css_first(".milestone-title::text") or "",
            "url": f"https://www.indiehackers.com{href}",
            "author_handle": card.css_first(".milestone-author::text"),
            "posted_at": card.css_first(".milestone-time::attr(datetime)"),
            "votes": card.css_first(".milestone-votes::text"),
            "comments": card.css_first(".milestone-comments::text"),
            "tag": card.css_first(".milestone-tag::text"),
            "body_snippet": (card.css_first(".milestone-body::text") or "")[:200],
        })
    return records


class IndieHackersScraper(SignalSource):
    """Scraper for the IH public milestone feed."""

    source_name = "indie_hackers"

    def __init__(self, config: Optional[IHScraperConfig] = None):
        self.config = config or IHScraperConfig()

    def fetch(self, **_kwargs) -> list[ScrapedItem]:
        """Open the milestone feed, parse, return ScrapedItems.

        Lazy-imports scrapling so the module can be imported in test
        contexts that don't have the optional dep installed.
        """
        try:
            from scrapling.fetchers import StealthyFetcher
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "scrapling not installed. Run: pip install 'scrapling[fetchers]' "
                "&& scrapling install"
            ) from exc

        url = self.config.base_url + self.config.feed_path
        page = StealthyFetcher.fetch(
            url,
            headless=self.config.headless,
            network_idle=True,
            wait=int(self.config.page_load_wait_sec * 1000),
            user_agent=self.config.user_agent,
        )
        records = _extract_from_scrapling_page(page)
        items: list[ScrapedItem] = []
        for r in records[: self.config.max_items]:
            it = parse_milestone_item(r)
            if it is not None:
                items.append(it)
        return items
