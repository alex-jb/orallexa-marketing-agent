"""JSONL append store with dedup on (source, item_id)."""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Iterable

from marketing_agent.signals.base import ScrapedItem


def _default_root() -> Path:
    return Path(os.environ.get(
        "MARKETING_AGENT_HOME",
        Path.home() / ".marketing_agent",
    )) / "signals"


class SignalStore:
    """Append-only JSONL signal store, one file per source.

    Dedup key: (source, item_id). On append, we load existing ids in O(N) once
    and skip duplicates. Acceptable up to ~100k rows per source; if a source
    grows beyond that we'll switch to a sqlite index.
    """

    def __init__(self, root: Path | None = None):
        self.root = root or _default_root()
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, source: str) -> Path:
        return self.root / f"{source}.jsonl"

    def existing_ids(self, source: str) -> set[str]:
        p = self.path_for(source)
        if not p.exists():
            return set()
        ids: set[str] = set()
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            iid = row.get("item_id")
            if iid:
                ids.add(iid)
        return ids

    def append(self, items: Iterable[ScrapedItem]) -> int:
        """Append items, skipping duplicates. Returns count of new rows."""
        items = list(items)
        if not items:
            return 0
        source = items[0].source
        for it in items:
            if it.source != source:
                raise ValueError(
                    f"mixed sources in one append batch: {it.source} vs {source}"
                )
        seen = self.existing_ids(source)
        new_rows = [it for it in items if it.item_id not in seen]
        if not new_rows:
            return 0
        p = self.path_for(source)
        with p.open("a", encoding="utf-8") as f:
            for it in new_rows:
                f.write(json.dumps(it.to_dict(), ensure_ascii=False) + "\n")
        return len(new_rows)
