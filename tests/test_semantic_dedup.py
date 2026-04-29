"""Tests for semantic_dedup. Uses local sentence-transformers when available;
falls back to "no embedding" path when not — both paths are exercised."""
from __future__ import annotations

import pytest

from marketing_agent.semantic_dedup import (
    SemanticDedupIndex, _cosine, _pack, _unpack, embed,
)
from marketing_agent.types import Platform


def test_pack_unpack_roundtrip():
    vec = [0.1, -0.2, 0.3, 0.4, -0.5]
    assert _unpack(_pack(vec)) == pytest.approx(vec, abs=1e-6)


def test_cosine_identical_is_one():
    assert _cosine([1.0, 0.0, 0.0], [1.0, 0.0, 0.0]) == pytest.approx(1.0)


def test_cosine_orthogonal_is_zero():
    assert _cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_empty_inputs_safe():
    assert _cosine([], []) == 0.0
    assert _cosine([1.0], []) == 0.0


def test_index_returns_empty_when_no_embedder(tmp_path, monkeypatch):
    """If sentence-transformers + voyage are both unavailable, behavior is
    'no near-dup detected' (False, None) — never crash."""
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    # Force local backend to "unavailable"
    import marketing_agent.semantic_dedup as sd
    monkeypatch.setattr(sd, "_embed_local", lambda _t: None)
    idx = SemanticDedupIndex(db_path=tmp_path / "db.sqlite")
    is_dup, near = idx.is_near_duplicate(
        "any body", project_name="x", platform=Platform.X)
    assert is_dup is False
    assert near is None


def test_add_and_nearest_with_synthetic_embedder(tmp_path, monkeypatch):
    """Bypass real embeddings — supply a deterministic stub so the SQL +
    cosine plumbing is fully exercised regardless of CI environment."""
    import marketing_agent.semantic_dedup as sd
    # Tiny fake embedder: hash-based 8-dim vector
    def _fake_embed(text):
        h = abs(hash(text))
        v = [(h >> (i * 4)) & 0xF for i in range(8)]
        norm = sum(x * x for x in v) ** 0.5 or 1.0
        return [x / norm for x in v]
    monkeypatch.setattr(sd, "_embed_voyage", lambda _t: None)
    monkeypatch.setattr(sd, "_embed_local", _fake_embed)

    idx = SemanticDedupIndex(db_path=tmp_path / "db.sqlite")
    assert idx.add("h1", "the quick brown fox", project_name="proj",
                    platform=Platform.X) is True
    near = idx.nearest("the quick brown fox", project_name="proj",
                         platform=Platform.X)
    assert len(near) == 1
    assert near[0]["similarity"] == pytest.approx(1.0, abs=1e-6)


def test_is_near_duplicate_threshold(tmp_path, monkeypatch):
    import marketing_agent.semantic_dedup as sd

    def _fake(text):
        # Identical for "A" / "A2" → similarity 1.0; different for "B".
        if text.startswith("A"):
            return [1.0, 0.0, 0.0]
        return [0.0, 1.0, 0.0]
    monkeypatch.setattr(sd, "_embed_voyage", lambda _t: None)
    monkeypatch.setattr(sd, "_embed_local", _fake)

    idx = SemanticDedupIndex(db_path=tmp_path / "db.sqlite")
    idx.add("h1", "A original", project_name="p", platform=Platform.X)
    is_dup, _ = idx.is_near_duplicate("A2 reposted", project_name="p",
                                         platform=Platform.X, threshold=0.92)
    assert is_dup is True
    is_dup, _ = idx.is_near_duplicate("B different", project_name="p",
                                         platform=Platform.X, threshold=0.92)
    assert is_dup is False
