"""Supervisor — Drafter → Critic → Rewriter loop.

Flagship architecture upgrade. Rather than "generate once, hope it's good,"
we draft N times with critic feedback steering each rewrite. Reflexion-lite,
implemented without LangGraph (zero new deps). Plays nicely with the rest:

  Iteration loop per (project, platform):
    1. Drafter   → produce a post (LLM if keyed, else template variant)
    2. Critic    → score it (heuristic always; LLM critic when keyed)
    3. If score < min_score AND iterations remaining:
         → Rewriter applies heuristic fixes (strip hype, trim length,
            de-shout caps) AND/OR re-prompts the LLM with critic feedback
    4. Track best-so-far; return best after max_iterations or early exit

Gracefully degrades:
  - Without ANTHROPIC_API_KEY: heuristic critic + template variants
    cycling through (emoji-led / question-led / stat-led) on rewrite
  - With key: LLM drafter + LLM critic + LLM rewriter

Why "lite" Reflexion? Real Reflexion stores per-task reflections across
runs. Our v0.6 runs the loop within a single generate() call. A future
v0.7 will persist reflections to SQLite so the agent learns across days.
"""
from __future__ import annotations
import os
import re
from dataclasses import dataclass, field
from typing import Optional

from marketing_agent.content import templates
from marketing_agent.critic import CritiqueResult, critique
from marketing_agent.logging import get_logger
from marketing_agent.reflexion_memory import ReflexionMemory
from marketing_agent.types import GenerationMode, Platform, Post, Project

log = get_logger(__name__)


@dataclass
class SupervisorResult:
    """Return value of supervise(). Contains the best post + full trace."""
    post: Post
    critique: CritiqueResult
    iterations: int
    history: list[tuple[Post, CritiqueResult]] = field(default_factory=list)


def _draft_attempt(project: Project, platform: Platform, *,
                     attempt: int, mode: GenerationMode,
                     subreddit: Optional[str] = None,
                     last_critique: Optional[CritiqueResult] = None,
                     reflexion_hint: str = "") -> Post:
    """Generate one draft, optionally informed by the last critique.

    Strategy:
      - attempt 0: standard generation (default variant for X = emoji-led)
      - attempt 1+: cycle to next variant (X variants exhaust at 3)
      - LLM mode: if last_critique provided, prepend a steering hint to
                   the user prompt (this is the "rewriter")
    """
    if mode == GenerationMode.TEMPLATE or not os.getenv("ANTHROPIC_API_KEY"):
        if platform == Platform.X:
            variants = templates.X_VARIANTS
            chosen = variants[attempt % len(variants)]
            return templates.render_x(project, variant=chosen)
        return templates.render(platform, project, subreddit=subreddit)

    # LLM mode: import locally so test runs without anthropic still work
    try:
        from anthropic import Anthropic
        from marketing_agent.content.generator import (
            _system_for, _user_prompt_for, _post_for,
        )
        client = Anthropic()
        system = _system_for(platform)
        user = _user_prompt_for(project, platform, subreddit=subreddit)
        # Reflexion: cross-session memory of past failures on this channel
        if reflexion_hint:
            user += "\n\n" + reflexion_hint
        # Within-call critique from the previous iteration
        if last_critique and last_critique.reasons:
            steer = (
                "\n\n[Reviewer feedback on the previous draft in this call to AVOID]:\n- "
                + "\n- ".join(last_critique.reasons)
                + "\nProduce a fundamentally different draft that addresses these."
            )
            user += steer
        resp = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=600,
            system=system, messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        text = text.strip('"').strip("'").strip()
        return _post_for(platform, text, project, subreddit=subreddit).with_count()
    except Exception as e:
        log.debug("LLM draft failed in supervisor, falling back: %s", e)
        return templates.render(platform, project, subreddit=subreddit)


_HYPE_PATTERN = re.compile(
    r"\b(revolutionary|game[- ]chang(?:ing|er)|cutting[- ]edge|next[- ]gen(?:eration)?|"
    r"world[- ]class|best[- ]in[- ]class|industry[- ]leading|state[- ]of[- ]the[- ]art|"
    r"supercharge|skyrocket|unleash|paradigm shift|disrupt(?:ive)?|harness the power|"
    r"unlock the power|elevate your|leverag(?:e|ing)|synergy|breakthrough innovation)\b",
    re.IGNORECASE,
)


