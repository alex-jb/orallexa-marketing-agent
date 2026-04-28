"""Image suggestions — picks (or generates) cover art prompts for posts.

Two modes:
  1. **Suggestion mode (default)**: Claude writes a vivid image-prompt
     description that you can paste into Midjourney / DALL-E / Stable
     Diffusion / Flux. No API call to image services from this lib.
  2. **Future generation mode**: when an OpenAI key is set, can call
     DALL-E directly. (Not implemented in v0.2 to avoid binding to one
     image vendor.)

Why suggestions only? Image generation is taste-heavy. The agent writes
a great prompt; you (the human) keep curation control.
"""
from __future__ import annotations
import os

from marketing_agent.types import Platform, Project


def suggest_image_prompt(project: Project, *,
                          platform: Platform = Platform.X,
                          style: str = "minimalist") -> str:
    """Return a single Midjourney/DALL-E-ready prompt string."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return _template_image_prompt(project, platform, style)

    try:
        from anthropic import Anthropic
        client = Anthropic()
        resp = client.messages.create(
            model="claude-haiku-4-5",
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
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
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
