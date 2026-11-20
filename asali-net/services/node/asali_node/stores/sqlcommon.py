"""Shared base of the SQL adapters: staff, scan corrections and document links.

Each organisation names these three tables its own way (Kesar: USR_MST, SCN_CORR, DOC_LNK), so the
subclass says which table and columns to use. Everything else is that organisation's own code.
"""

import re
from datetime import datetime
from typing import Any

from asali_node.canonical import (
    IST,
    Batch,
    DocLink,
    Event,
    Product,
    ScanCorrection,
    StaffRecord,
    UnitView,
)  # fmt: skip
from asali_node.context.explore import INFRA_TABLES, Roots, explore
from asali_node.context.graph import SqlGraph
from asali_node.stores.sqlbase import SqlDb

LOT_COLUMN = re.compile(r"^(lot|lot_no|lot_number)$", re.I)


def view(
    gtin: str, serial: str, events: list[Event], status: str, lot: str | None = None, expiry: Any = None
) -> UnitView:
    events = sorted(events, key=lambda e: e.at)
    return UnitView(
        gtin=gtin,
        serial=serial,
        known=bool(events) or status != "never_held",
        lot=lot,
        expiry=expiry,
        status_here=status,
        events=events,
    )  # type: ignore[arg-type]


def party_kind(org_id: str) -> str:
    """The kind of organisation an id names, from the network's naming (dist-north, shop-delhi, consumer-delhi)."""
    for prefix, kind in (
        ("dist-", "distributor"),
        ("shop-", "shop"),
        ("consumer-", "consumer"),
        ("regulator", "regulator"),
    ):
        if org_id.startswith(prefix):
            return kind
    return "pharma"


def in_clause(n: int) -> str:
    return "(" + ",".join("?" * n) + ")"


def chunks(items: list[str], size: int = 400) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


class SqlStore:
    ENGINE = "sqlite"
    ORG = ""
    STAFF = ("staff", "username", "password_hash", "role", "display_name")
    CORR = ("scan_corrections", "at", "raw", "field", "chosen", "cost", "confirmed_by")
    DOCLNK = ("document_links", "doc_id", "entity_type", "entity_key", "confidence", "linked_at")
    CONTEXT_ROOTS: Roots = ()  # (table, column, "serial" | "gtin" | "lot"): where this organisation's rows mention a pack

    def context_for(
        self, gtin: str | None, serial: str | None, lot: str | None, keywords: list[str], params: dict[str, Any] | None = None
    ) -> dict[str, Any]:  # fmt: skip
        """Phase 3: the context this database finds for a pack, through its own foreign keys (context/)."""
        graph = SqlGraph(self.db, skip_tables=INFRA_TABLES)
        return explore(
            graph,
            list(self.CONTEXT_ROOTS),
            {"serial": serial, "gtin": gtin, "lot": lot},
            self.ORG,
            keywords,
            params,
        )

    def recorded_serials(self) -> list[dict[str, Any]]:
        """Every distinct code this organisation has recorded, where, how many rows, and the lot beside it if there is one."""
        graph = SqlGraph(self.db, skip_tables=INFRA_TABLES)
        out: dict[str, dict[str, Any]] = {}
        for table, column, kind in self.CONTEXT_ROOTS:
            if kind != "serial":
                continue
            lot_col = next((c for c in graph.fields(table) if LOT_COLUMN.match(c)), None)
            lot_sql = f', MIN("{lot_col}")' if lot_col else ", NULL"
            for value, rows, lot in self.db.rows(
                f'SELECT "{column}", COUNT(*){lot_sql} FROM "{table}" GROUP BY "{column}"'
            ):
                if value is None:
                    continue
                e = out.setdefault(
                    str(value), {"table": table, "column": column, "value": str(value), "rows": 0, "lot": lot}
                )
                e["rows"] += int(rows)
        return list(out.values())

    def rename_serial(self, old: str, new: str) -> int:
        """Change a recorded code everywhere this organisation records it. Returns the rows changed."""
        total = 0
        for table, column, kind in self.CONTEXT_ROOTS:
            if kind != "serial":
                continue
            n = int(self.db.rows(f'SELECT COUNT(*) FROM "{table}" WHERE "{column}" = ?', old)[0][0])
            if n:
                self.db.run(f'UPDATE "{table}" SET "{column}" = ? WHERE "{column}" = ?', new, old)
                total += n
        return total

    def __init__(self, target: str, mode: str = "rw", city: str = ""):
        self.db = SqlDb(self.ENGINE, target, mode)
        self.mode = mode
        self.city = city

    @property
    def org_id(self) -> str:
        return self.ORG

    def init_schema(self) -> None:
        self.db.script(self.ORG)

    def close(self) -> None:
        self.db.close()

    # ---- staff ----
    def get_staff(self, username: str) -> StaffRecord | None:
        t, u, p, r, n = self.STAFF
        rows = self.db.rows(f"SELECT {u}, {p}, {r}, {n} FROM {t} WHERE {u} = ?", username)
        if not rows:
            return None
        return StaffRecord(username=rows[0][0], password_hash=rows[0][1], role=rows[0][2],
                           display_name=rows[0][3])  # fmt: skip

    def add_staff(self, rec: StaffRecord) -> None:
        t, u, p, r, n = self.STAFF
        self.db.run(f"INSERT INTO {t} ({u}, {p}, {r}, {n}) VALUES (?, ?, ?, ?)",
                    rec.username, rec.password_hash, rec.role, rec.display_name)  # fmt: skip

    # ---- scan corrections and document links ----
    def add_scan_correction(self, c: ScanCorrection) -> None:
        t, *cols = self.CORR
        self.db.run(f"INSERT INTO {t} ({', '.join(cols)}) VALUES (?, ?, ?, ?, ?, ?)",
                    c.at, c.raw, c.field, c.chosen, c.cost, c.confirmed_by)  # fmt: skip

    def upsert_document_links(self, doc_id: str, links: list[DocLink]) -> None:
        t, d, et, ek, cf, ts = self.DOCLNK
        with self.db.tx() as tx:
            tx.run(f"DELETE FROM {t} WHERE {d} = ?", doc_id)
            for link in links:
                tx.run(f"INSERT INTO {t} ({d}, {et}, {ek}, {cf}, {ts}) VALUES (?, ?, ?, ?, ?)",
                       doc_id, link.entity_type, link.entity_key, link.confidence, link.linked_at)  # fmt: skip

    def documents_linked_to(self, entity_keys: list[str]) -> list[str]:
        if not entity_keys:
            return []
        t, d, _et, ek, _cf, _ts = self.DOCLNK
        out: list[str] = []
        for part in chunks(entity_keys):
            rows = self.db.rows(f"SELECT DISTINCT {d} FROM {t} WHERE {ek} IN {in_clause(len(part))}", *part)
            out += [r[0] for r in rows if r[0] not in out]
        return sorted(out)


def product_from(
    gtin: str, brand: str, generic: str, strength: str, form: str, pack: int,
    lo: float | None, hi: float | None, owner: str,
) -> Product:  # fmt: skip
    return Product(gtin=gtin, brand=brand, generic=generic, strength=strength, form=form,  # type: ignore[arg-type]
                   pack_size=pack, storage_min_c=lo, storage_max_c=hi, owner_org=owner)  # fmt: skip


def batch_from(gtin: str, lot: str, mfg: Any, exp: Any, status: str, owner: str) -> Batch:
    return Batch(gtin=gtin, lot=lot, mfg_date=mfg, expiry_date=exp, status=status, owner_org=owner)  # type: ignore[arg-type]


def ist_now() -> datetime:
    return datetime.now(IST)
