"""Semantic dedup — flag drafts that are paraphrases of past posts.

The string-hash dedup in memory.py catches exact reposts; this module
catches "I changed two words and posted again" — the actual problem at
30-day cadence.

**v0.6 upgrade (per Q1 2026 retrieval benchmarks): hybrid score = 0.6 *
dense_cosine + 0.4 * bm25_normalized.** Hybrid retrieval beats dense-alone
by ~17pp MRR@3 on paraphrase tasks (arxiv 2604.01733). BM25 catches
exact-overlap that dense embeddings smooth over; dense catches semantic
paraphrases BM25 misses. Together they're robust.

Two backends for the dense half:
  1. Local (default, no key): sentence-transformers all-MiniLM-L6-v2.
     ~80MB model, runs on CPU in ~50ms/post. Quality: 80% of Voyage-3
     for retrieval, free.
  2. Voyage (when VOYAGE_API_KEY set): voyage-3-large embeddings.
     Better recall on near-duplicates, $0.02/M tokens.

BM25 always runs (pure Python; we ship a tiny implementation inline so
there's no rank_bm25 dependency). Disable hybrid scoring with
`hybrid=False` to fall back to dense-only.

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


# ───── BM25 (pure Python, no rank_bm25 dep) ─────
import math as _math
import re as _re


def _tokenize(text: str) -> list[str]:
    """Lowercase word-tokenization. Good enough for short marketing posts."""
    return [t for t in _re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 1]


def _bm25_score(query_tokens: list[str], doc_tokens: list[str],
                  corpus_token_lists: list[list[str]],
                  k1: float = 1.5, b: float = 0.75) -> float:
    """Score one (query, doc) pair against a corpus. Returns BM25 raw score.

    Standard Robertson/Walker formulation. Treats every doc as length-normalized
    by the corpus average. Returns 0 when the corpus is empty.
    """
    if not corpus_token_lists or not doc_tokens or not query_tokens:
        return 0.0
    N = len(corpus_token_lists)
    avgdl = sum(len(d) for d in corpus_token_lists) / N
    # term-doc frequencies for IDF
    df: dict[str, int] = {}
    for d in corpus_token_lists:
        for t in set(d):
            df[t] = df.get(t, 0) + 1
    score = 0.0
    doc_freq: dict[str, int] = {}
    for t in doc_tokens:
        doc_freq[t] = doc_freq.get(t, 0) + 1
    dl = len(doc_tokens)
    for t in query_tokens:
        n = df.get(t, 0)
        if n == 0:
            continue
        idf = _math.log((N - n + 0.5) / (n + 0.5) + 1.0)
        f = doc_freq.get(t, 0)
        score += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avgdl))
    return score


def _normalize_bm25(scores: list[float]) -> list[float]:
    """Min-max into [0, 1] so it composes with cosine similarity.

    Edge cases:
      - Empty list → [].
      - Single non-zero score → [0.5]. With only one corpus doc we have
        no reference for what "high" BM25 means, so we return a neutral
        midpoint instead of biasing dedup toward "this is the best match"
        (was [1.0] in v0.6, which over-confidently flagged single-corpus
        cases as near-duplicates).
      - All-zero or all-equal across multiple → all 0.0.
    """
    if not scores:
        return []
    if len(scores) == 1:
        return [0.5 if scores[0] > 0 else 0.0]
    lo, hi = min(scores), max(scores)
    if hi <= lo:
        return [0.0 for _ in scores]
    return [(s - lo) / (hi - lo) for s in scores]


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
                  top_k: int = 1, hybrid: bool = True,
                  dense_weight: float = 0.6) -> list[dict]:
        """Find top-K nearest stored posts using hybrid dense+BM25 scoring.

        Returns rows with `similarity` = hybrid score (or pure cosine if
        hybrid=False or BM25 corpus is empty).
        """
        query_vec, _ = embed(body)
        sql = ("SELECT content_hash, project_name, platform, body_preview, "
                "embedding FROM post_embeddings WHERE 1=1")
        args: list = []
        if project_name:
            sql += " AND project_name = ?"; args.append(project_name)
        if platform:
            sql += " AND platform = ?"; args.append(platform.value)
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(sql, args).fetchall()

        if not rows:
            return []

        # Dense scores (or None if no embedder available)
        dense_scores: list[float] = []
        if query_vec is not None:
            for _h, _p, _pl, _prev, emb in rows:
                dense_scores.append(_cosine(query_vec, _unpack(emb)))
        else:
            dense_scores = [0.0] * len(rows)

        # BM25 scores (always available; pure Python)
        if hybrid:
            corpus_tokens = [_tokenize(r[3]) for r in rows]  # body_preview
            q_tokens = _tokenize(body)
            raw = [_bm25_score(q_tokens, doc, corpus_tokens) for doc in corpus_tokens]
            bm25_norm = _normalize_bm25(raw)
        else:
            bm25_norm = [0.0] * len(rows)

        scored = []
        bm25_weight = 1.0 - dense_weight
        for (h, proj, plat, preview, _emb), d, b in zip(rows, dense_scores, bm25_norm):
            if hybrid and query_vec is not None:
                hybrid_score = dense_weight * d + bm25_weight * b
            elif hybrid and query_vec is None:
                hybrid_score = b  # BM25-only when no embedder
            else:
                hybrid_score = d
            scored.append({
                "content_hash": h, "project_name": proj, "platform": plat,
                "body_preview": preview,
                "similarity": round(hybrid_score, 4),
                "dense": round(d, 4), "bm25": round(b, 4),
            })
        scored.sort(key=lambda r: r["similarity"], reverse=True)
        return scored[:top_k]

    def is_near_duplicate(self, body: str, *, project_name: str,
                            platform: Platform,
                            threshold: float = DEFAULT_THRESHOLD,
                            hybrid: bool = True,
                            ) -> tuple[bool, Optional[dict]]:
        """Return (is_dup, nearest_match_or_None)."""
        nearest = self.nearest(body, project_name=project_name,
                                 platform=platform, top_k=1, hybrid=hybrid)
        if not nearest:
            return False, None
        top = nearest[0]
        return top["similarity"] >= threshold, top