def heuristic_rewrite(post: Post, crit: CritiqueResult) -> Post:
    """Apply deterministic fixes based on critic reasons. No API needed.

    - Strip hype words
    - De-shout (lowercase if >40% caps)
    - Trim to platform limit
    - Strip excess hashtags (>3)
    """
    body = post.body
    reasons_text = " ".join(crit.reasons).lower()

    if "hype words" in reasons_text:
        body = _HYPE_PATTERN.sub("", body)
        body = re.sub(r"\s{2,}", " ", body)
        body = re.sub(r"\s+([,.!?])", r"\1", body).strip()

    if "caps" in reasons_text:
        # Down-case the loud sentences while preserving sentence-initial caps
        body = ". ".join(s.strip().capitalize() if s.strip() else s
                          for s in body.split("."))

    if "hashtag" in reasons_text:
        # Keep first 3 hashtags only
        seen = 0
        def _trim(m):
            nonlocal seen
            seen += 1
            return m.group(0) if seen <= 3 else ""
        body = re.sub(r"#\w+", _trim, body)
        body = re.sub(r"\s{2,}", " ", body).strip()

    # Trim to limit if needed
    limits = {Platform.X: 280, Platform.BLUESKY: 300, Platform.MASTODON: 500}
    limit = limits.get(post.platform)
    if limit and len(body) > limit:
        body = body[:limit - 3].rstrip() + "..."

    return post.model_copy(update={"body": body, "char_count": len(body)})


def _try_agent_sdk(project: Project, platform: Platform, *,
                     mode: GenerationMode,
                     min_score: float, max_iterations: int,
                     subreddit: Optional[str] = None,
                     reflexion_hint: str = "") -> Optional[SupervisorResult]:
    """Use Anthropic's Claude Agent SDK 0.1.68+ when available.

    The official SDK ships managed loops, task budgets, file-system memory,
    and OTel tracing — replacing our hand-rolled loop with maintained code.
    Returns None if the SDK isn't installed OR no API key OR not LLM mode;
    caller should then fall back to the local supervise() loop.

    Why a wrapper rather than full migration? The SDK is in beta as of
    2026-04. We adopt it transparently when present, but the hand-rolled
    loop must keep working for users running template-only or older deps.
    """
    if mode == GenerationMode.TEMPLATE or not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        # The SDK's symbols moved a couple of times between alpha and 0.1.68.
        # We import lazily so missing/incompatible installs degrade silently.
        from claude_agent_sdk import (  # type: ignore
            ClaudeSDKClient, ClaudeAgentOptions,
        )
    except ImportError:
        return None

    try:
        from marketing_agent.content.generator import (
            _post_for, _system_for, _user_prompt_for,
        )
        opts = ClaudeAgentOptions(
            system_prompt=_system_for(platform),
            max_turns=max_iterations,
        )
        user_prompt = _user_prompt_for(project, platform, subreddit=subreddit)
        if reflexion_hint:
            user_prompt += "\n\n" + reflexion_hint
        with ClaudeSDKClient(options=opts) as agent:
            text = agent.complete(user_prompt) or ""
        post = _post_for(platform, text.strip(), project,
                          subreddit=subreddit).with_count()
        crit = critique(post, project_name=project.name,
                          min_score=min_score, use_llm=False)
        log.info("agent_sdk path used (single-shot)",
                  extra={"score": crit.score, "platform": platform.value})
        return SupervisorResult(
            post=post, critique=crit, iterations=1,
            history=[(post, crit)],
        )
    except Exception as e:
        log.debug("Agent SDK path failed, falling back: %s", e)
        return None


# Platforms where self-consistency-3 has the best ROI: short-form posts
# where a single chosen draft must carry the message. Per Q1 2026 paper,
# self-consistency-3 captures ~80% of Tree-of-Thoughts lift at 25% the cost.
_SHORT_FORM = (Platform.X, Platform.BLUESKY, Platform.MASTODON)


def _self_consistency_pick(project: Project, platform: Platform, *,
                              mode: GenerationMode, attempt: int,
                              subreddit: Optional[str], reflexion_hint: str,
                              project_name: str, min_score: float,
                              n: int = 3) -> tuple[Post, CritiqueResult]:
    """Generate `n` drafts at varied temperatures, return the highest-scoring.

    Falls back to a single draft if any sample fails. Used for short-form
    platforms (X / Bluesky / Mastodon) where a single output must carry.
    """
    candidates: list[tuple[Post, CritiqueResult]] = []
    for i in range(n):
        try:
            p = _draft_attempt(project, platform, attempt=attempt + i, mode=mode,
                                  subreddit=subreddit, reflexion_hint=reflexion_hint)
            c = critique(p, project_name=project_name,
                            min_score=min_score, use_llm=False)
            candidates.append((p, c))
        except Exception as e:
            log.debug("self-consistency sample %d failed: %s", i, e)
    if not candidates:
        # Should never happen since template fallback always returns something
        p = _draft_attempt(project, platform, attempt=attempt, mode=mode,
                              subreddit=subreddit, reflexion_hint=reflexion_hint)
        c = critique(p, project_name=project_name,
                        min_score=min_score, use_llm=False)
        return p, c
    # Pick the one with the highest critic score
    return max(candidates, key=lambda pc: pc[1].score)


