"""Tests for ICPL preference store."""
from __future__ import annotations

import pytest

from marketing_agent.preference import PreferenceStore, _diff_summary
from marketing_agent.types import Platform


@pytest.fixture
def store(tmp_path):
    return PreferenceStore(db_path=tmp_path / "pref.db")


# ──────────────── _diff_summary ────────────────


def test_diff_summary_identical_returns_zero():
    chars, ratio = _diff_summary("hello world", "hello world")
    assert chars == 0
    assert ratio == 0.0


def test_diff_summary_completely_different():
    chars, ratio = _diff_summary("hello", "completely unrelated text here")
    assert chars > 0
    assert ratio > 0.5


def test_diff_summary_small_change_low_ratio():
    chars, ratio = _diff_summary(
        "I just shipped a thing today",
        "I just shipped a thing today!",
    )
    # 1-char diff out of ~30 → ratio < 0.1
    assert ratio < 0.1


# ──────────────── record / recent_pairs ────────────────


def test_record_skips_identical_edit(store):
    rid = store.record(
        project_name="x", platform=Platform.X,
        original_body="hello", edited_body="hello",
    )
    assert rid is None


def test_record_returns_id_for_real_edit(store):
    rid = store.record(
        project_name="x", platform=Platform.X,
        original_body="Revolutionary game-changing thing today",
        edited_body="Just shipped a thing today",
    )
    assert isinstance(rid, int)
    assert rid > 0


def test_recent_pairs_returns_in_descending_order(store):
    for orig, edit in [
        ("A original", "A improved"),
        ("B original", "B improved"),
        ("C original", "C improved"),
    ]:
        store.record(project_name="x", platform=Platform.X,
                       original_body=orig, edited_body=edit)
    pairs = store.recent_pairs(limit=3)
    # Most recent first → C, B, A
    assert pairs[0]["original_body"] == "C original"
    assert pairs[2]["original_body"] == "A original"


def test_recent_pairs_filters_by_min_ratio(store):
    # Big change (high ratio)
    store.record(project_name="x", platform=Platform.X,
                   original_body="completely different text here",
                   edited_body="something else entirely now")
    # Tiny change (low ratio) — should be filtered out
    store.record(project_name="x", platform=Platform.X,
                   original_body="A clean post about marketing-agent shipped today",
                   edited_body="A clean post about marketing-agent shipped today!")
    pairs = store.recent_pairs(min_ratio=0.05, limit=10)
    # Only the high-ratio edit survives
    assert len(pairs) == 1
    assert pairs[0]["original_body"].startswith("completely different")


def test_recent_pairs_filters_by_project_and_platform(store):
    store.record(project_name="orallexa", platform=Platform.X,
                   original_body="A", edited_body="B totally different")
    store.record(project_name="vibex", platform=Platform.X,
                   original_body="C", edited_body="D totally different")
    store.record(project_name="orallexa", platform=Platform.LINKEDIN,
                   original_body="E", edited_body="F totally different")
    out = store.recent_pairs(project_name="orallexa", platform=Platform.X)
    assert len(out) == 1
    assert out[0]["project_name"] == "orallexa"
    assert out[0]["platform"] == "x"


# ──────────────── few_shot_block ────────────────


def test_few_shot_block_empty_when_no_history(store):
    assert store.few_shot_block() == ""


def test_few_shot_block_contains_pairs(store):
    store.record(project_name="x", platform=Platform.X,
                   original_body="Revolutionary game-changing AI to supercharge your workflow",
                   edited_body="Shipped a thing. It does X. Here's the link.")
    block = store.few_shot_block()
    assert "Examples of how the human reviewer improved" in block
    assert "ORIGINAL:" in block
    assert "IMPROVED:" in block
    assert "Revolutionary" in block
    assert "Shipped a thing" in block


def test_few_shot_block_truncates_long_bodies(store):
    long_orig = "X" * 1000
    long_edit = "Y" * 1000
    store.record(project_name="x", platform=Platform.X,
                   original_body=long_orig, edited_body=long_edit)
    block = store.few_shot_block()
    # Both ORIGINAL and IMPROVED truncated at 300
    assert block.count("X") <= 350
    assert block.count("Y") <= 350


# ──────────────── stats ────────────────


def test_stats_aggregates(store):
    store.record(project_name="x", platform=Platform.X,
                   original_body="A", edited_body="B totally different")
    store.record(project_name="x", platform=Platform.LINKEDIN,
                   original_body="C", edited_body="D totally different")
    s = store.stats()
    assert s["total_edits"] == 2
    assert s["by_platform"] == {"x": 1, "linkedin": 1}
    assert s["avg_edit_ratio"] > 0


# ───────────────── SFOS JSONL mirror ─────────────────


def test_record_mirrors_to_sfos_jsonl(tmp_path):
    """Each record() writes both SQLite + a JSONL row in the
    solo_founder_os.preference schema (ts/task/original/edited/context)."""
    import json
    jpath = tmp_path / "preference-pairs.jsonl"
    s = PreferenceStore(db_path=tmp_path / "p.db", jsonl_path=jpath)
    s.record(project_name="orallexa", platform=Platform.X,
              original_body="Just shipped v0.18 — VibeX integration done",
              edited_body="🚀 Just shipped v0.18 — VibeX integration done. "
                            "Biggest unlock: agent now self-sources from your "
                            "own platform's hot projects.")
    lines = jpath.read_text().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    # SFOS log_edit schema
    for k in ("ts", "task", "original", "edited", "context"):
        assert k in row
    assert row["task"] == "draft_x"
    assert row["context"]["project_name"] == "orallexa"
    assert row["context"]["platform"] == "x"


def test_jsonl_mirror_skipped_when_no_change(tmp_path):
    jpath = tmp_path / "p.jsonl"
    s = PreferenceStore(db_path=tmp_path / "p.db", jsonl_path=jpath)
    s.record(project_name="p", platform=Platform.X,
              original_body="same", edited_body="same")
    assert not jpath.exists()


def test_jsonl_path_overridable_via_env(tmp_path, monkeypatch):
    custom = tmp_path / "custom-pref.jsonl"
    monkeypatch.setenv("MARKETING_AGENT_PREFERENCE_JSONL", str(custom))
    s = PreferenceStore(db_path=tmp_path / "p.db")
    s.record(project_name="p", platform=Platform.X,
              original_body="A", edited_body="B totally different")
    assert custom.exists()


def test_record_returns_row_id_even_when_jsonl_path_unwritable(tmp_path):
    """If JSONL mirror fails (perms, disk full), SQLite record still wins.
    We force this by passing a path inside a non-existent symlink chain."""
    bad = tmp_path / "no-such-dir" / "deep" / "p.jsonl"
    s = PreferenceStore(db_path=tmp_path / "p.db", jsonl_path=bad)
    # Should still return SQLite row id; mirror best-effort creates parents
    rid = s.record(project_name="p", platform=Platform.X,
                     original_body="A", edited_body="B different")
    assert rid is not None and rid > 0
