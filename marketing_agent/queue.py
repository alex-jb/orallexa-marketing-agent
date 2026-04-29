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
                generated_by: str = "auto", *,
                gate: bool = True,
                min_score: float = 4.0,
                dedup_threshold: float = 0.92) -> Path:
        """Write a post into pending/ (or rejected/ if it fails the gate).

        Args:
            gate: When True, run critic + semantic-dedup before queuing.
                  Failing drafts go to rejected/ with reason in frontmatter.
                  Pass gate=False to bypass (e.g. for unit tests).
            min_score: Critic score below this → auto-reject.
            dedup_threshold: Cosine sim above this → auto-reject as near-dup.

        Returns the path of the saved file (in pending/ or rejected/).
        """
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        slug = re.sub(r"[^a-z0-9]+", "-", project_name.lower()).strip("-")
        fname = f"{ts}-{slug}-{post.platform.value}.md"

        gate_note: Optional[str] = None
        target_dir = "pending"
        if gate:
            try:
                from marketing_agent.critic import critique
                from marketing_agent.semantic_dedup import SemanticDedupIndex
                from marketing_agent.memory import _hash

                crit = critique(post, project_name=project_name,
                                  min_score=min_score, use_llm=True)
                if crit.auto_reject:
                    gate_note = (f"auto-rejected by critic (score {crit.score}/10): "
                                  f"{'; '.join(crit.reasons) or 'low quality'}")
                    target_dir = "rejected"
                else:
                    idx = SemanticDedupIndex(db_path=self._db_path_for_dedup())
                    is_dup, near = idx.is_near_duplicate(
                        post.body, project_name=project_name,
                        platform=post.platform, threshold=dedup_threshold,
                    )
                    if is_dup and near:
                        gate_note = (f"auto-rejected as near-duplicate "
                                      f"(sim {near['similarity']}): "
                                      f"{near['body_preview'][:80]}")
                        target_dir = "rejected"
                    else:
                        # Index this post for future dedup checks
                        idx.add(_hash(post), post.body,
                                  project_name=project_name,
                                  platform=post.platform)
            except Exception:
                # Gate must never block submission on its own bugs;
                # log and pass through.
                pass

        path = self.root / target_dir / fname
        path.write_text(self._render(post, project_name, generated_by, gate_note))
        return path

    @staticmethod
    def _db_path_for_dedup():
        from marketing_agent.memory import _default_db_path
        return _default_db_path()

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

    def _render(self, post: Post, project_name: str, generated_by: str,
                  gate_note: Optional[str] = None) -> str:
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
        if post.variant_key:
            front.append(f"variant_key: {post.variant_key}")
        front.append(f"char_count: {post.char_count or len(post.body)}")
        if gate_note:
            front.append(f"gate_note: {self._yaml_escape(gate_note)}")
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
