"""viral_patterns.py — BuzzPlay-derived viral content templates.

Extracted from a 2026-05-13 study of BuzzPlay (buzzplay.app) — a Chinese
indie AI interactive-content platform whose early 小红书 招内测用户 post
got disproportionate engagement vs typical AI-product launch posts.

Two patterns we found worth crystallizing:

1. **Negative-space positioning** — define product by NOT-categories first:
   "不是视频,不是图文,是真的能「玩」的"

2. **5-part recruit-invite structure** — for early-stage indie product
   internal-test recruitment on 小红书 / Twitter / Show HN:
     [1] Problem framing (1 sentence, 2-3 user action verbs)
     [2] Validation hook (specific result + casual "哈哈哈")
     [3] Stage honesty ("还在早期")
     [4] Soft CTA double-track (low-friction + high-intent)
     [5] Hashtag chain (8 tags: brand + category + community + lifecycle)

Plus `casual_humanizer_zh()` — surgical injection of casual particles
(啊 / 嘛 / 哈哈) into formal Chinese drafts. Calibrated so the result
sounds like a friend, not a corporate ad.

Tests: `tests/test_viral_patterns.py`.
"""
from __future__ import annotations

import random
import re

from marketing_agent.types import Platform, Post, Project


# ────────────────────────────────────────────────────────────────────
# Pattern 1 — Negative-space positioning
# ────────────────────────────────────────────────────────────────────

def negative_space_positioning(
    project_name: str,
    not_categories: list[str],
    is_verb_noun: str,
    *,
    language: str = "zh",
) -> str:
    """Render a one-line positioning statement using NOT-categories.

    Examples:
      >>> negative_space_positioning(
      ...     "念念",
      ...     ["日记 app", "聊天 bot"],
      ...     "你说一句话,世界长出来一点东西",
      ... )
      '念念 — 不是日记 app,不是聊天 bot,是你说一句话,世界长出来一点东西。'

      >>> negative_space_positioning(
      ...     "VibeXForge",
      ...     ["ProductHunt", "GitHub trending"],
      ...     "给中国独立 AI 创作者一个真能炸的舞台",
      ... )
      'VibeXForge — 不是 ProductHunt,不是 GitHub trending,是给中国独立 AI 创作者一个真能炸的舞台。'

    Args:
      project_name: brand to position
      not_categories: ≥2 well-known categories your product is NOT. Pick
        ones the reader will instinctively reach for. The point is to
        block those associations before they form.
      is_verb_noun: a verb-led description of what you ARE. Should be
        concrete (an outcome, not an abstraction). No emoji.
      language: "zh" (default) or "en". English version uses "not… not…
        but" rhythm.
    """
    if len(not_categories) < 2:
        raise ValueError("Need at least 2 NOT-categories to anchor the positioning")
    if language == "en":
        not_parts = ", ".join(f"not {c}" for c in not_categories)
        return f"{project_name} — {not_parts} — {is_verb_noun}."
    not_parts = "".join(f"不是{c}," for c in not_categories)
    return f"{project_name} — {not_parts}是{is_verb_noun}。"


# ────────────────────────────────────────────────────────────────────
# Pattern 2 — Recruit-invite (5-part structure)
# ────────────────────────────────────────────────────────────────────

