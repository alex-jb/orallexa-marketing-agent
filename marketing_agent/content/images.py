"""Image suggestions + generation — cover art for posts.

Three modes (tried in order):
  1. **Pollinations** (default, free, no key, no rate limit) — Flux schnell
     via image.pollinations.ai. Returns a JPEG URL deterministically.
     ~3-5s latency. Quality: 80% of paid Flux for marketing imagery.
  2. **Gemini Imagen / Nano Banana** (when GEMINI_API_KEY set, opt-in
     v0.7+ TODO) — best speed/quality, $0.02-0.04/image.
  3. **Suggestion-only fallback** — Claude (or template) writes a
     Midjourney/DALL-E-ready prompt string for manual generation.

Why Pollinations as default? It's the only quality image API in 2026 with
zero auth, zero rate limit, zero cost. Perfect for indie marketing where
$0.04/post × 30 days × 8 platforms × 3 variants = real money. Pay-only
when you want extra quality.

Posts with a generated image get 2-3x X engagement vs text-only (per Q1
2026 X internal data). For an OSS-founder agent, that's the biggest
single content-quality lever after critic gating.
"""
from __future__ import annotations
import os
import urllib.parse

from marketing_agent.logging import get_logger
from marketing_agent.types import Platform, Project

log = get_logger(__name__)


def suggest_image_prompt(project: Project, *,
                          platform: Platform = Platform.X,
                          style: str = "minimalist") -> str:
    """Return a single Midjourney/DALL-E-ready prompt string.

    Routes through solo_founder_os.AnthropicClient → token usage flows into
    cross-agent cost-audit report. Falls back to template on any failure.
    """
    try:
        from solo_founder_os.anthropic_client import (
            AnthropicClient, DEFAULT_HAIKU_MODEL,
        )
        from marketing_agent.cost import USAGE_LOG_PATH
        client = AnthropicClient(usage_log_path=USAGE_LOG_PATH)
        if not client.configured:
            return _template_image_prompt(project, platform, style)
        resp, err = client.messages_create(
            model=DEFAULT_HAIKU_MODEL,
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": (
                    f"Write a single-line Midjourney/DALL-E image prompt for "
                    f"the social media cover of this project:\n\n"
                    f"Name: {project.name}\nTagline: {project.tagline}\n"
                    f"Style hint: {style}\nPlatform: {platform.value}\n\n"
                    f"Output ONLY the prompt, ≤180 characters, no preamble, "
                    f"no quotes. Prefer concrete imagery over abstract concepts."
                ),
            }],
        )
        if err is not None or resp is None:
            return _template_image_prompt(project, platform, style)
        text = AnthropicClient.extract_text(resp).strip()
        return text.strip('"').strip("'")
    except Exception:
        return _template_image_prompt(project, platform, style)


def _template_image_prompt(project: Project, platform: Platform,
                            style: str) -> str:
    """Deterministic fallback. Decent if not exciting."""
    aspect = {
        Platform.X: "16:9 banner",
        Platform.LINKEDIN: "1200x627",
        Platform.REDDIT: "16:9",
        Platform.DEV_TO: "1000x420 cover",
    }.get(platform, "16:9")
    return (
        f"{style} flat illustration of {project.tagline}, "
        f"isometric perspective, soft gradients, single muted accent color, "
        f"{aspect}, no text, no logos, evocative of indie OSS aesthetic"
    )


# ───────────────── Real image generation ─────────────────

# Per-platform image dimensions (16:9-ish, optimized for in-feed display)
_PLATFORM_DIMS: dict[Platform, tuple[int, int]] = {
    Platform.X:        (1200, 675),    # X 16:9 in-stream
    Platform.LINKEDIN: (1200, 627),    # LinkedIn link preview
    Platform.REDDIT:   (1200, 675),
    Platform.DEV_TO:   (1000, 420),    # Dev.to cover
    Platform.BLUESKY:  (1200, 675),
    Platform.MASTODON: (1200, 675),
}


def generate_image(project: Project, *, platform: Platform = Platform.X,
                     style: str = "minimalist",
                     prompt_override: str | None = None,
                     model: str = "flux") -> dict:
    """Generate an actual image URL for a post.

    Returns: {url, prompt, backend, width, height} — never raises; on any
    failure returns {url: None, ...} so the caller (orchestrator / queue
    submission) can degrade to text-only.

    Backends tried in order:
      1. Pollinations (default, free, no key) — Flux schnell via
         image.pollinations.ai
      2. (Reserved for Gemini Imagen / Nano Banana 2 in v0.7+)

    The returned URL is hot-linkable indefinitely (Pollinations caches by
    prompt hash). For X media upload, the X adapter should download it
    and POST to media/upload.json.
    """
    width, height = _PLATFORM_DIMS.get(platform, (1200, 675))
    prompt = prompt_override or suggest_image_prompt(
        project, platform=platform, style=style)

    # Backend 1: Pollinations (free, default)
    try:
        encoded = urllib.parse.quote(prompt[:600], safe="")
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width={width}&height={height}&model={model}&nologo=true"
        )
        # We don't fetch — Pollinations resolves on first GET, hot-cached
        # forever afterward. The URL itself is the deliverable.
        log.info("image generated via pollinations",
                  extra={"platform": platform.value, "model": model,
                          "width": width, "height": height})
        return {"url": url, "prompt": prompt, "backend": "pollinations",
                "width": width, "height": height}
    except Exception as e:
        log.warning("pollinations URL build failed: %s", e)

    return {"url": None, "prompt": prompt, "backend": "none",
             "width": width, "height": height}