def supervise(project: Project, platform: Platform, *,
                mode: GenerationMode = GenerationMode.HYBRID,
                max_iterations: int = 3,
                min_score: float = 7.0,
                subreddit: Optional[str] = None,
                use_llm_critic: bool = True,
                use_reflexion: bool = True,
                use_agent_sdk: bool = True,
                use_self_consistency: bool = False) -> SupervisorResult:
    """Drafter → Critic → Rewriter loop. Returns best-scoring post.

    Stops early as soon as a draft scores >= min_score. Otherwise runs
    max_iterations and returns the best one seen.

    use_reflexion: when True (default), prepend recent low-score patterns
    from this (project, platform) channel to the LLM prompt as a
    "things-to-avoid" hint, AND append every critique to reflexion memory.

    use_self_consistency: when True for short-form platforms (X / Bluesky /
    Mastodon), each iteration samples 3 drafts and picks the highest-scoring.
    Per Q1 2026 LLM research, captures ~80% of Tree-of-Thoughts lift at 25%
    the cost on short-form content. Off by default (3x LLM cost).
    """
    history: list[tuple[Post, CritiqueResult]] = []
    best_idx = 0
    last_crit: Optional[CritiqueResult] = None
    mem = ReflexionMemory() if use_reflexion else None
    hint = mem.steering_hint(project_name=project.name, platform=platform) \
            if mem else ""

    # First, try the official Claude Agent SDK if available + LLM-keyed
    if use_agent_sdk:
        sdk_result = _try_agent_sdk(
            project, platform, mode=mode,
            min_score=min_score, max_iterations=max_iterations,
            subreddit=subreddit, reflexion_hint=hint,
        )
        if sdk_result and sdk_result.critique.score >= min_score:
            if mem:
                mem.record(project_name=project.name, platform=platform,
                              score=sdk_result.critique.score,
                              reasons=sdk_result.critique.reasons,
                              body_preview=sdk_result.post.body[:200])
            return sdk_result

    short_form_self_consistency = (
        use_self_consistency and platform in _SHORT_FORM
    )
    for attempt in range(max_iterations):
        if short_form_self_consistency:
            post, _initial_crit = _self_consistency_pick(
                project, platform, mode=mode, attempt=attempt,
                subreddit=subreddit, reflexion_hint=hint,
                project_name=project.name, min_score=min_score, n=3,
            )
        else:
            post = _draft_attempt(
                project, platform, attempt=attempt, mode=mode,
                subreddit=subreddit, last_critique=last_crit,
                reflexion_hint=hint,
            )
        crit = critique(post, project_name=project.name,
                          min_score=min_score, use_llm=use_llm_critic)
        log.info("supervisor attempt %d: score=%.2f reasons=%s",
                  attempt, crit.score, crit.reasons,
                  extra={"attempt": attempt, "score": crit.score,
                          "platform": platform.value, "project": project.name})
        history.append((post, crit))

        if crit.score > history[best_idx][1].score:
            best_idx = len(history) - 1

        # Persist this attempt to reflexion memory (regardless of outcome —
        # high-scoring drafts seed positive patterns for future runs)
        if mem:
            mem.record(project_name=project.name, platform=platform,
                          score=crit.score, reasons=crit.reasons,
                          body_preview=post.body[:200])

        if crit.score >= min_score:
            break

        # Heuristic rewrite for the next iteration's seed
        rewritten = heuristic_rewrite(post, crit)
        if rewritten.body != post.body:
            r_crit = critique(rewritten, project_name=project.name,
                                min_score=min_score, use_llm=False)
            history.append((rewritten, r_crit))
            if r_crit.score > history[best_idx][1].score:
                best_idx = len(history) - 1
            if r_crit.score >= min_score:
                break
        last_crit = crit

    best_post, best_crit = history[best_idx]
    return SupervisorResult(
        post=best_post, critique=best_crit,
        iterations=len(history), history=history,
    )
