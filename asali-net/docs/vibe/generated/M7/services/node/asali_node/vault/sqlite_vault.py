"""The vault, on SQLite FTS5 (TEXT_ML.md section 5; the engine differs, see CHANGES.md D13).

The portal writes through a read-write vault. The share API gets a second Vault opened with mode=ro, so
it can search and read but a write fails inside SQLite, the same way the database accounts do.
"""

import json
import re
import sqlite3
import threading
from pathlib import Path
from typing import Any

from asali_node.canonical import IST  # noqa: F401  (documents carry IST timestamps in created_at)

SCHEMA = """
CREATE TABLE IF NOT EXISTS docs (
  id TEXT PRIMARY KEY, org_id TEXT NOT NULL, doc_type TEXT NOT NULL, doc_type_declared TEXT, kind TEXT NOT NULL,
  title TEXT NOT NULL, body TEXT NOT NULL, language TEXT NOT NULL, created_at INTEGER NOT NULL,
  issue_labels TEXT NOT NULL DEFAULT '[]', mentions TEXT NOT NULL DEFAULT '{}', claims TEXT NOT NULL DEFAULT '[]',
  meta TEXT NOT NULL DEFAULT '{}', type_confidence REAL);
CREATE TABLE IF NOT EXISTS links (
  doc_id TEXT NOT NULL REFERENCES docs(id), entity_key TEXT NOT NULL, entity_type TEXT NOT NULL,
  confidence REAL NOT NULL, because TEXT NOT NULL DEFAULT '[]', rejected INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (doc_id, entity_key));
CREATE INDEX IF NOT EXISTS ix_links_key ON links(entity_key);
CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(id UNINDEXED, title, body, tokenize='unicode61');
"""


def _fts(q: str) -> str:
    words = re.findall(r"\w+", q.lower())
    return " OR ".join(f'"{w}"' for w in words[:12])


