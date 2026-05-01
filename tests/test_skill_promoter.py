"""Tests for Voyager-style auto-skill promotion."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path


from marketing_agent.engagement import EngagementTracker
from marketing_agent.memory import PostMemory
from marketing_agent.skill_promoter import (
    _opening_pattern, _slugify, _structural_fingerprint,
    find_top_quartile_posts, promote,
)
from marketing_agent.types import Engagement, Platform, Post


# ──────────────── helpers ────────────────


def _seed_post(db: Path, *, ext_id: str, body: str, peak_likes: int,
                  platform: Platform = Platform.X) -> None:
    """Insert one post with known engagement into shared SQLite DB."""
    mem = PostMemory(db_path=db)
    p = Post(platform=platform, body=body).with_count()
    mem.record(p, project_name="t", external_id=ext_id)
    eng = EngagementTracker(db_path=db)
    eng.record(Engagement(
        platform=platform, post_id=ext_id,
        metric="like", count=peak_likes,
        timestamp=datetime.now(timezone.utc),
    ))


# ──────────────── unit: _slugify ────────────────


def test_slugify_basic():
    assert _slugify("Hello World!") == "hello-world"
    assert _slugify("X / Y / Z") == "x-y-z"


def test_slugify_caps_at_60():
    s = _slugify("a" * 200)
    assert len(s) <= 60


# ──────────────── unit: _opening_pattern ────────────────


def test_opening_pattern_emoji_led():
    assert _opening_pattern("🛠 Ship it") == "emoji-led"


def test_opening_pattern_question_led():
    assert _opening_pattern("Why does this work?") == "question-led"


def test_opening_pattern_stat_led():
    assert _opening_pattern("3 changes today.") == "stat-led"


def test_opening_pattern_build_in_public():
    assert _opening_pattern("Just shipped v0.12 today") == "build-in-public-led"


def test_opening_pattern_narrative():
    assert _opening_pattern("Hello to all of you") == "narrative-led"


# ──────────────── unit: _structural_fingerprint ────────────────


def test_fingerprint_counts_hashtags():
    f = _structural_fingerprint("#ai #ml hello")
    assert f["hashtag_count"] == 2


def test_fingerprint_detects_url():
    f = _structural_fingerprint("post body https://x.com/y")
    assert f["has_url"] is True


def test_fingerprint_detects_code_block():
    f = _structural_fingerprint("post body\n```bash\nls\n```\n")
    assert f["has_code_block"] is True


# ──────────────── find_top_quartile_posts ────────────────


def test_find_top_quartile_returns_empty_for_missing_db(tmp_path):
    out = find_top_quartile_posts(db_path=tmp_path / "nope.db")
    assert out == []


def test_find_top_quartile_skips_when_too_few_samples(tmp_path):
    db = tmp_path / "h.db"
    _seed_post(db, ext_id="a", body="post1", peak_likes=10)
    _seed_post(db, ext_id="b", body="post2", peak_likes=20)
    out = find_top_quartile_posts(db_path=db, min_samples=4)
    assert out == []


def test_find_top_quartile_returns_top_25_pct(tmp_path):
    db = tmp_path / "h.db"
    likes = [5, 10, 15, 20, 100, 200]  # 6 posts
    for i, peak in enumerate(likes):
        _seed_post(db, ext_id=f"e{i}", body=f"post{i}", peak_likes=peak)
    out = find_top_quartile_posts(db_path=db, min_samples=4)
    # Cutoff is the 75th-percentile of [5,10,15,20,100,200] = 100. So
    # both 100 and 200 are at-or-above cutoff → 2 posts qualify.
    assert len(out) >= 1
    peaks = [r["peak"] for r in out]
    assert max(peaks) >= 100


# ──────────────── promote ────────────────


def test_promote_writes_skill_file(tmp_path):
    db = tmp_path / "h.db"
    likes = [5, 10, 15, 20, 200]
    for i, peak in enumerate(likes):
        _seed_post(db, ext_id=f"e{i}",
                      body=f"🛠 Test post {i} on the agent. "
                            f"https://github.com/x/y",
                      peak_likes=peak)
    out_dir = tmp_path / "skills" / "learned"
    written = promote(db_path=db, skill_dir=out_dir, min_samples=4)
    assert len(written) >= 1
    # Files must contain the structural-fingerprint scaffolding
    for path in written:
        text = path.read_text()
        assert "Auto-promoted skill" in text
        assert "Structural fingerprint" in text
        assert "Opening pattern" in text


def test_promote_idempotent(tmp_path):
    db = tmp_path / "h.db"
    likes = [5, 10, 15, 20, 200]
    for i, peak in enumerate(likes):
        _seed_post(db, ext_id=f"e{i}", body=f"post {i}", peak_likes=peak)
    out_dir = tmp_path / "skills"
    a = promote(db_path=db, skill_dir=out_dir, min_samples=4)
    b = promote(db_path=db, skill_dir=out_dir, min_samples=4)
    # Same files written both times (replaced, not duplicated)
    assert sorted(a) == sorted(b)
    assert len(list(out_dir.glob("*.md"))) == len(a)


def test_promote_returns_empty_when_no_data(tmp_path):
    out_dir = tmp_path / "skills"
    written = promote(db_path=tmp_path / "missing.db", skill_dir=out_dir)
    assert written == []
