"""Content generation entry point. Tries Claude when keyed, falls back to templates."""
from __future__ import annotations
import os
from typing import Optional

from marketing_agent.types import GenerationMode, Platform, Post, Project
from marketing_agent.content import templates


def generate_posts(
    project: Project,
    platforms: list[Platform],
    mode: GenerationMode = GenerationMode.HYBRID,
    *,
    subreddit: Optional[str] = None,
    n_variants: int = 1,
) -> list[Post]:
    """Generate one Post per platform.

    HYBRID (default): try Claude when ANTHROPIC_API_KEY is set; on any failure
    or when key is missing, fall back to deterministic templates.

    n_variants > 1: for platforms that support multiple stylistic variants
    (currently only X), generate that many variants per platform; the bandit
    chooses one. Other platforms ignore n_variants and always return one post.
    """
    out: list[Post] = []
    for p in platforms:
        if mode == GenerationMode.TEMPLATE or not os.getenv("ANTHROPIC_API_KEY"):
            if n_variants > 1:
                variants = templates.render_variants(p, project, n=n_variants,
                                                       subreddit=subreddit)
                out.append(_pick_with_bandit(variants))
            else:
                out.append(templates.render(p, project, subreddit=subreddit))
            continue

        try:
            out.append(_generate_with_llm(project, p, subreddit=subreddit))
        except Exception:
            if mode == GenerationMode.LLM:
                raise  # caller asked for LLM-only; don't silently downgrade
            if n_variants > 1:
                variants = templates.render_variants(p, project, n=n_variants,
                                                       subreddit=subreddit)
                out.append(_pick_with_bandit(variants))
            else:
                out.append(templates.render(p, project, subreddit=subreddit))
    return out


def _pick_with_bandit(variants: list[Post]) -> Post:
    """Pick one variant via Thompson sampling. Falls back to first on errors."""
    keys = [v.variant_key for v in variants if v.variant_key]
    if not keys:
        return variants[0]
    try:
        from marketing_agent.bandit import VariantBandit
        chosen_key = VariantBandit().choose(keys)
        for v in variants:
            if v.variant_key == chosen_key:
                return v
    except Exception:
        pass
    return variants[0]


def _generate_with_llm(
    project: Project,
    platform: Platform,
    *,
    subreddit: Optional[str] = None,
) -> Post:
    """Generate via LLM. Routes to cheapest configured provider:

      1. Cloudflare Workers AI Llama 3.3 (~$0.011/1M tokens, when keyed)
      2. Anthropic Claude Sonnet 4.6 (default — preserves prompt-caching
         + ICPL behavior)

    Critic + rewriter still hit Claude (via supervisor.py) when keyed —
    edge tier is only the cheap first-draft path.
    """
    system_prompt = _system_for(platform)
    user_prompt = _user_prompt_for(project, platform, subreddit=subreddit)

    # ICPL: inject up to 5 recent (original → edited) pairs from this
    # (project, platform) channel as few-shot exemplars. Free preference
    # signal — over time the agent learns to write in the human reviewer's
    # voice without any fine-tuning. No-op when no edits logged yet.
    try:
        from marketing_agent.preference import PreferenceStore
        block = PreferenceStore().few_shot_block(
            project_name=project.name, platform=platform, limit=5)
        if block:
            user_prompt = block + "\n\n" + user_prompt
    except Exception:
        pass

    # Tier 1: Cloudflare edge inference. Falls through to Claude on any
    # failure or when Cloudflare envs aren't set.
    try:
        from marketing_agent.llm.edge_provider import (
            complete_via_edge, is_edge_configured,
        )
        if is_edge_configured():
            edge_text = complete_via_edge(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=600,
            )
            if edge_text:
                cleaned = edge_text.strip().strip('"').strip("'").strip()
                return _post_for(platform, cleaned, project,
                                    subreddit=subreddit).with_count()
    except Exception:
        pass

    # Tier 2: Anthropic Claude via solo_founder_os.AnthropicClient
    # (token usage flows into the cross-agent cost-audit report).
    from marketing_agent.llm.anthropic_compat import (
        AnthropicClient, DEFAULT_SONNET_MODEL,
    )
    from marketing_agent.cost import USAGE_LOG_PATH
    client = AnthropicClient(usage_log_path=USAGE_LOG_PATH)
    if not client.configured:
        # No key — caller (generate_posts) will fall through to template
        raise RuntimeError("ANTHROPIC_API_KEY not set; LLM mode unavailable")

    # Prompt caching: the system prompt (~200-400 tokens of style guide)
    # is stable across all daily-cron calls. Marking it cache_control
    # ephemeral with 1h TTL cuts input cost ~80% on repeated runs.
    resp, err = client.messages_create(
        model=DEFAULT_SONNET_MODEL,
        max_tokens=600,
        system=[{
            "type": "text", "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": user_prompt}],
    )
    if err is not None or resp is None:
        raise RuntimeError(f"LLM call failed: {err}")
    text = AnthropicClient.extract_text(resp).strip()
    text = text.strip('"').strip("'").strip()

    return _post_for(platform, text, project, subreddit=subreddit).with_count()


def _system_for(platform: Platform) -> str:
    """Per-platform voice / constraints."""
    base = (
        "You are writing on behalf of an indie OSS developer who is building "
        "in public. Voice: technical, honest, no marketing fluff, no hype "
        "words like 'revolutionary' or 'cutting-edge'. Show, don't tell."
    )
    extras = {
        Platform.X: (
            " Output a single tweet, max 270 chars (we'll append a URL). "
            "1 emoji max at start. No hashtags. End on a concrete observation, "
            "not a CTA."
        ),
        Platform.REDDIT: (
            " Output a Reddit post body, 4-8 short paragraphs. Open with what "
            "you built and why. Include code or numbers if relevant. End with "
            "an honest ask for feedback."
        ),
        Platform.LINKEDIN: (
            " Output a LinkedIn post, 600-1000 chars. More polished than X but "
            "not corporate. Lead with the problem or the journey."
        ),
        Platform.DEV_TO: (
            " Output a DEV.to article, markdown formatted, ~600-1500 words. "
            "Use H2 sections. Include a code block if relevant."
        ),
    }
    return base + extras.get(platform, "")


def _user_prompt_for(
    project: Project,
    platform: Platform,
    *,
    subreddit: Optional[str] = None,
) -> str:
    parts = [f"Project: {project.name}", f"Tagline: {project.tagline}"]
    if project.description:
        parts.append(f"Description:\n{project.description}")
    if project.recent_changes:
        parts.append("Recent changes:\n" + "\n".join(f"- {c}" for c in project.recent_changes[:10]))
    if project.target_audience:
        parts.append(f"Target audience: {project.target_audience}")
    if project.tags:
        parts.append(f"Tags: {', '.join(project.tags)}")
    if subreddit and platform == Platform.REDDIT:
        parts.append(f"Subreddit: r/{subreddit}")

    parts.append(f"\nWrite the {platform.value} post now. Output ONLY the post text, no preamble.")
    return "\n\n".join(parts)


def _post_for(platform: Platform, text: str, project: Project,
               *, subreddit: Optional[str] = None) -> Post:
    if platform == Platform.REDDIT:
        title = f"[Project] {project.name}: {project.tagline}"
        return Post(platform=platform, title=title, body=text,
                    target=subreddit or "MachineLearning")
    return Post(platform=platform, body=text)
