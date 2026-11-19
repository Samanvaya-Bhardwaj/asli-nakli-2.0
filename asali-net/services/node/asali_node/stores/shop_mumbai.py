"""Apna Chemist, Mumbai: PostgreSQL, one inventory ledger. See schemas/shop-mumbai/MAPPING.md."""

from datetime import datetime

from asali_node.canonical import (
    Event,
    NewDispatch,
    NewReceipt,
    NewReturn,
    NewSale,
    Shipment,
    StockLine,
    UnitView,
)
from asali_node.stores.protocols import NotSupported
from asali_node.stores.sqlbase import to_ist
from asali_node.stores.sqlcommon import SqlStore, view

EVENT = {"IN": "receive", "SALE": "sell", "RETURN": "return", "DAMAGE": "destroy"}
STATUS = {"IN": "in_stock", "SALE": "sold", "RETURN": "returned", "DAMAGE": "destroyed"}
_LAST = "l.entry_id = (SELECT MAX(m.entry_id) FROM inventory_ledger m WHERE m.gtin = l.gtin AND m.serial = l.serial)"


class ShopMumbaiStore(SqlStore):
    ENGINE = "pg"
    ORG = "shop-mumbai"

    def record_receipt(self, r: NewReceipt) -> None:
        with self.db.tx() as tx:
            for u in r.units:
                tx.run(
                    "INSERT INTO inventory_ledger (kind, gtin, serial, counterparty, doc_no, at) "
                    "VALUES ('IN', ?, ?, ?, ?, ?)", u.gtin, u.serial, r.from_org, r.source_ref, r.at,
                )  # fmt: skip

    def received_refs(self) -> set[tuple[str, str]]:
        rows = self.db.rows("SELECT DISTINCT counterparty, doc_no FROM inventory_ledger WHERE kind = 'IN'")
        return {(a, b) for a, b in rows}

    def record_dispatch(self, d: NewDispatch) -> Shipment:
        raise NotSupported("a shop does not dispatch to other organisations")

    def _last_kind(self, tx, gtin: str, serial: str) -> str | None:  # type: ignore[no-untyped-def]
        rows = tx.rows(
            "SELECT kind FROM inventory_ledger WHERE gtin = ? AND serial = ? ORDER BY entry_id DESC LIMIT 1",
            gtin,
            serial,
        )
        return str(rows[0][0]) if rows else None

    def record_sale(self, s: NewSale) -> None:
        with self.db.tx() as tx:
            for line in s.lines:
                if self._last_kind(tx, line.gtin, line.serial) != "IN":
                    raise ValueError(f"{line.serial} is not in stock")
            tx.run("INSERT INTO bills (doc_no, at, amount_paise, customer_ref_hash) VALUES (?, ?, ?, ?)",
                   s.bill_no, s.at, sum(x.mrp_paise for x in s.lines), s.customer_ref_hash)  # fmt: skip
            for line in s.lines:
                tx.run("INSERT INTO inventory_ledger (kind, gtin, serial, counterparty, doc_no, at) "
                       "VALUES ('SALE', ?, ?, NULL, ?, ?)", line.gtin, line.serial, s.bill_no, s.at)  # fmt: skip

    def record_return(self, r: NewReturn) -> None:
        with self.db.tx() as tx:
            sold = tx.rows(
                "SELECT 1 FROM inventory_ledger WHERE kind = 'SALE' AND doc_no = ? AND serial = ?",
                r.bill_no,
                r.serial,
            )
            if not sold or self._last_kind(tx, r.gtin, r.serial) != "SALE":
                raise ValueError(f"{r.serial} was not sold on bill {r.bill_no}")
            tx.run("INSERT INTO inventory_ledger (kind, gtin, serial, counterparty, doc_no, at) "
                   "VALUES ('RETURN', ?, ?, ?, ?, ?)", r.gtin, r.serial, r.reason, r.bill_no, r.at)  # fmt: skip

    def unit_view(self, gtin: str, serial: str) -> UnitView:
        rows = self.db.rows(
            "SELECT entry_id, kind, counterparty, doc_no, at FROM inventory_ledger WHERE gtin = ? AND serial = ? "
            "ORDER BY entry_id", gtin, serial,
        )  # fmt: skip
        if not rows:
            return view(gtin, serial, [], "never_held")
        events = [
            Event(event_id=f"shop-mumbai:{eid}", org_id=self.ORG, event_type=EVENT[kind], at=to_ist(at),  # type: ignore[arg-type]
                  gtin=gtin, serial=serial, from_org=who if kind == "IN" else None, ref=doc, city=self.city)
            for eid, kind, who, doc, at in rows
        ]  # fmt: skip
        return view(gtin, serial, events, STATUS[rows[-1][1]])

    def stock(self) -> list[StockLine]:
        rows = self.db.rows(
            f"SELECT l.gtin, l.serial, l.at FROM inventory_ledger l WHERE l.kind = 'IN' AND {_LAST} ORDER BY l.serial"
        )
        return [StockLine(gtin=g, serial=s, lot=None, expiry=None, since=to_ist(t)) for g, s, t in rows]

    def shipments_to(self, org_id: str, since: datetime | None = None) -> list[Shipment]:
        return []
