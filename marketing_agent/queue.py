"""HITL approval queue — markdown-file-based.

Why markdown files instead of a web UI? Because for a one-person agent
company, the founder's editor (or Obsidian) IS the dashboard. The agent
writes proposed posts as markdown files into a `pending/` folder; the
human edits them or moves them to `approved/`. A separate publish step
reads `approved/` and actually posts.

Each post is its own .md file with YAML frontmatter, so any text editor
or Obsidian works. Move a file to `rejected/` to permanently skip it.

Layout:
    queue/
    ├── pending/    # newly generated, awaiting human review
    ├── approved/   # human moved them here; ready to publish
    ├── posted/     # published successfully (archive)
    └── rejected/   # human said no
"""
from __future__ import annotations
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from marketing_agent.types import Platform, Post


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)", re.DOTALL)


class ApprovalQueue:
    """File-based approval queue. The queue root has 4 subdirs."""

    def __init__(self, root: Optional[Path | str] = None):
        if root is None:
            root = os.getenv("MARKETING_AGENT_QUEUE",
                             Path.home() / ".marketing_agent" / "queue")
        self.root = Path(root)
        for sub in ("pending", "approved", "posted", "rejected"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    def submit(self, post: Post, project_name: str,
                generated_by: str = "auto") -> Path:
        """Write a post into pending/, return its path."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        slug = re.sub(r"[^a-z0-9]+", "-", project_name.lower()).strip("-")
        fname = f"{ts}-{slug}-{post.platform.value}.md"
        path = self.root / "pending" / fname
        path.write_text(self._render(post, project_name, generated_by))
        return path

    def list_approved(self) -> list[Path]:
        """Return paths of posts approved by the human, ready to publish."""
        return sorted((self.root / "approved").glob("*.md"))

    def load(self, path: Path) -> tuple[Post, dict]:
        """Read an approval-queue markdown file back into a Post + metadata.

        Returns (post, metadata_dict). Metadata includes project_name,
        generated_by, original timestamp, etc.
        """
        text = path.read_text()
        m = _FRONTMATTER_RE.match(text)
        if not m:
            raise ValueError(f"Bad queue file format (no frontmatter): {path}")
        meta_yaml, body = m.groups()
        meta = self._parse_yaml_lite(meta_yaml)
        post = Post(
            platform=Platform(meta["platform"]),
            body=body.strip(),
            title=meta.get("title") or None,
            target=meta.get("target") or None,
        ).with_count()
        return post, meta

    def mark_posted(self, path: Path, external_id: Optional[str] = None) -> Path:
        """Move file from approved/ → posted/ and append the external id."""
        new_path = self.root / "posted" / path.name
        text = path.read_text()
        if external_id:
            text = text.rstrip() + f"\n\n<!-- posted_id: {external_id} -->\n"
        new_path.write_text(text)
        path.unlink()
        return new_path

    def mark_rejected(self, path: Path) -> Path:
        """Move file → rejected/."""
        new_path = self.root / "rejected" / path.name
        new_path.write_text(path.read_text())
        path.unlink()
        return new_path

    # ───────────────────── internals ─────────────────────

    def _render(self, post: Post, project_name: str, generated_by: str) -> str:
        front = [
            "---",
            f"platform: {post.platform.value}",
            f"project: {project_name}",
            f"generated_by: {generated_by}",
            f"generated_at: {datetime.now(timezone.utc).isoformat()}",
        ]
        if post.title:
            front.append(f"title: {self._yaml_escape(post.title)}")
        if post.target:
            front.append(f"target: {post.target}")
        front.append(f"char_count: {post.char_count or len(post.body)}")
        front.append("---")
        return "\n".join(front) + "\n" + post.body + "\n"

    @staticmethod
    def _yaml_escape(s: str) -> str:
        if any(ch in s for ch in ":[]{}#&*!|>'\""):
            return '"' + s.replace('"', '\\"') + '"'
        return s

    @staticmethod
    def _parse_yaml_lite(text: str) -> dict[str, str]:
        """Minimal YAML parser — handles `key: value` lines only."""
        out: dict[str, str] = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            v = v.strip()
            if v.startswith('"') and v.endswith('"'):
                v = v[1:-1].replace('\\"', '"')
            out[k.strip()] = v
        return out
