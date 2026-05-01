"""Multi-project config — let the cron handle N projects in one pass.

Why: real users have several repos (Orallexa + VibeXForge + marketing-agent
itself). Today the cron is hardcoded to one. With this module + a
`marketing-agent.yml` config in the repo root, daily.yml iterates through
each enabled project.

Schema (deliberately minimal — keep it readable in a text editor):

    projects:
      - name: Orallexa
        repo: alex-jb/orallexa-ai-trading-agent
        tagline: Self-tuning multi-agent AI trading system
        description: 8-source signal fusion + Bull/Bear/Judge debate. MIT.
        website: https://orallexa-ui.vercel.app
        platforms: [x, bluesky]
        tags: [multi-agent, trading, llm]
        enabled: true
      - name: VibeXForge
        repo: alex-jb/vibex
        tagline: Gamified growth platform for AI creators
        platforms: [x]
        enabled: true

YAML chosen for human-friendliness (vs TOML) but we don't take a PyYAML
dependency — the parser here handles the limited subset we need (no flow
style, no anchors, scalars + lists). For full YAML, set ENV
`MARKETING_AGENT_USE_PYYAML=1` and we'll use it if installed.
"""
from __future__ import annotations
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ProjectConfig:
    """One project entry from marketing-agent.yml."""
    name: str
    repo: str
    tagline: str
    description: Optional[str] = None
    website: Optional[str] = None
    platforms: list[str] = field(default_factory=lambda: ["x"])
    tags: list[str] = field(default_factory=list)
    subreddit: Optional[str] = None
    enabled: bool = True


@dataclass
class TrendsConfig:
    """Top-level `trends:` block in marketing-agent.yml. Optional.

    When enabled, the daily cron also runs `trends_to_drafts` for each
    enabled project, using these shared filters. Per-project override is
    intentionally NOT supported yet — most users want one consistent
    niche filter across all their projects.
    """
    enabled: bool = False
    languages: list[str] = field(default_factory=list)   # GitHub langs
    hn_query: str = ""
    subreddits: list[str] = field(default_factory=list)
    top_n: int = 3
    hours: int = 168


def load_config(path: str | Path = "marketing-agent.yml") -> list[ProjectConfig]:
    """Load and return enabled projects. Returns [] if file missing.

    Order: file order. Skipped projects (enabled: false) are filtered out.
    """
    data = _load_raw(path)
    if data is None:
        return []
    projects = data.get("projects", [])
    out: list[ProjectConfig] = []
    for p in projects:
        cfg = ProjectConfig(
            name=p.get("name") or "",
            repo=p.get("repo") or "",
            tagline=p.get("tagline") or "",
            description=p.get("description"),
            website=p.get("website"),
            platforms=p.get("platforms") or ["x"],
            tags=p.get("tags") or [],
            subreddit=p.get("subreddit"),
            enabled=p.get("enabled", True),
        )
        if cfg.enabled and cfg.name and cfg.repo and cfg.tagline:
            out.append(cfg)
    return out


def load_trends_config(path: str | Path = "marketing-agent.yml") -> TrendsConfig:
    """Load the top-level `trends:` block. Returns disabled default if absent."""
    data = _load_raw(path)
    if data is None:
        return TrendsConfig()
    block = data.get("trends") or {}
    if not isinstance(block, dict):
        return TrendsConfig()
    return TrendsConfig(
        enabled=bool(block.get("enabled", False)),
        languages=list(block.get("languages") or []),
        hn_query=str(block.get("hn_query") or ""),
        subreddits=list(block.get("subreddits") or []),
        top_n=int(block.get("top_n") or 3),
        hours=int(block.get("hours") or 168),
    )


def _load_raw(path: str | Path) -> Optional[dict]:
    """Shared YAML loader used by load_config + load_trends_config."""
    p = Path(path)
    if not p.exists():
        return None
    text = p.read_text(encoding="utf-8")

    if os.getenv("MARKETING_AGENT_USE_PYYAML"):
        try:
            import yaml  # type: ignore
            return yaml.safe_load(text) or {}
        except Exception:
            return _parse_minimal_yaml(text)
    return _parse_minimal_yaml(text)


# ───────────────── minimal YAML parser ─────────────────
# Handles the exact subset we use:
#   key: value             (scalar)
#   key:                   (mapping/list start)
#     - item               (list item, scalar OR mapping)
#     - key2: val2         (nested mapping in list)
#       key3: val3         (continued mapping fields)
#   [a, b, c]              (inline list)

_SCALAR = re.compile(r"^([A-Za-z_][\w-]*):\s*(.*)$")
_LIST_ITEM = re.compile(r"^-\s+(.*)$")


def _coerce(s: str):
    s = s.strip()
    if not s:
        return None
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1]
    if s.startswith("'") and s.endswith("'"):
        return s[1:-1]
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [_coerce(x) for x in inner.split(",")]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "none", "~"):
        return None
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        pass
    return s


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _parse_minimal_yaml(text: str) -> dict:
    """Return a dict matching what we'd get from yaml.safe_load() for our
    schema. Strict enough for us; not a general YAML parser."""
    lines = [ln.rstrip() for ln in text.splitlines()
              if ln.strip() and not ln.lstrip().startswith("#")]

    root: dict = {}
    # Scan top level for `key:` followed by indented content
    i = 0
    while i < len(lines):
        line = lines[i]
        if _indent(line) != 0:
            i += 1
            continue
        m = _SCALAR.match(line)
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2).strip()
        if val:
            root[key] = _coerce(val)
            i += 1
            continue
        # Block follows. Collect indented lines.
        block_lines: list[str] = []
        i += 1
        while i < len(lines) and _indent(lines[i]) > 0:
            block_lines.append(lines[i])
            i += 1
        # Decide if it's a list (starts with `-`) or mapping
        if block_lines and block_lines[0].lstrip().startswith("- "):
            root[key] = _parse_list_block(block_lines)
        else:
            root[key] = _parse_mapping_block(block_lines)
    return root


def _parse_mapping_block(block: list[str]) -> dict:
    out: dict = {}
    base_indent = _indent(block[0]) if block else 0
    for ln in block:
        if _indent(ln) != base_indent:
            continue
        m = _SCALAR.match(ln.lstrip())
        if not m:
            continue
        out[m.group(1)] = _coerce(m.group(2))
    return out


def _parse_list_block(block: list[str]) -> list:
    """Parse a `- item` list. Items may be scalars or nested mappings."""
    items: list = []
    base_indent = _indent(block[0]) if block else 0
    cur_item: Optional[dict] = None
    cur_indent_extra = base_indent + 2  # default Python-style 2-space

    for ln in block:
        ind = _indent(ln)
        stripped = ln.lstrip()

        if ind == base_indent and stripped.startswith("- "):
            if cur_item is not None:
                items.append(cur_item)
            payload = stripped[2:]
            if ":" in payload and not payload.startswith(("'", '"')):
                m = _SCALAR.match(payload)
                if m:
                    cur_item = {m.group(1): _coerce(m.group(2))}
                    cur_indent_extra = ind + 2
                    continue
            # Scalar list item
            items.append(_coerce(payload))
            cur_item = None
            continue

        if cur_item is not None and ind >= cur_indent_extra:
            m = _SCALAR.match(stripped)
            if m:
                cur_item[m.group(1)] = _coerce(m.group(2))
    if cur_item is not None:
        items.append(cur_item)
    return items
