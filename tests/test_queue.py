"""Tests for ApprovalQueue."""
from __future__ import annotations

import pytest

from marketing_agent import ApprovalQueue, Platform, Post


@pytest.fixture
def queue(tmp_path):
    return ApprovalQueue(root=tmp_path / "queue")


def test_submit_creates_pending_file(queue):
    post = Post(platform=Platform.X, body="hello").with_count()
    path = queue.submit(post, project_name="demo")
    assert path.exists()
    assert path.parent.name == "pending"


def test_load_roundtrip(queue):
    post = Post(platform=Platform.REDDIT, body="body text",
                title="A title", target="MachineLearning").with_count()
    path = queue.submit(post, project_name="demo")
    loaded, meta = queue.load(path)
    assert loaded.platform == post.platform
    assert loaded.body == post.body
    assert loaded.title == post.title
    assert loaded.target == post.target
    assert meta["project"] == "demo"


def test_mark_posted_moves_file(queue):
    post = Post(platform=Platform.X, body="hi").with_count()
    pending = queue.submit(post, project_name="demo")
    # Manually move to approved/ to simulate human approval
    approved = queue.root / "approved" / pending.name
    pending.rename(approved)
    new_path = queue.mark_posted(approved, external_id="https://x.com/abc")
    assert new_path.parent.name == "posted"
    assert not approved.exists()
    assert "posted_id" in new_path.read_text()


def test_mark_rejected_moves_file(queue):
    post = Post(platform=Platform.X, body="hi").with_count()
    pending = queue.submit(post, project_name="demo")
    rejected = queue.mark_rejected(pending)
    assert rejected.parent.name == "rejected"
    assert not pending.exists()


def test_list_approved_finds_files(queue):
    post = Post(platform=Platform.X, body="hi").with_count()
    pending = queue.submit(post, project_name="demo")
    pending.rename(queue.root / "approved" / pending.name)
    found = queue.list_approved()
    assert len(found) == 1
