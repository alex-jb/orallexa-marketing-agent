"""Tests for VariantBandit."""
from __future__ import annotations
import random

import pytest

from marketing_agent.bandit import VariantBandit, _squash


@pytest.fixture
def bandit(tmp_path):
    return VariantBandit(db_path=tmp_path / "bandit.db")


def test_single_arm_always_returns_it(bandit):
    assert bandit.choose(["x:emoji-led"]) == "x:emoji-led"


def test_choose_returns_one_of_provided(bandit):
    keys = ["x:emoji-led", "x:question-led", "x:stat-led"]
    for _ in range(20):
        assert bandit.choose(keys) in keys


def test_update_changes_posterior(bandit):
    bandit.update("x:emoji-led", reward=0.9)
    bandit.update("x:emoji-led", reward=0.9)
    bandit.update("x:emoji-led", reward=0.9)
    bandit.update("x:question-led", reward=0.1)
    stats = {s["variant_key"]: s for s in bandit.stats()}
    assert stats["x:emoji-led"]["mean"] > stats["x:question-led"]["mean"]


def test_thompson_concentrates_on_winner_over_time(bandit):
    """After many updates with a clear winner, choose() should pick it most of the time."""
    random.seed(42)
    # Train: emoji-led wins consistently
    for _ in range(100):
        bandit.update("x:emoji-led", reward=0.8)
        bandit.update("x:question-led", reward=0.05)
    picks = [bandit.choose(["x:emoji-led", "x:question-led"]) for _ in range(200)]
    winner_share = picks.count("x:emoji-led") / len(picks)
    assert winner_share > 0.85, f"Expected >85% winner picks, got {winner_share:.2%}"


def test_update_rejects_out_of_range_reward(bandit):
    with pytest.raises(ValueError):
        bandit.update("x:emoji-led", reward=1.5)
    with pytest.raises(ValueError):
        bandit.update("x:emoji-led", reward=-0.1)


def test_squash_is_monotonic_in_engagement():
    assert _squash(0) == 0
    assert _squash(50) == pytest.approx(0.5, abs=0.01)
    assert _squash(200) > _squash(50) > _squash(10)
    assert _squash(500) <= 1.0  # saturates near 1.0 for very high engagement


def test_update_from_engagement_returns_squashed(bandit):
    r = bandit.update_from_engagement("x:emoji-led", raw_engagement=50.0)
    assert 0.0 <= r <= 1.0
    assert r == pytest.approx(0.5, abs=0.01)


# ──────────────── report() — A/B winner + CI ────────────────


def test_report_empty_when_no_arms(bandit):
    assert bandit.report() == {}


def test_report_groups_arms_by_platform_prefix(bandit):
    bandit.update("x:emoji-led", reward=0.8)
    bandit.update("x:question-led", reward=0.3)
    bandit.update("reddit:value-first", reward=0.5)
    rep = bandit.report(min_pulls=1)
    assert "x" in rep
    assert "reddit" in rep
    assert len(rep["x"]["arms"]) == 2
    assert len(rep["reddit"]["arms"]) == 1


def test_report_picks_highest_mean_as_winner(bandit):
    for _ in range(5):
        bandit.update("x:emoji-led", reward=0.9)
        bandit.update("x:question-led", reward=0.1)
    rep = bandit.report(min_pulls=3)
    assert rep["x"]["winner"] == "x:emoji-led"


def test_report_no_winner_when_below_min_pulls(bandit):
    bandit.update("x:emoji-led", reward=0.9)  # only 1 pull
    rep = bandit.report(min_pulls=10)
    assert rep["x"]["winner"] is None


def test_report_includes_credible_intervals(bandit):
    for _ in range(20):
        bandit.update("x:emoji-led", reward=0.8)
    rep = bandit.report(min_pulls=3)
    arm = rep["x"]["arms"][0]
    assert 0.0 <= arm["ci95_low"] <= arm["mean"] <= arm["ci95_high"] <= 1.0


