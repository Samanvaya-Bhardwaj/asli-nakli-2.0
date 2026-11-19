"""Shared base of the MongoDB adapters: staff, scan corrections, document links, validators and indexes.

Collection and field names are the organisation's own (camelCase). Each organisation also ships
``schemas/<org-id>/validators.json`` with a ``$jsonSchema`` per collection and its indexes.
"""

import json
from datetime import UTC, date, datetime
from typing import Any

from asali_node.canonical import DocLink, ScanCorrection, StaffRecord, UnitView
from asali_node.stores import engines
from asali_node.stores.sqlbase import SCHEMAS
from asali_node.stores.sqlcommon import view as _view

view = _view


def d2dt(d: date) -> datetime:
    """MongoDB has no date-only type: a date is stored as midnight UTC."""
    return datetime(d.year, d.month, d.day, tzinfo=UTC)


def dt2d(v: datetime) -> date:
    return v.astimezone(UTC).date() if v.tzinfo else v.date()


def unknown_unit(gtin: str, serial: str) -> UnitView:
    return view(gtin, serial, [], "never_held")


class MongoStore:
    ORG = ""

    def __init__(self, target: str, mode: str = "rw", city: str = ""):
        self.db: Any = engines.mongo_db(target)
        self.mode, self.city = mode, city

    @property
    def org_id(self) -> str:
        return self.ORG

    def close(self) -> None:
        self.db.client.close()

    def init_schema(self) -> None:
        spec = json.loads((SCHEMAS / self.ORG / "validators.json").read_text(encoding="utf-8"))
        existing = set(self.db.list_collection_names())
        for name, validator in spec["collections"].items():
            if name not in existing:
                self.db.create_collection(name, validator={"$jsonSchema": validator})
        for name, indexes in spec["indexes"].items():
            for ix in indexes:
                self.db[name].create_index(
                    [tuple(k) for k in ix["keys"]], unique=ix.get("unique", False), name=ix.get("name")
                )

    # ---- staff, corrections, document links ----
    def get_staff(self, username: str) -> StaffRecord | None:
        d = self.db["staff"].find_one({"_id": username})
        if d is None:
            return None
        return StaffRecord(username=d["_id"], password_hash=d["hash"], role=d["role"], display_name=d["name"])

    def add_staff(self, rec: StaffRecord) -> None:
        self.db["staff"].insert_one(
            {"_id": rec.username, "hash": rec.password_hash, "role": rec.role, "name": rec.display_name}
        )

    def add_scan_correction(self, c: ScanCorrection) -> None:
        self.db["scanFixes"].insert_one(
            {
                "at": c.at,
                "raw": c.raw,
                "field": c.field,
                "chosen": c.chosen,
                "cost": c.cost,
                "by": c.confirmed_by,
            }
        )

    def upsert_document_links(self, doc_id: str, links: list[DocLink]) -> None:
        self.db["docLinks"].delete_many({"docId": doc_id})
        if links:
            self.db["docLinks"].insert_many(
                [
                    {"docId": doc_id, "entityType": x.entity_type, "entityKey": x.entity_key,
                     "confidence": x.confidence, "linkedAt": x.linked_at}
                    for x in links
                ]
            )  # fmt: skip

    def documents_linked_to(self, entity_keys: list[str]) -> list[str]:
        if not entity_keys:
            return []
        return sorted(self.db["docLinks"].distinct("docId", {"entityKey": {"$in": entity_keys}}))
