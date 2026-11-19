"""Plain file store for text documents, used until a node has a text vault (M7 puts the vault on top)."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class FileDocuments:
    def __init__(self, data_dir: Path) -> None:
        self.dir = data_dir / "documents"
        self.dir.mkdir(parents=True, exist_ok=True)

    def add(self, doc_id: str, doc_type: str, text: str, meta: dict[str, Any]) -> None:
        body = {"doc_id": doc_id, "doc_type": doc_type, "text": text, "meta": meta,
                "stored_at": datetime.now(UTC).isoformat()}  # fmt: skip
        (self.dir / f"{doc_id}.json").write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")

    def get(self, doc_id: str) -> dict[str, Any] | None:
        path = self.dir / f"{doc_id}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def all(self) -> list[dict[str, Any]]:
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(self.dir.glob("*.json"))]
