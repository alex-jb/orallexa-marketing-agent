"""Tests for the trends module — GitHub / HN / Reddit content ideation.

Strategy: mock urllib.request.urlopen for all HTTP. Verify each scraper
returns TrendItem objects with the right shape, falls back gracefully
on network failure, and aggregate() de-dupes by URL.
"""
from __future__ import annotations
import json
from unittest.mock import MagicMock, patch

import pytest

from marketing_agent.trends import (
    TrendItem, _http_get, aggregate, render_markdown,
    trending_github_repos, trending_hn_posts, trending_subreddit_posts,
)


def _fake_urlopen_response(body: str, *, status: int = 200) -> MagicMock:
    fake = MagicMock()
    fake.read.return_value = body.encode("utf-8")
    cm = MagicMock()
    cm.__enter__.return_value = fake
    cm.__exit__.return_value = False
    return cm


# ──────────────── _http_get ────────────────


def test_http_get_returns_body_on_success():
    with patch("urllib.request.urlopen",
                  return_value=_fake_urlopen_response("hello")):
        out = _http_get("https://example.com")
    assert out == "hello"


def test_http_get_returns_none_on_network_error():
    with patch("urllib.request.urlopen",
                  side_effect=ConnectionError("dns fail")):
        out = _http_get("https://example.com")
    assert out is None


# ──────────────── trending_github_repos ────────────────


def _gh_html_fixture() -> str:
    """Realistic-enough fragment of GitHub trending HTML."""
    return """
<html><body>
<article>
  <h2 class="h3 lh-condensed">
    <a href="/owner1/repo-one" class="Link">owner1/repo-one</a>
  </h2>
  <p class="col-9 color-fg-muted my-1 pr-4">
    First repo description, includes <span>HTML</span> tags.
  </p>
  <a href="/owner1/repo-one/stargazers">  12,345 </a>
</article>
<article>
  <h2 class="h3 lh-condensed">
    <a href="/owner2/repo-two">owner2/repo-two</a>
  </h2>
  <p class="col-9 color-fg-muted my-1 pr-4">Second repo.</p>
  <a href="/owner2/repo-two/stargazers"> 999 </a>
</article>
</body></html>
"""


def test_github_trending_parses_repos():
    with patch("urllib.request.urlopen",
                  return_value=_fake_urlopen_response(_gh_html_fixture())):
        out = trending_github_repos(language="python", limit=10)
    assert len(out) == 2
    first = out[0]
    assert first.source == "github"
    assert first.title == "owner1/repo-one"
    assert first.url == "https://github.com/owner1/repo-one"
    assert first.score == 12345
    assert "First repo description" in first.summary
    # HTML tags stripped from description
    assert "<span>" not in first.summary


def test_github_trending_returns_empty_on_network_failure():
    with patch("urllib.request.urlopen",
                  side_effect=ConnectionError("offline")):
        assert trending_github_repos() == []


# ──────────────── trending_hn_posts ────────────────


def _hn_response_fixture() -> str:
    return json.dumps({
        "hits": [
            {
                "objectID": "1234",
                "title": "Show HN: An AI marketing agent",
                "url": "https://example.com/showhn",
                "points": 187,
                "num_comments": 45,
                "_tags": ["story", "show_hn"],
            },
            {
                "objectID": "5678",
                "title": "Ask HN: What's the best agent framework in 2026?",
                "url": None,
                "points": 92,
                "num_comments": 30,
                "_tags": ["story", "ask_hn"],
            },
        ],
    })


def test_hn_trending_parses_hits():
    with patch("urllib.request.urlopen",
                  return_value=_fake_urlopen_response(_hn_response_fixture())):
        out = trending_hn_posts(query="agent", hours=72, min_points=50)
    assert len(out) == 2
    assert out[0].source == "hn"
    assert out[0].title.startswith("Show HN")
    assert out[0].score == 187
    assert out[0].n_comments == 45
    # When url is None, falls back to news.ycombinator.com/item?id=
    assert "news.ycombinator.com" in out[1].url


