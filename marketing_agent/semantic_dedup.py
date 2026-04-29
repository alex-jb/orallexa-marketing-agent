"""Semantic dedup — flag drafts that are paraphrases of past posts.

The string-hash dedup in memory.py catches exact reposts; this module
catches "I changed two words and posted again" — the actual problem at
30-day cadence.

Two backends:
  1. Local (default, no key): sentence-transformers all-MiniLM-L6-v2.
     ~80MB model, runs on CPU in ~50ms/post. Quality: 80% of Voyage-3
     for retrieval, free.
  2. Voyage (when VOYAGE_API_KEY set): voyage-3-large embeddings.
     Better recall on near-duplicates, $0.02/M tokens.

Storage: post embeddings cached in a single SQLite table (BLOB column).
On a new draft, we cosine-compare against all past (project, platform)
embeddings; max similarity > threshold → flag as near-duplicate.

Threshold: 0.92 cosine similarity. Tuned so "v0.3.0 shipped today" and
"v0.4.0 shipped today" don't collide (they shouldn't), but "Just shipped
v0.4 of marketing-agent" and "v0.4 of marketing-agent is out" do.

Graceful degradation: if sentence-transformers isn't installed, the
function returns 0.0 similarity (treated as "no duplicate found") so the
rest of the pipeline never breaks.
"""
from __future__ import annotations
import os
import sqlite3
import struct
from pathlib import Path
from typing import Optional

from marketing_agent.logging import get_logger
from marketing_agent.memory import _default_db_path
from marketing_agent.types import Platform

log = get_logger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS post_embeddings (
    content_hash  TEXT PRIMARY KEY,
    project_name  TEXT NOT NULL,
    platform      TEXT NOT NULL,
    body_preview  TEXT NOT NULL,
    embedding     BLOB NOT NULL,
    backend       TEXT NOT NULL,
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_emb_project_platform
    ON post_embeddings(project_name, platform);
"""

# Default near-duplicate threshold. Cosine sim above this → flag.
DEFAULT_THRESHOLD = 0.92


def _pack(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _unpack(blob: bytes) -> list[float]:
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _embed_voyage(text: str) -> Optional[list[float]]:
    """voyage-3-large via HTTP. Returns None on any failure."""
    if not os.getenv("VOYAGE_API_KEY"):
        return None
    try:
        import urllib.request
        import json as _json
        req = urllib.request.Request(
            "https://api.voyageai.com/v1/embeddings",
            data=_json.dumps({
                "model": "voyage-3-large",
                "input": [text[:8000]],
                "input_type": "document",
            }).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {os.getenv('VOYAGE_API_KEY')}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
        return data["data"][0]["embedding"]
    except Exception as e:
        log.debug("voyage embed failed: %s", e)
        return None


def _embed_local(text: str) -> Optional[list[float]]:
    """sentence-transformers MiniLM. Returns None if package unavailable."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return None
    # Cache the model on the function attribute so reload cost is paid once
    if not hasattr(_embed_local, "_model"):
        _embed_local._model = SentenceTransformer("all-MiniLM-L6-v2")  # type: ignore[attr-defined]
    vec = _embed_local._model.encode(text[:2000])  # type: ignore[attr-defined]
    return [float(x) for x in vec]


def embed(text: str) -> tuple[Optional[list[float]], str]:
    """Embed a string. Returns (vector_or_None, backend_used)."""
    v = _embed_voyage(text)
    if v is not None:
        return v, "voyage-3-large"
    v = _embed_local(text)
    if v is not None:
        return v, "minilm-local"
    return None, "none"


class SemanticDedupIndex:
    """SQLite-backed embedding index with cosine search."""

    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path) if db_path else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(_SCHEMA)

    def add(self, content_hash: str, body: str, *, project_name: str,
              platform: Platform) -> bool:
        """Embed and store. Returns True on success."""
        vec, backend = embed(body)
        if vec is None:
            return False
        from datetime import datetime, timezone
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO post_embeddings
                   (content_hash, project_name, platform, body_preview,
                    embedding, backend, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (content_hash, project_name, platform.value,
                 body[:200], _pack(vec), backend,
                 datetime.now(timezone.utc).isoformat()),
            )
        return True

    def nearest(self, body: str, *, project_name: Optional[str] = None,
                  platform: Optional[Platform] = None,
                  top_k: int = 1) -> list[dict]:
        """Find top-K nearest stored posts. Returns [] if can't embed."""
        query, _ = embed(body)
        if query is None:
            return []
        sql = "SELECT content_hash, project_name, platform, body_preview, embedding FROM post_embeddings WHERE 1=1"
        args: list = []
        if project_name:
            sql += " AND project_name = ?"; args.append(project_name)
        if platform:
            sql += " AND platform = ?"; args.append(platform.value)
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(sql, args).fetchall()
        scored = []
        for h, proj, plat, preview, emb in rows:
            sim = _cosine(query, _unpack(emb))
            scored.append({
                "content_hash": h, "project_name": proj, "platform": plat,
                "body_preview": preview, "similarity": round(sim, 4),
            })
        scored.sort(key=lambda r: r["similarity"], reverse=True)
        return scored[:top_k]

    def is_near_duplicate(self, body: str, *, project_name: str,
                            platform: Platform,
                            threshold: float = DEFAULT_THRESHOLD
                            ) -> tuple[bool, Optional[dict]]:
        """Return (is_dup, nearest_match_or_None)."""
        nearest = self.nearest(body, project_name=project_name,
                                 platform=platform, top_k=1)
        if not nearest:
            return False, None
        top = nearest[0]
        return top["similarity"] >= threshold, top
