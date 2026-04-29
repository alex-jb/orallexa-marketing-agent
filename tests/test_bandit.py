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