def test_report_flags_low_sample_warning(bandit):
    """Winner determined but n_pulls < 10 → sample_size_warning=True."""
    for _ in range(4):
        bandit.update("x:emoji-led", reward=0.9)
    rep = bandit.report(min_pulls=3)
    assert rep["x"]["winner"] == "x:emoji-led"
    assert rep["x"]["sample_size_warning"] is True


# ─────────────────────────────────────────────────────────────────────────
# v0.19.0 — predict() / predict_top_k() (JEPA-flavored predictor layer).
# Surface posterior stats to callers BEFORE LLM commit, instead of burying
# them inside Thompson sampling. See alex-brain world-models research note.
# ─────────────────────────────────────────────────────────────────────────


def test_predict_empty_list_returns_empty(bandit):
    assert bandit.predict([]) == []


def test_predict_unknown_arm_uses_uniform_prior(bandit):
    [d] = bandit.predict(["x:never-seen"])
    assert d["mean"] == 0.5  # Beta(1,1) prior
    assert d["n_pulls"] == 0
    assert d["alpha"] == 1.0
    assert d["beta"] == 1.0
    assert 0.0 <= d["ci95_low"] <= d["mean"] <= d["ci95_high"] <= 1.0


def test_predict_returns_sorted_by_mean_desc(bandit):
    bandit.update("x:emoji-led", reward=0.9)
    bandit.update("x:emoji-led", reward=0.9)
    bandit.update("x:emoji-led", reward=0.9)
    bandit.update("x:stat-led", reward=0.5)
    bandit.update("x:question-led", reward=0.1)
    bandit.update("x:question-led", reward=0.1)
    out = bandit.predict([
        "x:question-led", "x:emoji-led", "x:stat-led",
    ])
    means = [d["mean"] for d in out]
    assert means == sorted(means, reverse=True)
    assert out[0]["variant_key"] == "x:emoji-led"
    assert out[-1]["variant_key"] == "x:question-led"


def test_predict_includes_full_posterior_payload(bandit):
    bandit.update("x:stat-led", reward=0.7)
    [d] = bandit.predict(["x:stat-led"])
    for key in ("variant_key", "mean", "std", "ci95_low", "ci95_high",
                "n_pulls", "alpha", "beta"):
        assert key in d, f"predict() output missing key {key!r}"
    assert d["n_pulls"] == 1
    assert d["mean"] > 0.5  # one positive reward shifts away from prior


def test_predict_ci95_brackets_mean(bandit):
    bandit.update("x:stat-led", reward=0.6)
    bandit.update("x:stat-led", reward=0.6)
    [d] = bandit.predict(["x:stat-led"])
    assert d["ci95_low"] <= d["mean"] <= d["ci95_high"]
    assert d["ci95_low"] >= 0.0
    assert d["ci95_high"] <= 1.0


def test_predict_top_k_returns_k_variants(bandit):
    bandit.update("x:a", reward=0.9)
    bandit.update("x:b", reward=0.5)
    bandit.update("x:c", reward=0.1)
    top2 = bandit.predict_top_k(["x:a", "x:b", "x:c"], k=2)
    assert top2 == ["x:a", "x:b"]


def test_predict_top_k_ties_break_on_lower_std(bandit):
    """When two variants have equal mean, the more-tested one (lower std)
    should win the tiebreak — preference for confidence over noise."""
    # x:tested gets 4 pulls → narrow posterior at mean 0.5
    bandit.update("x:tested", reward=0.5)
    bandit.update("x:tested", reward=0.5)
    bandit.update("x:tested", reward=0.5)
    bandit.update("x:tested", reward=0.5)
    # x:untested has 0 pulls → wide posterior at mean 0.5
    [first] = bandit.predict_top_k(["x:tested", "x:untested"], k=1)
    assert first == "x:tested"


def test_predict_top_k_default_k_is_two(bandit):
    bandit.update("x:a", reward=0.9)
    bandit.update("x:b", reward=0.5)
    bandit.update("x:c", reward=0.1)
    out = bandit.predict_top_k(["x:a", "x:b", "x:c"])
    assert len(out) == 2


def test_predict_top_k_handles_k_greater_than_arms(bandit):
    bandit.update("x:a", reward=0.5)
    out = bandit.predict_top_k(["x:a"], k=10)
    assert out == ["x:a"]
