"""
luminaries.py — wave-borrow trigger registry for 20 AI luminaries (2026 H1).

Wires `render_wave_borrow_post()` (viral_patterns.py:191) to a fixed list of
high-signal X handles. When one of them posts a pain point / public ask /
controversial take, marketing-agent's listener can match against this list
and auto-draft a wave-borrow response within 24h.

Source pattern: Karpathy's CLAUDE.md frustration (2026-01-26) → multica-ai
shipped a 65-line response 24h later → 100k+ stars in 7 days. This is the
canonical 2026 H1 wave-borrow signature.

The list is intentionally short and high-signal. Adding more reduces SLA
(we cannot maintain 24h response across 50 handles); fewer reduces hit rate.

Status: DATA layer only. Listener cron + draft trigger not yet wired —
shipping the registry first so it's stable before the consumer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Tier = Literal["foundation", "vc", "indie", "research"]


@dataclass(frozen=True)
class Luminary:
    """Fixed pointer to one AI luminary worth wave-borrowing from in 2026 H1."""

    handle: str  # X handle WITHOUT the @
    name: str
    tier: Tier
    relevance_themes: tuple[str, ...]  # what we'd respond to
    why_listed: str  # one-line case for inclusion


# 20 high-signal AI luminaries — calibrated to Alex's portfolio surface area
# (agentic infra / calibration-honesty / solo-founder / multi-agent / quant).
# Order = priority ranking when SLA is contested.
LUMINARIES_2026_H1: tuple[Luminary, ...] = (
    # Tier 1: foundation labs / cited weekly in Alex's brief
    Luminary(
        handle="karpathy",
        name="Andrej Karpathy",
        tier="foundation",
        relevance_themes=("agentic engineering", "Claude Code", "LLM education"),
        why_listed="2026-05 joined Anthropic; vibe→agentic frame is Alex's positioning",
    ),
    Luminary(
        handle="DarioAmodei",
        name="Dario Amodei",
        tier="foundation",
        relevance_themes=("alignment", "Anthropic prod", "self-coding flywheel"),
        why_listed="80% Anthropic code Claude-authored mirrors Alex's 11-agent SFOS posture",
    ),
    Luminary(
        handle="sama",
        name="Sam Altman",
        tier="foundation",
        relevance_themes=("OpenAI direction", "GPT-5.x", "inference compute"),
        why_listed="public statements move calendar; wave-borrow window is narrow",
    ),
    Luminary(
        handle="gdb",
        name="Greg Brockman",
        tier="foundation",
        relevance_themes=("agents", "ChatGPT+Codex merger", "product strategy"),
        why_listed="2026-05-16 took OpenAI product strategy; agent-first frame is on",
    ),
    Luminary(
        handle="ylecun",
        name="Yann LeCun",
        tier="research",
        relevance_themes=("world models", "LLM dead end", "AMI Labs"),
        why_listed="contrarian $1.03B seed 2026-03; loud disagreement = wave-borrow gold",
    ),
    Luminary(
        handle="miramurati",
        name="Mira Murati",
        tier="foundation",
        relevance_themes=("interaction models", "200ms loop", "multimodal"),
        why_listed="foreground/background split = SFOS architecture lift",
    ),
    Luminary(
        handle="AravSrinivas",
        name="Aravind Srinivas",
        tier="foundation",
        relevance_themes=("Perplexity", "Model Council", "subscription"),
        why_listed="Model Council 2026-02 = directly steal-able UX for council-diff",
    ),
    # Tier 2: VCs whose endorsement moves Alex's distribution
    Luminary(
        handle="garrytan",
        name="Garry Tan",
        tier="vc",
        relevance_themes=("YC W26/S26", "agent infra", "founder demographics"),
        why_listed="YC W26 41.5% agent infra; SFOS positioning aligns directly",
    ),
    Luminary(
        handle="paulg",
        name="Paul Graham",
        tier="vc",
        relevance_themes=("Brand Age", "essays", "indie posture"),
        why_listed="The Brand Age (2026) thesis = developer trust over benchmark",
    ),
    Luminary(
        handle="naval",
        name="Naval Ravikant",
        tier="vc",
        relevance_themes=("shrinking company", "USVC fund", "AI redistribution"),
        why_listed="shrinking-company thesis = direct fit for solo founder OS",
    ),
    Luminary(
        handle="eladgil",
        name="Elad Gil",
        tier="vc",
        relevance_themes=("market clarity", "AI 0.25% GDP", "exit window"),
        why_listed="2026-04-20 essay flags 12-18mo exit window; calibrate Alex's pace",
    ),
    Luminary(
        handle="sarahcat21",
        name="Sarah Tavel",
        tier="vc",
        relevance_themes=("consumer AI", "agent UX", "monetization"),
        why_listed="Benchmark partner; consumer-AI takes move distribution",
    ),
    # Tier 3: indie operators whose receipts validate Alex's solo posture
    Luminary(
        handle="shl",
        name="Sahil Lavingia",
        tier="indie",
        relevance_themes=("Anti-Work", "Gumroad $10M / 1 FTE", "AI-authored code %"),
        why_listed="closest operating analog to Alex's stack; emulable receipts",
    ),
    Luminary(
        handle="levelsio",
        name="Pieter Levels",
        tier="indie",
        relevance_themes=("PhotoAI", "indie revenue dashboard", "X distribution"),
        why_listed="indie distribution canon; $3.1M ARR solo with public dashboard",
    ),
    Luminary(
        handle="marc_louvion",
        name="Marc Lou",
        tier="indie",
        relevance_themes=("ShipFast", "boilerplate flywheel", "$1M ARR solo"),
        why_listed="ship-cadence template that VibeXForge could emulate",
    ),
    # Tier 4: research / agent-infra voices
    Luminary(
        handle="swyx",
        name="Shawn Wang",
        tier="research",
        relevance_themes=("Latent Space podcast", "Stainless analysis", "DX trends"),
        why_listed="cited Stainless wind-down 2026-05 = MCP-server biz death signal",
    ),
    Luminary(
        handle="lateinteraction",
        name="Omar Khattab",
        tier="research",
        relevance_themes=("DSPy", "RAG eval", "retrieval calibration"),
        why_listed="marketing-agent uses DSPy; co-relevant calibration work",
    ),
    Luminary(
        handle="HamelHusain",
        name="Hamel Husain",
        tier="research",
        relevance_themes=("eval", "LLM in prod", "fine-tuning"),
        why_listed="eval-honesty advocate; SFOS-obs target endorser",
    ),
    Luminary(
        handle="simonw",
        name="Simon Willison",
        tier="indie",
        relevance_themes=("llm CLI", "Datasette", "weeknotes"),
        why_listed="bridges indie + Anthropic ecosystem; weeknotes amplify Alex's repos",
    ),
    Luminary(
        handle="virattt",
        name="Virat Singh",
        tier="research",
        relevance_themes=("ai-hedge-fund", "quant agents", "OSS finance"),
        why_listed="direct adjacency to Orallexa; 25k stars on ai-hedge-fund repo",
    ),
)


def by_tier(tier: Tier) -> tuple[Luminary, ...]:
    """Return luminaries filtered to one tier (foundation/vc/indie/research)."""
    return tuple(l for l in LUMINARIES_2026_H1 if l.tier == tier)


def find(handle: str) -> Luminary | None:
    """Lookup by handle (case-insensitive, with or without @)."""
    norm = handle.lstrip("@").lower()
    for l in LUMINARIES_2026_H1:
        if l.handle.lower() == norm:
            return l
    return None


def match_themes(post_text: str, *, top_k: int = 3) -> list[Luminary]:
    """
    Cheap keyword match: given a post body, return luminaries whose
    relevance_themes overlap with terms in the text. Used by the
    listener to decide which wave-borrow template to draft against.

    Not a semantic match — that lives in the listener's Claude call.
    This is the offline filter.
    """
    text_lower = post_text.lower()
    scored: list[tuple[int, Luminary]] = []
    for l in LUMINARIES_2026_H1:
        hits = sum(1 for theme in l.relevance_themes if theme.lower() in text_lower)
        if hits > 0:
            scored.append((hits, l))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [l for _, l in scored[:top_k]]
