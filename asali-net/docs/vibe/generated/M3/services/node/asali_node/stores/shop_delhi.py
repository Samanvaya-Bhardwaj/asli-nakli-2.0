"""Sharma Medicos, Delhi: SQLite, purchase and sale bills. See schemas/shop-delhi/MAPPING.md."""

from datetime import datetime

from asali_node.canonical import Event, NewDispatch, NewReceipt, NewReturn, NewSale, Shipment, StockLine, UnitView
from asali_node.stores.protocols import NotSupported
from asali_node.stores.sqlbase import new_id, to_date, to_ist
from asali_node.stores.sqlcommon import SqlStore, chunks, in_clause, view

# a pack is in stock when it was bought and no sale or return has been recorded since
_IN_STOCK = (
    "NOT EXISTS (SELECT 1 FROM sale_items si JOIN sales s ON s.bill_no = si.bill_no "
    "WHERE si.sn = pi.sn AND s.sold_at >= p.bill_date)"
)


class ShopDelhiStore(SqlStore):
    ORG = "shop-delhi"
    STAFF = ("users", "username", "pw_hash", "user_role", "full_name")
    CORR = ("scan_fixes", "fixed_at", "raw", "which", "chosen", "cost", "by_user")
    DOCLNK = ("doc_links", "doc_id", "ent_type", "ent_key", "conf", "linked_at")

    def record_receipt(self, r: NewReceipt) -> None:
        pur = new_id("PUR")
        with self.db.tx() as tx:
            tx.run(
                "INSERT INTO purchases (pur_id, distributor_org, bill_no, bill_date) VALUES (?, ?, ?, ?)",
                pur, r.from_org, r.source_ref, r.at,
            )  # fmt: skip
            for u in r.units:
                tx.run(
                    "INSERT INTO purchase_items (pur_id, gtin, sn, lot, exp) VALUES (?, ?, ?, ?, ?)",
                    pur, u.gtin, u.serial, u.lot, u.expiry,
                )  # fmt: skip

    def received_refs(self) -> set[tuple[str, str]]:
        return {(a, b) for a, b in self.db.rows("SELECT distributor_org, bill_no FROM purchases")}

    def record_dispatch(self, d: NewDispatch) -> Shipment:
        raise NotSupported("a shop does not dispatch to other organisations")

    def _in_stock(self, tx, serials: list[str]) -> set[str]:  # type: ignore[no-untyped-def]
        found: set[str] = set()
        for part in chunks(serials):
            rows = tx.rows(
                "SELECT pi.sn FROM purchase_items pi JOIN purchases p ON p.pur_id = pi.pur_id "
                f"WHERE pi.sn IN {in_clause(len(part))} AND {_IN_STOCK}", *part,
            )  # fmt: skip
            found |= {r[0] for r in rows}
        return found

    def record_sale(self, s: NewSale) -> None:
        with self.db.tx() as tx:
            wanted = [line.serial for line in s.lines]
            missing = set(wanted) - self._in_stock(tx, wanted)
            if missing:
                raise ValueError(f"not in stock: {sorted(missing)[:3]}")
            tx.run(
                "INSERT INTO sales (bill_no, sold_at, customer_ref_hash, total_paise) VALUES (?, ?, ?, ?)",
                s.bill_no, s.at, s.customer_ref_hash, sum(line.mrp_paise for line in s.lines),
            )  # fmt: skip
            for line in s.lines:
                tx.run(
                    "INSERT INTO sale_items (bill_no, gtin, sn, mrp_paise) VALUES (?, ?, ?, ?)",
                    s.bill_no, line.gtin, line.serial, line.mrp_paise,
                )  # fmt: skip

    def record_return(self, r: NewReturn) -> None:
        with self.db.tx() as tx:
            sold = tx.rows("SELECT 1 FROM sale_items WHERE bill_no = ? AND sn = ?", r.bill_no, r.serial)
            if not sold:
                raise ValueError(f"{r.serial} was not sold on bill {r.bill_no}")
            tx.run(
                "INSERT INTO returns (ret_id, bill_no, sn, reason, at) VALUES (?, ?, ?, ?, ?)",
                new_id("RET"), r.bill_no, r.serial, r.reason, r.at,
            )  # fmt: skip

    def unit_view(self, gtin: str, serial: str) -> UnitView:
        buys = self.db.rows(
            "SELECT p.pur_id, p.distributor_org, p.bill_no, p.bill_date, pi.lot, pi.exp FROM purchase_items pi "
            "JOIN purchases p ON p.pur_id = pi.pur_id WHERE pi.sn = ? AND pi.gtin = ?", serial, gtin,
        )  # fmt: skip
        if not buys:
            return view(gtin, serial, [], "never_held")
        sells = self.db.rows(
            "SELECT s.bill_no, s.sold_at FROM sale_items si JOIN sales s ON s.bill_no = si.bill_no "
            "WHERE si.sn = ? AND si.gtin = ?", serial, gtin,
        )  # fmt: skip
        rets = self.db.rows("SELECT ret_id, bill_no, at FROM returns WHERE sn = ?", serial)
        events = [
            Event(event_id=f"shop-delhi:{pur}:{serial}", org_id=self.ORG, event_type="receive", at=to_ist(at),
                  gtin=gtin, serial=serial, lot=lot, from_org=org, ref=bill, city=self.city)
            for pur, org, bill, at, lot, _exp in buys
        ]  # fmt: skip
        events += [
            Event(event_id=f"shop-delhi:sale:{bill}:{serial}", org_id=self.ORG, event_type="sell", at=to_ist(at),
                  gtin=gtin, serial=serial, ref=bill, city=self.city)
            for bill, at in sells
        ]  # fmt: skip
        events += [
            Event(event_id=f"shop-delhi:{rid}", org_id=self.ORG, event_type="return", at=to_ist(at),
                  gtin=gtin, serial=serial, ref=bill, city=self.city)
            for rid, bill, at in rets
        ]  # fmt: skip
        rank = {"receive": 0, "sell": 1, "return": 2}
        last = max(events, key=lambda e: (e.at, rank[e.event_type]))
        status = {"receive": "in_stock", "sell": "sold", "return": "returned"}[last.event_type]
        return view(gtin, serial, events, status, buys[-1][4], to_date(buys[-1][5]) if buys[-1][5] else None)

    def stock(self) -> list[StockLine]:
        rows = self.db.rows(
            "SELECT pi.gtin, pi.sn, pi.lot, pi.exp, p.bill_date FROM purchase_items pi "
            f"JOIN purchases p ON p.pur_id = pi.pur_id WHERE {_IN_STOCK} "
            "AND NOT EXISTS (SELECT 1 FROM returns r WHERE r.sn = pi.sn AND r.at >= p.bill_date) ORDER BY pi.sn"
        )
        return [
            StockLine(gtin=g, serial=s, lot=lot, expiry=to_date(e) if e else None, since=to_ist(at))
            for g, s, lot, e, at in rows
        ]

    def shipments_to(self, org_id: str, since: datetime | None = None) -> list[Shipment]:
        return []
