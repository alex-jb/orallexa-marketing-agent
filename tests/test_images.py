"""Tests for content/images.py — prompt suggester + Pollinations URL builder."""
from __future__ import annotations
import urllib.parse

import pytest

from marketing_agent.content.images import (
    _PLATFORM_DIMS, _template_image_prompt, generate_image,
    suggest_image_prompt,
)
from marketing_agent.types import Platform, Project


def _proj() -> Project:
    return Project(name="VibeXForge",
                    tagline="AI maker launch platform — projects evolve like RPG characters")


def test_template_prompt_includes_tagline_and_aspect():
    p = _template_image_prompt(_proj(), Platform.X, "minimalist")
    assert "RPG characters" in p or "AI maker" in p
    assert "16:9" in p
    assert "no text" in p
    assert "no logos" in p


def test_suggest_image_prompt_falls_back_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    p = suggest_image_prompt(_proj())
    # Falls back to template — should be deterministic
    assert isinstance(p, str)
    assert len(p) > 50


def test_generate_image_returns_url_with_correct_dims():
    result = generate_image(_proj(), platform=Platform.X)
    assert result["url"].startswith("https://image.pollinations.ai/prompt/")
    assert result["backend"] == "pollinations"
    assert (result["width"], result["height"]) == _PLATFORM_DIMS[Platform.X]
    # Prompt is URL-encoded into the path
    decoded = urllib.parse.unquote(result["url"])
    assert "VibeXForge" in decoded or "AI maker" in decoded


def test_generate_image_per_platform_dims():
    for plat, dims in _PLATFORM_DIMS.items():
        r = generate_image(_proj(), platform=plat)
        assert r["width"] == dims[0]
        assert r["height"] == dims[1]


def test_generate_image_respects_prompt_override():
    custom = "a single isometric mountain, dawn light, no text"
    r = generate_image(_proj(), platform=Platform.X,
                         prompt_override=custom)
    assert r["prompt"] == custom
    decoded = urllib.parse.unquote(r["url"])
    assert "isometric mountain" in decoded


def test_generate_image_includes_nologo_param():
    r = generate_image(_proj(), platform=Platform.X)
    # Pollinations: nologo=true tells the service to skip its watermark
    assert "nologo=true" in r["url"]


def test_generate_image_supports_alternate_model():
    r = generate_image(_proj(), platform=Platform.X, model="flux-realism")
    assert "model=flux-realism" in r["url"]
