"""tests/test_signals.py
─────────────────────────────────────────────────────────────
Scraping infrastructure tests — fixture-only, no network.

The Scrapling-driven scrape itself can't be unit-tested without a
live IH page (and we don't want to hit IH from CI). Tests cover:
- ScrapedItem dataclass round-trip
- SignalStore dedup on (source, item_id)
- IH parse_milestone_item() handles full + missing-field records
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from marketing_agent.signals import (
    ScrapedItem,
    SignalStore,
    IndieHackersScraper,
    IHScraperConfig,
    parse_milestone_item,
)


# ════════════════════════════════════════════════════════════════════
# ScrapedItem dataclass
# ════════════════════════════════════════════════════════════════════


def test_scraped_item_to_dict_and_back():
    """Round-trip through dict+JSON (used by storage.append)."""
    it = ScrapedItem(
        source="indie_hackers",
        item_id="ms-12345",
        title="Hit $5k MRR",
        url="https://www.indiehackers.com/milestone/ms-12345",
        author_handle="@alice",
        posted_at="2026-05-10T14:00:00Z",
        votes=42,
        comments=7,
        tag="saas",
    )
    d = it.to_dict()
    s = json.dumps(d, ensure_ascii=False)
    parsed = json.loads(s)
    assert parsed["source"] == "indie_hackers"
    assert parsed["votes"] == 42
    assert parsed["title"] == "Hit $5k MRR"


# ════════════════════════════════════════════════════════════════════
# SignalStore dedup
# ════════════════════════════════════════════════════════════════════


def test_store_dedups_on_item_id(tmp_path: Path):
    store = SignalStore(root=tmp_path)
    items_a = [
        ScrapedItem(source="indie_hackers", item_id="a1", title="A", url="https://x/a1"),
        ScrapedItem(source="indie_hackers", item_id="a2", title="B", url="https://x/a2"),
    ]
    assert store.append(items_a) == 2

    # second call with same items: dedup → 0 new rows
    assert store.append(items_a) == 0

    # adding 1 new + 1 dup: only the new one
    items_b = [
        ScrapedItem(source="indie_hackers", item_id="a2", title="B", url="https://x/a2"),
        ScrapedItem(source="indie_hackers", item_id="a3", title="C", url="https://x/a3"),
    ]
    assert store.append(items_b) == 1

    # file has 3 lines total
    p = store.path_for("indie_hackers")
    lines = p.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3


def test_store_rejects_mixed_sources():
    store = SignalStore(root=Path(tempfile.mkdtemp()))
    bad = [
        ScrapedItem(source="indie_hackers", item_id="a1", title="A", url="https://x/a1"),
        ScrapedItem(source="product_hunt", item_id="b1", title="B", url="https://x/b1"),
    ]
    try:
        store.append(bad)
        assert False, "expected ValueError on mixed sources"
    except ValueError as exc:
        assert "mixed sources" in str(exc).lower()


# ════════════════════════════════════════════════════════════════════
# IH milestone parser
# ════════════════════════════════════════════════════════════════════


def _full_record() -> dict:
    return {
        "item_id": "milestone-987",
        "title": "Hit $10k MRR after 18 months",
        "url": "https://www.indiehackers.com/milestone/milestone-987",
        "author_handle": "@indiebob",
        "posted_at": "2026-05-11T09:30:00Z",
        "votes": "55",            # IH renders as text — must be str-coerced
        "comments": "12",
        "tag": "ai",
        "body_snippet": "Took longer than expected. Here's what worked...",
    }


def test_parse_full_record():
    r = parse_milestone_item(_full_record())
    assert r is not None
    assert r.source == "indie_hackers"
    assert r.item_id == "milestone-987"
    assert r.title.startswith("Hit $10k")
    assert r.votes == 55       # int-coerced from "55"
    assert r.comments == 12
    assert r.tag == "ai"


def test_parse_missing_required_returns_none():
    """Record without item_id / title / url is dropped (defensive)."""
    incomplete = {"title": "A milestone"}        # no item_id, no url
    assert parse_milestone_item(incomplete) is None

    incomplete2 = {"item_id": "x", "url": "https://x"}  # no title
    assert parse_milestone_item(incomplete2) is None


def test_parse_handles_non_int_votes():
    r = _full_record()
    r["votes"] = "abc"     # garbage
    r["comments"] = None   # null
    parsed = parse_milestone_item(r)
    assert parsed is not None
    assert parsed.votes is None
    assert parsed.comments is None


# ════════════════════════════════════════════════════════════════════
# IndieHackersScraper config
# ════════════════════════════════════════════════════════════════════


def test_scraper_default_config():
    s = IndieHackersScraper()
    assert s.source_name == "indie_hackers"
    assert s.config.base_url == "https://www.indiehackers.com"
    assert s.config.headless is True
    assert s.config.max_items == 50


def test_scraper_custom_config():
    cfg = IHScraperConfig(max_items=10, headless=False, page_load_wait_sec=5.0)
    s = IndieHackersScraper(config=cfg)
    assert s.config.max_items == 10
    assert s.config.headless is False
    assert s.config.page_load_wait_sec == 5.0


def test_scraper_fetch_raises_clear_error_without_scrapling(monkeypatch):
    """Without scrapling installed, .fetch() should raise a clear hint."""
    import builtins
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("scrapling"):
            raise ImportError("No module named 'scrapling'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    s = IndieHackersScraper()
    try:
        s.fetch()
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "scrapling" in str(exc).lower()
        assert "pip install" in str(exc).lower()
