"""DSPy signatures — typed prompt declarations for content generation + critique.

Why DSPy? In late 2025-early 2026, DSPy + GEPA + BAML emerged as the way to
*compile* prompts against your own data instead of hand-tuning them.
Reported ~+20pp on structured tasks. With the engagement tracker we already
have, we can compile signatures against (post → engagement) pairs to
auto-tune the system prompt over time.

This module declares the signatures. Compilation happens later (v0.9):
    dspy.teleprompt.BootstrapFewShot.compile(generator, trainset=engagement_pairs)

For now, `compile_if_keyed()` is a no-op when DSPy isn't installed and
ANTHROPIC_API_KEY is unset. The signatures are usable as-is — a thin
wrapper over the existing generator's prompts, but with declarative I/O.

Status:
    - Signatures: DRAFTED here
    - Wiring into generator: v0.9 (needs LLM key for compilation)
    - Compilation against engagement DB: v0.9
"""
from __future__ import annotations
import os
from typing import Any


def is_dspy_available() -> bool:
    try:
        import dspy  # noqa: F401
        return True
    except ImportError:
        return False


# ─────────────────── signatures (declarative I/O) ───────────────────

def get_signatures() -> dict[str, Any]:
    """Return DSPy Signature classes if dspy is installed, else {}.

    Each signature names its inputs / outputs and a docstring that becomes
    the system prompt. DSPy compilation will mutate that prompt against
    training data later.
    """
    if not is_dspy_available():
        return {}
    import dspy

    class DraftPost(dspy.Signature):
        """Write a single platform-tuned marketing post for an indie OSS / AI
        project. Voice: technical, honest, no hype. Show, don't tell.
        Concrete details over abstract claims.
        """
        platform: str = dspy.InputField(desc="x | reddit | linkedin | dev_to | bluesky | mastodon")
        project_name: str = dspy.InputField()
        tagline: str = dspy.InputField()
        recent_changes: str = dspy.InputField(desc="Newline-separated commit headlines")
        target_audience: str = dspy.InputField(desc="Optional persona description")
        post_body: str = dspy.OutputField(desc="The post text. No preamble. "
                                                  "Respect platform char limits.")

    class CritiquePost(dspy.Signature):
        """Score a draft post 0-10 on quality. Penalize hype words, generic
        platitudes, missing concrete detail, length issues. 0-3: don't ship.
        4-6: meh. 7-8: solid. 9-10: ship.
        """
        platform: str = dspy.InputField()
        body: str = dspy.InputField()
        project_name: str = dspy.InputField()
        score: int = dspy.OutputField(desc="0-10 integer")
        reason: str = dspy.OutputField(desc="≤120 chars, why this score")

    class RewritePost(dspy.Signature):
        """Rewrite a low-scoring draft addressing specific critic feedback.
        Produce a fundamentally different draft, not a tweak.
        """
        platform: str = dspy.InputField()
        original_body: str = dspy.InputField()
        critic_reasons: str = dspy.InputField(
            desc="Newline-separated reasons the critic gave")
        rewritten_body: str = dspy.OutputField()

    class GenerateLaunchPlan(dspy.Signature):
        """Output a JSON launch plan for an indie project. Day 0 = launch day.
        HN posts at PH+10. No platform 3x/2 days. Mix posts/threads/reply_burst.
        """
        project_name: str = dspy.InputField()
        tagline: str = dspy.InputField()
        days: int = dspy.InputField()
        ph_launch_day: int = dspy.InputField(
            desc="Day offset where Product Hunt launch happens")
        plan_json: str = dspy.OutputField(desc="Strict JSON: {actions: [...]}")

    return {
        "DraftPost": DraftPost,
        "CritiquePost": CritiquePost,
        "RewritePost": RewritePost,
        "GenerateLaunchPlan": GenerateLaunchPlan,
    }


# ─────────────────── compilation (no-op stub for v0.8) ───────────────────

def compile_if_keyed(signature_name: str, *,
                       trainset: list[dict] | None = None) -> Any:
    """Future hook: compile a signature against engagement-tagged history.

    For v0.8 this is a no-op stub. v0.9 will:
      1. Pull (post, engagement) pairs from EngagementTracker
      2. Filter to high-engagement posts (top quartile by likes)
      3. dspy.teleprompt.BootstrapFewShot.compile() against them
      4. Persist the compiled program to disk

    Returns None when dspy missing OR no LLM key OR not yet implemented.
    """
    if not is_dspy_available():
        return None
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    sigs = get_signatures()
    if signature_name not in sigs:
        return None
    # v0.9: compile here
    return None


def list_signatures() -> list[str]:
    """For CLI / introspection. Always works (lists names, not classes)."""
    return ["DraftPost", "CritiquePost", "RewritePost", "GenerateLaunchPlan"]
