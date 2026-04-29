"""Critic agent — score draft posts before they hit the queue.

Why? LLM (and templates) sometimes produce content that's technically
valid but obviously bad: "revolutionary game-changing AI-powered solution"
slop, drafts that overshoot platform char limits, drafts with no concrete
detail, missing URL when the project has one.

Two-tier scoring:
  1. Heuristic (always): O(ms), deterministic, no API calls.
     Penalizes: hype words, char-limit overshoots, no concrete numbers,
     missing URL when expected, all-caps shouting.
  2. LLM (optional, when ANTHROPIC_API_KEY is set): asks Claude Haiku for
     a 1-10 score + 1-line reason. Adds ~$0.0005/post.

Drafts below `min_score` are routed to queue/rejected/ automatically with
the reason recorded as YAML frontmatter, so the user can scan them later
without them clogging pending/.

Reflexion-style: every reject is logged so the next generation pass can
read past failure modes and steer away from them. (v0.5 stores the log;
v0.6 will read it back into the system prompt.)
"""
from __future__ import annotations
import os
import re
from dataclasses import dataclass, field
from typing import Optional

from marketing_agent.logging import get_logger
from marketing_agent.types import Platform, Post

log = get_logger(__name__)


# Hype/buzz words that scream "AI-generated marketing slop". Penalized hard.
_BANNED_PHRASES = (
    "revolutionary", "game-changing", "game-changer", "cutting-edge",
    "next-generation", "next-gen", "synergy", "leverage", "leveraging",
    "unleash", "unlock the power", "transform your", "harness the power",
    "world-class", "best-in-class", "industry-leading", "state-of-the-art",
    "elevate your", "supercharge", "skyrocket", "breakthrough innovation",
    "paradigm shift", "disrupt", "disruptive",
)

# Soft penalty: salesy CTAs that don't fit a build-in-public voice.
_SOFT_PENALTY = (
    "click the link", "sign up now", "limited time", "don't miss out",
    "act now", "today only", "exclusive offer",
)


_PLATFORM_LIMITS: dict[Platform, int] = {
    Platform.X: 280,
    Platform.BLUESKY: 300,
    Platform.MASTODON: 500,
    Platform.LINKEDIN: 3000,
    Platform.REDDIT: 40000,
    Platform.DEV_TO: 100000,
}

# Single source of truth for the auto-reject threshold.
# Used by both the critic itself AND queue.submit()'s gate. Override one
# place and the other follows. Tuned by observation: scores at or below 4.0
# are unfailingly bad; 4.5+ is occasionally salvageable; 7+ is shippable.
DEFAULT_MIN_SCORE = 4.0


@dataclass
class CritiqueResult:
    """Output of the critic. score in [0, 10]."""
    score: float
    reasons: list[str] = field(default_factory=list)
    auto_reject: bool = False


def heuristic_score(post: Post) -> CritiqueResult:
    """Fast, deterministic critic. Always runs; no API calls.

    Returns a score in [0, 10] and a list of reasons that lowered it.
    auto_reject=True when score < 4 (strong signal something's wrong).
    """
    score = 10.0
    reasons: list[str] = []
    body_lower = post.body.lower()

    # 1. Hype/banned words — heavy penalty (2.5 per hit, cap at 3 words = -7.5)
    hits = [p for p in _BANNED_PHRASES if p in body_lower]
    if hits:
        score -= 2.5 * min(len(hits), 3)
        reasons.append(f"hype words: {', '.join(hits[:3])}")

    soft_hits = [p for p in _SOFT_PENALTY if p in body_lower]
    if soft_hits:
        score -= 0.5 * min(len(soft_hits), 3)
        reasons.append(f"salesy CTA: {', '.join(soft_hits[:2])}")

    # 2. Char limit overshoot
    limit = _PLATFORM_LIMITS.get(post.platform)
    if limit and len(post.body) > limit:
        overshoot = len(post.body) - limit
        score -= min(3.0, overshoot / 50)  # 50 chars over = -1, capped at -3
        reasons.append(f"over {post.platform.value} limit by {overshoot} chars")

    # 3. Too short — likely incomplete or wrong (escalates with severity)
    if len(post.body) < 20:
        score -= 7.0
        reasons.append(f"way too short ({len(post.body)} chars)")
    elif len(post.body) < 30:
        score -= 3.0
        reasons.append(f"too short ({len(post.body)} chars)")

    # 4. All-caps shouting (>40% uppercase letters in a >30-char run)
    letters = [c for c in post.body if c.isalpha()]
    if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.4:
        if len(post.body) > 30:
            score -= 1.5
            reasons.append("excessive caps")

    # 5. Excessive emoji (>5)
    emoji_count = sum(1 for c in post.body if ord(c) > 0x2600)
    if emoji_count > 5:
        score -= 1.0
        reasons.append(f"too many emoji ({emoji_count})")

    # 6. Hashtag spam (>3 on X/LinkedIn — Reddit doesn't use hashtags)
    if post.platform in (Platform.X, Platform.LINKEDIN):
        hashtags = re.findall(r"#\w+", post.body)
        if len(hashtags) > 3:
            score -= 1.0
            reasons.append(f"hashtag spam ({len(hashtags)})")

    score = max(0.0, min(10.0, score))
    return CritiqueResult(
        score=round(score, 2),
        reasons=reasons,
        auto_reject=score < DEFAULT_MIN_SCORE,
    )


