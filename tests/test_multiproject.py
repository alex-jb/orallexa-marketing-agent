"""Tests for multi-project YAML config."""
from __future__ import annotations
from pathlib import Path

import pytest

from marketing_agent.multiproject import (
    ProjectConfig, _coerce, _parse_minimal_yaml, load_config,
)


SAMPLE = """
projects:
  - name: Orallexa
    repo: alex-jb/orallexa-ai-trading-agent
    tagline: Self-tuning multi-agent AI trading system
    description: 8-source signal fusion, MIT.
    website: https://orallexa-ui.vercel.app
    platforms: [x, bluesky]
    tags: [multi-agent, trading, llm]
    enabled: true
  - name: VibeXForge
    repo: alex-jb/vibex
    tagline: Gamified growth platform for AI creators
    platforms: [x]
    enabled: true
  - name: Disabled
    repo: foo/bar
    tagline: Skip me
    enabled: false
"""


def test_coerce_basic_types():
    assert _coerce("true") is True
    assert _coerce("false") is False
    assert _coerce("null") is None
    assert _coerce("42") == 42
    assert _coerce("3.14") == 3.14
    assert _coerce('"hello"') == "hello"
    assert _coerce("[a, b, c]") == ["a", "b", "c"]
    assert _coerce("[]") == []


def test_parse_minimal_yaml_returns_list_of_dicts():
    data = _parse_minimal_yaml(SAMPLE)
    assert "projects" in data
    assert len(data["projects"]) == 3
    first = data["projects"][0]
    assert first["name"] == "Orallexa"
    assert first["repo"] == "alex-jb/orallexa-ai-trading-agent"
    assert first["platforms"] == ["x", "bluesky"]
    assert first["enabled"] is True


def test_load_config_returns_only_enabled(tmp_path):
    p = tmp_path / "marketing-agent.yml"
    p.write_text(SAMPLE)
    cfgs = load_config(p)
    assert len(cfgs) == 2
    names = [c.name for c in cfgs]
    assert "Orallexa" in names
    assert "VibeXForge" in names
    assert "Disabled" not in names


def test_load_config_returns_empty_when_file_missing(tmp_path):
    cfgs = load_config(tmp_path / "doesnt-exist.yml")
    assert cfgs == []


def test_project_config_has_sane_defaults(tmp_path):
    p = tmp_path / "minimal.yml"
    p.write_text("""
projects:
  - name: Bare
    repo: x/y
    tagline: Just a tagline
""")
    cfgs = load_config(p)
    assert len(cfgs) == 1
    c = cfgs[0]
    assert c.platforms == ["x"]
    assert c.tags == []
    assert c.enabled is True


def test_skips_invalid_projects(tmp_path):
    """Projects missing name/repo/tagline are silently skipped."""
    p = tmp_path / "bad.yml"
    p.write_text("""
projects:
  - name: Valid
    repo: x/y
    tagline: ok
  - repo: missing-name/y
    tagline: no name here
  - name: NoRepo
    tagline: no repo
""")
    cfgs = load_config(p)
    assert len(cfgs) == 1
    assert cfgs[0].name == "Valid"