def render_recruit_invite(
    project: Project,
    *,
    user_action_verbs: list[str],
    validation_hook: str,
    extra_tags: list[str] | None = None,
    target: str = "xiaohongshu",
    language: str | None = None,
) -> Post:
    """Render a BuzzPlay-style early-stage recruit-invite post.

    The 5 parts are stitched together with line breaks. Tags go at the end.

    Args:
      project: name + tagline used in problem framing
      user_action_verbs: 2-4 concrete user actions your product enables.
        These appear in sequence in the problem framing — they should
        be the user's experience, not the tech's feature.
        Good: ["玩", "选择", "看结果"]
        Bad:  ["LLM 推理", "向量检索", "结构化输出"]
      validation_hook: a specific anecdote of validation. Should include
        a concrete number/name AND a casual particle ("哈哈哈" / "honestly").
      extra_tags: project-specific tags to mix with the 5 default
        categories (brand / category / community / lifecycle / niche).
      target: "xiaohongshu" (default), "twitter", or "showhn".
      language: "zh" or "en". If None, defaults from target:
        xiaohongshu → zh, twitter/showhn → en. The template body
        (problem framing, stage honesty, CTA, default tags) switches
        with this — passing en-only `user_action_verbs` for an
        xiaohongshu target with `language="en"` is valid for
        bilingual brands like 念念 launching to global+CN.

    Returns:
      Post — platform set to whichever target was specified.
    """
    if language is None:
        language = "zh" if target == "xiaohongshu" else "en"

    verbs_block = "、".join(user_action_verbs) if language == "zh" else ", ".join(user_action_verbs)

    # [1] Problem framing
    if language == "zh":
        framing = f"{project.tagline.rstrip('。.')}—— 朋友可以 {verbs_block}。"
    else:
        framing = f"{project.tagline.rstrip('。.')} — your friend can {verbs_block}."

    # [2] Validation hook — feed in as-is
    validation = validation_hook.strip()

    # [3] Stage honesty
    if language == "zh":
        stage = "目前产品还在早期阶段 我们想多认识一些真实的用户 欢迎来体验、吐槽、提建议 🙏"
    else:
        stage = "Product is still very early. We're looking for real users to try, complain, suggest 🙏 Every reply gets read."

    # [4] CTA — varies by both target AND language
    if target == "showhn":
        cta = (
            "Feedback would mean a lot — drop a thought below, "
            "or DM me directly if you want to chat about what you'd build with this. 👇"
        )
    elif target == "twitter":
        cta = "Drop a 👀 below or DM me if you want early access. Every reply is read. 👇"
    elif language == "zh":
        cta = "感兴趣的小伙伴评论区扣「1」或者直接来聊聊你想用 AI 做什么有趣的东西 👇"
    else:
        cta = "Drop a comment or DM me — tell me what you'd want to build with this. 👇"

    # [5] Hashtag chain (5 categories: brand · category · community · lifecycle · niche)
    base_tags = [f"#{project.name}"]
    base_tags += [f"#{t}" for t in (extra_tags or [])]
    if language == "zh":
        base_tags += ["#独立开发", "#产品内测", "#AI产品", "#创业"]
    else:
        base_tags += ["#indiehackers", "#buildinpublic", "#showhn", "#earlyaccess"]
    # Deduplicate while preserving order
    seen: set[str] = set()
    deduped = []
    for t in base_tags:
        if t not in seen:
            seen.add(t)
            deduped.append(t)
    tags_line = " ".join(deduped)

    body_lines = [framing, "", validation, "", stage, "", cta, "", tags_line]
    body = "\n".join(body_lines)

    platform = {
        "xiaohongshu": Platform.XIAOHONGSHU,
        "twitter": Platform.X,
        "showhn": Platform.HACKER_NEWS,
    }.get(target, Platform.XIAOHONGSHU)

    return Post(
        platform=platform,
        body=body,
        title=f"{project.name} · 招内测",
        target=target,
        char_count=len(body),
    )


# ────────────────────────────────────────────────────────────────────
# Casual humanizer — inject "啊 / 嘛 / 哈哈" into formal Chinese drafts
# ────────────────────────────────────────────────────────────────────

# Sentence-end softeners. Inserted at sentence boundaries when the
# adjacent clause feels "delivery-style" rather than personal.
_PARTICLES_END = ("啊", "嘛", "呢")

# Standalone interjections — inserted ONCE per draft if validation/joy
# tone is detected. Used sparingly so the text doesn't read as forced.
_INTERJECTIONS_JOY = ("哈哈", "哈哈哈")