class Vault:
    def __init__(self, data_dir: Path, mode: str = "rw") -> None:
        self.dir = data_dir / "vault"
        self.mode = mode
        self._lock = threading.RLock()
        if mode == "rw":
            (self.dir / "text").mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.dir / "vault.sqlite", check_same_thread=False, timeout=10)
            self._conn.executescript(SCHEMA)
            self._conn.execute("PRAGMA journal_mode=WAL")
        else:
            uri = "file:" + str(self.dir / "vault.sqlite").replace("\\", "/") + "?mode=ro"
            self._conn = sqlite3.connect(uri, uri=True, check_same_thread=False, timeout=10)

    # ---- writing ----
    def put(self, doc: dict[str, Any], links: list[dict[str, Any]], original: str | None = None) -> None:
        with self._lock:
            c = self._conn
            c.execute("DELETE FROM docs_fts WHERE id = ?", (doc["id"],))
            c.execute(
                "INSERT OR REPLACE INTO docs (id, org_id, doc_type, doc_type_declared, kind, title, body, language, "
                "created_at, issue_labels, mentions, claims, meta, type_confidence) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (doc["id"], doc["org_id"], doc["doc_type"], doc.get("doc_type_declared"), doc["kind"], doc["title"],
                 doc["body"], doc["language"], doc["created_at"], json.dumps(doc.get("issue_labels", [])),
                 json.dumps(doc.get("mentions", {})), json.dumps(doc.get("claims", [])),
                 json.dumps(doc.get("meta", {})), doc.get("type_confidence")),
            )  # fmt: skip
            c.execute("INSERT INTO docs_fts (id, title, body) VALUES (?, ?, ?)", (doc["id"], doc["title"], doc["body"]))
            c.execute("DELETE FROM links WHERE doc_id = ? AND rejected = 0", (doc["id"],))
            for link in links:
                c.execute(
                    "INSERT OR IGNORE INTO links (doc_id, entity_key, entity_type, confidence, because) VALUES (?, ?, ?, ?, ?)",
                    (doc["id"], link["entity_key"], link["entity_type"], link["confidence"], json.dumps(link.get("because", []))),
                )  # fmt: skip
            c.commit()
            if original is not None:
                (self.dir / "text" / f"{doc['id']}.txt").write_text(original, encoding="utf-8")

    def reject_link(self, doc_id: str, entity_key: str) -> bool:
        with self._lock:
            cur = self._conn.execute("UPDATE links SET rejected = 1 WHERE doc_id = ? AND entity_key = ?", (doc_id, entity_key))
            self._conn.commit()
            return cur.rowcount > 0

    # ---- reading ----
    def _doc(self, row: tuple[Any, ...]) -> dict[str, Any]:
        keys = ["id", "org_id", "doc_type", "doc_type_declared", "kind", "title", "body", "language", "created_at",
                "issue_labels", "mentions", "claims", "meta", "type_confidence"]  # fmt: skip
        d = dict(zip(keys, row, strict=True))
        for k in ("issue_labels", "mentions", "claims", "meta"):
            d[k] = json.loads(d[k])
        d["links"] = [{"entity_key": k, "entity_type": t, "confidence": c, "because": json.loads(b)}
                      for k, t, c, b in self._conn.execute(
                          "SELECT entity_key, entity_type, confidence, because FROM links WHERE doc_id = ? AND rejected = 0 "
                          "ORDER BY confidence DESC", (d["id"],))]  # fmt: skip
        return d

    _COLS = ("id, org_id, doc_type, doc_type_declared, kind, title, body, language, created_at, issue_labels, "
             "mentions, claims, meta, type_confidence")  # fmt: skip

    def get(self, doc_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(f"SELECT {self._COLS} FROM docs WHERE id = ?", (doc_id,)).fetchone()
            return self._doc(row) if row else None

    def search(self, q: str = "", link_keys: list[str] | None = None, doc_types: list[str] | None = None,
               since: int | None = None, limit: int = 20) -> list[dict[str, Any]]:  # fmt: skip
        """Linked documents (link_keys) and/or text matches (q), newest first, with their links."""
        where, args = ["1=1"], []
        if link_keys:
            where.append("id IN (SELECT doc_id FROM links WHERE rejected = 0 AND entity_key IN (" + ",".join("?" * len(link_keys)) + "))")
            args += link_keys
        if q and _fts(q):
            where.append("id IN (SELECT id FROM docs_fts WHERE docs_fts MATCH ?)")
            args.append(_fts(q))
        if doc_types:
            where.append("doc_type IN (" + ",".join("?" * len(doc_types)) + ")")
            args += doc_types
        if since is not None:
            where.append("created_at >= ?")
            args.append(since)
        with self._lock:
            rows = self._conn.execute(f"SELECT {self._COLS} FROM docs WHERE {' AND '.join(where)} ORDER BY created_at DESC LIMIT ?", (*args, limit)).fetchall()
            return [self._doc(r) for r in rows]

    def listing(self, doc_type: str | None = None, linked: bool | None = None, limit: int = 100) -> list[dict[str, Any]]:
        where = ["1=1"] + (["doc_type = ?"] if doc_type else [])
        if linked is True:
            where.append("id IN (SELECT doc_id FROM links WHERE rejected = 0 AND confidence >= 0.8)")
        elif linked is False:
            where.append("id NOT IN (SELECT doc_id FROM links WHERE rejected = 0 AND confidence >= 0.8)")
        with self._lock:
            rows = self._conn.execute(f"SELECT {self._COLS} FROM docs WHERE {' AND '.join(where)} ORDER BY created_at DESC LIMIT ?", (*([doc_type] if doc_type else []), limit)).fetchall()
            return [self._doc(r) for r in rows]

    def unlinked(self, newer_than: int) -> list[dict[str, Any]]:
        """Documents with no link at 0.8 or more that are not too old (the relink task works on these)."""
        with self._lock:
            rows = self._conn.execute(
                f"SELECT {self._COLS} FROM docs WHERE created_at >= ? AND id NOT IN "
                "(SELECT doc_id FROM links WHERE rejected = 0 AND confidence >= 0.8)", (newer_than,)).fetchall()
            return [self._doc(r) for r in rows]

    def count(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0])

    def close(self) -> None:
        self._conn.close()
