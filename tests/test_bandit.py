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