def test_hn_trending_returns_empty_on_bad_json():
    with patch("urllib.request.urlopen",
                  return_value=_fake_urlopen_response("not json")):
        assert trending_hn_posts() == []


# ──────────────── trending_subreddit_posts ────────────────


def _reddit_response_fixture(*, n_posts: int = 2) -> str:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).timestamp()
    children = [
        {
            "data": {
                "title": f"Post {i}",
                "permalink": f"/r/MachineLearning/comments/abc{i}/",
                "score": 50 + i * 10,
                "num_comments": 5 + i,
                "selftext": f"Body of post {i}",
                "created_utc": now,
            },
        }
        for i in range(n_posts)
    ]
    return json.dumps({"data": {"children": children}})


def test_reddit_trending_parses_posts():
    with patch("urllib.request.urlopen",
                  return_value=_fake_urlopen_response(_reddit_response_fixture(n_posts=3))):
        out = trending_subreddit_posts("MachineLearning", hours=24, min_score=25)
    assert len(out) == 3
    assert out[0].source == "reddit"
    assert "reddit.com" in out[0].url
    assert "MachineLearning" in out[0].tags


def test_reddit_trending_filters_below_min_score():
    """Posts below min_score are dropped."""
    from datetime import datetime, timezone
    body = json.dumps({"data": {"children": [
        {"data": {"title": "weak", "permalink": "/r/x/comments/1/",
                    "score": 5, "num_comments": 1,
                    "created_utc": datetime.now(timezone.utc).timestamp()}},
        {"data": {"title": "strong", "permalink": "/r/x/comments/2/",
                    "score": 100, "num_comments": 20,
                    "created_utc": datetime.now(timezone.utc).timestamp()}},
    ]}})
    with patch("urllib.request.urlopen",
                  return_value=_fake_urlopen_response(body)):
        out = trending_subreddit_posts("x", hours=24, min_score=25)
    assert len(out) == 1
    assert out[0].title == "strong"


# ──────────────── aggregate + render_markdown ────────────────


def test_aggregate_dedupes_by_url():
    """If the same URL appears in both GitHub trending and HN, it appears once."""
    same_url = "https://github.com/owner/repo"
    a = TrendItem(source="github", title="owner/repo", url=same_url, score=500)
    b = TrendItem(source="hn", title="Show HN: owner/repo", url=same_url, score=200)
    # Use mock to force aggregate's internal calls to return controlled values
    import marketing_agent.trends as tr
    with patch.object(tr, "trending_github_repos", return_value=[a]), \
         patch.object(tr, "trending_hn_posts", return_value=[b]), \
         patch.object(tr, "trending_subreddit_posts", return_value=[]):
        out = aggregate(github_languages=[""], subreddits=[])
    assert len(out) == 1


def test_aggregate_sorts_by_score_desc():
    import marketing_agent.trends as tr
    items = [
        TrendItem(source="github", title="low", url="https://x/1", score=10),
        TrendItem(source="github", title="high", url="https://x/2", score=100),
        TrendItem(source="github", title="mid", url="https://x/3", score=50),
    ]
    with patch.object(tr, "trending_github_repos", return_value=items), \
         patch.object(tr, "trending_hn_posts", return_value=[]), \
         patch.object(tr, "trending_subreddit_posts", return_value=[]):
        out = aggregate(github_languages=[""])
    assert [i.title for i in out] == ["high", "mid", "low"]


def test_render_markdown_handles_empty():
    md = render_markdown([])
    assert "Trends digest" in md
    assert "No trending items" in md


def test_render_markdown_groups_by_source():
    items = [
        TrendItem(source="github", title="a", url="https://x/a", score=100),
        TrendItem(source="hn", title="b", url="https://x/b", score=80, n_comments=20),
        TrendItem(source="reddit", title="c", url="https://x/c", score=50),
    ]
    md = render_markdown(items)
    assert "🐙 GitHub trending" in md
    assert "📰 Hacker News" in md
    assert "🤖 Reddit" in md
    assert "[a](https://x/a)" in md
    assert "[b](https://x/b)" in md
