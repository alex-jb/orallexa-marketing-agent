"""Tests for ApprovalQueue."""
from __future__ import annotations

import pytest

from marketing_agent import ApprovalQueue, Platform, Post


@pytest.fixture
def queue(tmp_path):
    return ApprovalQueue(root=tmp_path / "queue")


def test_submit_creates_pending_file(queue):
    post = Post(platform=Platform.X, body="hello").with_count()
    path = queue.submit(post, project_name="demo", gate=False)
    assert path.exists()
    assert path.parent.name == "pending"


def test_load_roundtrip(queue):
    post = Post(platform=Platform.REDDIT, body="body text",
                title="A title", target="MachineLearning").with_count()
    path = queue.submit(post, project_name="demo", gate=False)
    loaded, meta = queue.load(path)
    assert loaded.platform == post.platform
    assert loaded.body == post.body
    assert loaded.title == post.title
    assert loaded.target == post.target
    assert meta["project"] == "demo"


def test_mark_posted_moves_file(queue):
    post = Post(platform=Platform.X, body="hi").with_count()
    pending = queue.submit(post, project_name="demo", gate=False)
    # Manually move to approved/ to simulate human approval
    approved = queue.root / "approved" / pending.name
    pending.rename(approved)
    new_path = queue.mark_posted(approved, external_id="https://x.com/abc")
    assert new_path.parent.name == "posted"
    assert not approved.exists()
    assert "posted_id" in new_path.read_text()


def test_mark_rejected_moves_file(queue):
    post = Post(platform=Platform.X, body="hi").with_count()
    pending = queue.submit(post, project_name="demo", gate=False)
    rejected = queue.mark_rejected(pending)
    assert rejected.parent.name == "rejected"
    assert not pending.exists()


def test_list_approved_finds_files(queue):
    post = Post(platform=Platform.X, body="hi").with_count()
    pending = queue.submit(post, project_name="demo", gate=False)
    pending.rename(queue.root / "approved" / pending.name)
    found = queue.list_approved()
    assert len(found) == 1


def test_gate_routes_low_quality_post_to_rejected(queue, monkeypatch):
    """Hype-laden post should auto-reject via critic."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    post = Post(platform=Platform.X,
                body="Revolutionary game-changing cutting-edge supercharge "
                     "paradigm shift unlock the power of synergy today.").with_count()
    path = queue.submit(post, project_name="demo", gate=True)
    assert path.parent.name == "rejected"
    text = path.read_text()
    assert "gate_note:" in text
    assert "auto-rejected" in text


def test_gate_passes_clean_post_to_pending(queue, monkeypatch):
    """Clean post lands in pending/. Heuristic-only mode (no LLM key)."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    post = Post(
        platform=Platform.X,
        body="Shipped marketing-agent v0.5: critic + semantic dedup + "
             "retries + structured logs. 90+ tests. https://github.com/x/y",
    ).with_count()
    path = queue.submit(post, project_name="demo", gate=True)
    assert path.parent.name == "pending"