def llm_score(post: Post, *, project_name: str = "") -> Optional[CritiqueResult]:
    """LLM-based critic. Routes through solo_founder_os.AnthropicClient so
    token usage flows into the cross-agent cost-audit report. Returns None
    if no key set or any failure."""
    try:
        from solo_founder_os.anthropic_client import (
            AnthropicClient, DEFAULT_HAIKU_MODEL,
        )
        from marketing_agent.cost import USAGE_LOG_PATH
        client = AnthropicClient(usage_log_path=USAGE_LOG_PATH)
        if not client.configured:
            return None
        prompt = (
            f"You are a brutal social-media editor. A solo OSS founder is "
            f"about to post the following on {post.platform.value}. Project "
            f"name: {project_name or '(unspecified)'}.\n\n"
            f"---\n{post.body}\n---\n\n"
            f"Output two lines, exactly this format:\n"
            f"SCORE: <0-10 integer>\n"
            f"REASON: <≤120 chars, why this score>\n\n"
            f"Score 0-3: don't ship it. 4-6: meh. 7-8: solid. 9-10: ship.\n"
            f"Penalize: hype words, generic platitudes, no concrete detail, "
            f"forced humor, hashtag spam, length issues."
        )
        resp, err = client.messages_create(
            model=DEFAULT_HAIKU_MODEL, max_tokens=120,
            messages=[{"role": "user", "content": prompt}],
        )
        if err is not None or resp is None:
            log.debug("llm_score messages_create returned error: %s", err)
            return None
        text = AnthropicClient.extract_text(resp)
        m_score = re.search(r"SCORE:\s*(\d+(?:\.\d+)?)", text)
        m_reason = re.search(r"REASON:\s*(.+)", text)
        if not m_score:
            return None
        score = float(m_score.group(1))
        reason = m_reason.group(1).strip()[:200] if m_reason else "(no reason given)"
        return CritiqueResult(
            score=round(score, 2),
            reasons=[f"llm: {reason}"],
            auto_reject=score < DEFAULT_MIN_SCORE,
        )
    except Exception as e:
        log.debug("llm_score failed (silent fallback): %s", e)
        return None


def critique(post: Post, *, project_name: str = "",
              min_score: float = DEFAULT_MIN_SCORE,
              use_llm: bool = True,
              use_ensemble: bool = True) -> CritiqueResult:
    """Combined critic: heuristic + LLM (single or ensemble) blended.

    Tier ladder (highest→lowest):
      1. Ensemble (Claude + GPT-5 + Gemini) when use_ensemble + ≥2 keys + litellm
      2. Single Claude critic when ANTHROPIC_API_KEY set (or single key in ensemble)
      3. Heuristic only — always available, no key needed

    Combination rule: take min of all available scores (harshest wins).
    auto_reject: heuristic always counts; ensemble votes by majority,
    single LLM by its own threshold.
    """
    h = heuristic_score(post)
    if not use_llm:
        h.auto_reject = h.score < min_score
        return h

    # Try ensemble first if requested and ≥2 providers configured
    if use_ensemble:
        try:
            from marketing_agent.ensemble_critic import (
                _configured_providers, ensemble_score,
            )
            if len(_configured_providers()) >= 2:
                ens = ensemble_score(post, project_name=project_name,
                                          min_score=min_score)
                if ens is not None:
                    combined = CritiqueResult(
                        score=round(min(h.score, ens.score), 2),
                        reasons=h.reasons + ens.reasons,
                        auto_reject=(min(h.score, ens.score) < min_score
                                       or ens.auto_reject),
                    )
                    return combined
        except Exception:
            pass

    # Fall back to single Claude critic (v0.10 behavior)
    llm = llm_score(post, project_name=project_name)
    if llm is None:
        h.auto_reject = h.score < min_score
        return h
    return CritiqueResult(
        score=round(min(h.score, llm.score), 2),
        reasons=h.reasons + llm.reasons,
        auto_reject=min(h.score, llm.score) < min_score,
    )