# Sentences ending in these markers feel like a friend confessing — we
# probabilistically insert humanizer at the end of those.
_PERSONAL_MARKERS = (
    "我", "我们", "感觉", "觉得", "试", "做了", "发现",
    "I", "we", "honestly", "actually",
)

# Sentences that should NEVER be humanized (technical / numeric / CTA).
_FORMAL_MARKERS_BLOCK = (
    "https://", "http://",
    "请",  # imperative
    "Tip:", "Note:",
    "%", "$", "GB",
    "API", "SDK", "MCP", "LLM",
)


def casual_humanizer_zh(
    text: str,
    *,
    seed: int | None = None,
    aggressiveness: float = 0.4,
    inject_interjection: bool = True,
) -> str:
    """Lightly inject casual Chinese particles into a draft.

    The goal is to make AI-drafted Chinese marketing text sound like a
    friend, not a corporate ad. Calibrated conservatively: by default
    only ~40% of eligible sentences get a particle, and at most ONE
    standalone interjection per draft.

    Args:
      text: input text (markdown / plain). Lines starting with '#',
        '-', '*', '|', '>', or '```' are skipped (headers, lists,
        tables, code).
      seed: pass a fixed int for reproducible output (tests).
      aggressiveness: 0.0 = no insertions; 1.0 = always insert. 0.4 is
        the calibrated default. Above 0.6 starts sounding cringe.
      inject_interjection: if True, ONCE per draft, insert a
        "哈哈" / "哈哈哈" at the end of a validation-tone sentence.

    Returns:
      Modified text. Original line breaks and structure preserved.
    """
    if not text.strip():
        return text
    rng = random.Random(seed)

    state = {"interjection_used": False}
    out_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "-", "*", "|", ">", "```")):
            out_lines.append(line)
            continue
        if any(m in stripped for m in _FORMAL_MARKERS_BLOCK):
            out_lines.append(line)
            continue
        out_lines.append(
            _humanize_line(
                line,
                rng=rng,
                aggressiveness=aggressiveness,
                allow_interjection=inject_interjection,
                state=state,
            )
        )
    return "\n".join(out_lines)


_SENTENCE_RE = re.compile(r"([^。!?！？]+)([。!?！？])")
_JOY_KEYWORDS = ("炸", "成了", "试了", "卧槽")


def _humanize_line(
    line: str,
    *,
    rng: random.Random,
    aggressiveness: float,
    allow_interjection: bool,
    state: dict,
) -> str:
    """Apply humanizer transformations to one line.

    `state` is a mutable dict carrying `interjection_used` across calls
    so we only insert the standalone "哈哈" once per whole draft.

    Strategy per sentence:
      1. If joyful (contains "炸"/"成了"/"试了") and no interjection
         has been used yet → append "哈哈"/"哈哈哈" before the period.
      2. Else if sentence has a personal marker AND doesn't already end
         with a particle AND rng draw passes → insert particle before
         the period.
    """
    out_parts: list[str] = []
    pos = 0
    for m in _SENTENCE_RE.finditer(line):
        body, terminator = m.group(1), m.group(2)
        if m.start() > pos:
            out_parts.append(line[pos:m.start()])
        pos = m.end()

        new_body = body
        if (allow_interjection
                and not state["interjection_used"]
                and any(k in body for k in _JOY_KEYWORDS)):
            new_body = body + rng.choice(_INTERJECTIONS_JOY)
            state["interjection_used"] = True
        elif any(pm in body for pm in _PERSONAL_MARKERS):
            if not body.rstrip().endswith(_PARTICLES_END):
                if rng.random() < aggressiveness:
                    new_body = body + rng.choice(_PARTICLES_END)
        out_parts.append(new_body + terminator)
    if pos < len(line):
        out_parts.append(line[pos:])
    return "".join(out_parts)
