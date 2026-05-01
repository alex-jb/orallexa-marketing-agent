"""Tests for marketing_agent.vibex_trends — VibeX top-of-feed → TrendItem."""
from __future__ import annotations
import json
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from marketing_agent.vibex_trends import trending_vibex_projects


def _fake_urlopen(payload):
    fake = MagicMock()
    fake.read.return_value = json.dumps(payload).encode()
    fake.__enter__ = lambda s: s
    fake.__exit__ = lambda *a: None
    return fake


def test_unconfigured_returns_empty(monkeypatch):
    monkeypatch.delenv("SUPABASE_PERSONAL_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("VIBEX_PROJECT_REF", raising=False)
    monkeypatch.delenv("SUPABASE_PROJECT_REF", raising=False)
    assert trending_vibex_projects() == []


def test_renders_trenditems_from_rows(monkeypatch):
    monkeypatch.setenv("SUPABASE_PERSONAL_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("VIBEX_PROJECT_REF", "abc")
    fake = _fake_urlopen([
        {
            "project_id": "p1",
            "title": "RAG Recipe Coach",
            "tagline": "Cook from your fridge with Claude",
            "upvotes": 120,
            "plays": 543,
            "views": 1200,
            "stage": "Breakout",
            "created_at": "2026-04-29T12:00:00+00:00",
            "creator_name": "Maker A",
        },
    ])
    with patch("urllib.request.urlopen", return_value=fake):
        items = trending_vibex_projects(hours=48, limit=10)
    assert len(items) == 1
    it = items[0]
    assert it.source == "vibex"
    assert it.title == "RAG Recipe Coach"
    assert it.url == "https://www.vibexforge.com/project/p1"
    assert it.score == 120
    assert it.n_comments == 543
    assert "Breakout" in it.summary
    assert "Maker A" in it.summary
    assert "breakout" in it.tags
    assert "vibex" in it.tags


def test_falls_back_to_supabase_project_ref(monkeypatch):
    monkeypatch.setenv("SUPABASE_PERSONAL_ACCESS_TOKEN", "tok")
    monkeypatch.delenv("VIBEX_PROJECT_REF", raising=False)
    monkeypatch.setenv("SUPABASE_PROJECT_REF", "shared")
    fake = _fake_urlopen([])
    with patch("urllib.request.urlopen", return_value=fake) as m:
        trending_vibex_projects()
    req = m.call_args[0][0]
    assert "shared" in req.full_url


def test_handles_dict_response_shape(monkeypatch):
    monkeypatch.setenv("SUPABASE_PERSONAL_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("VIBEX_PROJECT_REF", "abc")
    fake = _fake_urlopen({"result": [{
        "project_id": "px", "title": "X", "tagline": "",
        "upvotes": 5, "plays": 10, "views": 30,
        "stage": "Seed", "created_at": None, "creator_name": "",
    }]})
    with patch("urllib.request.urlopen", return_value=fake):
        items = trending_vibex_projects()
    assert len(items) == 1
    assert items[0].title == "X"


def test_swallows_network_errors(monkeypatch):
    monkeypatch.setenv("SUPABASE_PERSONAL_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("VIBEX_PROJECT_REF", "abc")
    with patch("urllib.request.urlopen", side_effect=Exception("boom")):
        assert trending_vibex_projects() == []


def test_minimal_row_doesnt_crash(monkeypatch):
    """Rows with NULL/empty optional fields shouldn't blow up."""
    monkeypatch.setenv("SUPABASE_PERSONAL_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("VIBEX_PROJECT_REF", "abc")
    fake = _fake_urlopen([
        {"project_id": "p", "title": None, "tagline": None,
          "upvotes": None, "plays": None, "stage": None,
          "creator_name": None},
    ])
    with patch("urllib.request.urlopen", return_value=fake):
        items = trending_vibex_projects()
    assert len(items) == 1
    assert items[0].title == "(untitled)"
    assert items[0].score == 0
    # Stage defaults to Seed when null
    assert "seed" in items[0].tags
