"""Tests for multi-project YAML config."""
from __future__ import annotations


from marketing_agent.multiproject import (
    TrendsConfig, _coerce, _parse_minimal_yaml, load_config,
    load_trends_config,
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


# ───────────────── TrendsConfig ─────────────────


def test_load_trends_config_default_when_block_absent(tmp_path):
    p = tmp_path / "no_trends.yml"
    p.write_text("""
projects:
  - name: A
    repo: x/y
    tagline: t
""")
    tcfg = load_trends_config(p)
    assert isinstance(tcfg, TrendsConfig)
    assert tcfg.enabled is False
    assert tcfg.languages == []
    assert tcfg.subreddits == []
    assert tcfg.top_n == 3
    assert tcfg.hours == 168


def test_load_trends_config_returns_disabled_when_file_missing(tmp_path):
    tcfg = load_trends_config(tmp_path / "does-not-exist.yml")
    assert tcfg.enabled is False


def test_load_trends_config_parses_top_level_block(tmp_path):
    p = tmp_path / "with_trends.yml"
    p.write_text("""
trends:
  enabled: true
  languages: [python, rust]
  hn_query: agent
  subreddits: [MachineLearning, IndieHackers]
  top_n: 5
  hours: 72

projects:
  - name: A
    repo: x/y
    tagline: t
""")
    tcfg = load_trends_config(p)
    assert tcfg.enabled is True
    assert tcfg.languages == ["python", "rust"]
    assert tcfg.hn_query == "agent"
    assert tcfg.subreddits == ["MachineLearning", "IndieHackers"]
    assert tcfg.top_n == 5
    assert tcfg.hours == 72


def test_load_trends_config_explicit_disabled(tmp_path):
    p = tmp_path / "disabled.yml"
    p.write_text("""
trends:
  enabled: false
  languages: [python]

projects:
  - name: A
    repo: x/y
    tagline: t
""")
    tcfg = load_trends_config(p)
    assert tcfg.enabled is False
    # Other values still parsed.
    assert tcfg.languages == ["python"]


def test_load_config_unaffected_by_trends_block(tmp_path):
    """Adding trends: block must not break project parsing."""
    p = tmp_path / "with_trends.yml"
    p.write_text("""
trends:
  enabled: true
  languages: [python]

projects:
  - name: A
    repo: x/y
    tagline: t
  - name: B
    repo: a/b
    tagline: t2
""")
    cfgs = load_config(p)
    assert [c.name for c in cfgs] == ["A", "B"]
