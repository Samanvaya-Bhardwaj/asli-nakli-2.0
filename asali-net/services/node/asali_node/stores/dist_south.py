"""Dakshin Pharma Agencies: SQLite, inward and outward registers with raw scan text. See MAPPING.md."""

from datetime import datetime

from asali_node.canonical import (
    Event,
    NewDispatch,
    NewReceipt,
    NewReturn,
    NewSale,
    Shipment,
    StockLine,
    UnitRef,
    UnitView,
)
from asali_node.stores.protocols import NotSupported
from asali_node.stores.sqlbase import to_date, to_ist
from asali_node.stores.sqlcommon import SqlStore, chunks, in_clause, view

_IN_STOCK = (
    "NOT EXISTS (SELECT 1 FROM outward_lines ol JOIN outward o ON o.entry_id = ol.entry_id "
    "WHERE ol.sn = il.sn AND o.entry_date >= i.entry_date)"
)


def _day(d: datetime) -> str:
    return to_ist(d).date().isoformat()


def _midnight(day: str) -> datetime:
    return to_ist(day)


class DistSouthStore(SqlStore):
    ORG = "dist-south"
    STAFF = ("users", "username", "pw_hash", "user_role", "full_name")
    CORR = ("scan_fixes", "fixed_at", "raw", "which", "chosen", "cost", "by_user")
    DOCLNK = ("doc_refs", "doc_id", "ent_type", "ent_key", "conf", "linked_at")

    def record_receipt(self, r: NewReceipt) -> None:
        with self.db.tx() as tx:
            tx.run(
                "INSERT INTO inward (supplier_org, dc_number, entry_date) VALUES (?, ?, ?)",
                r.from_org, r.source_ref, _day(r.at),
            )  # fmt: skip
            entry = tx.rows("SELECT last_insert_rowid()")[0][0]
            for u in r.units:
                tx.run(
                    "INSERT INTO inward_lines (entry_id, barcode_raw, gtin, sn, lot, exp, corrected) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    entry, u.raw, u.gtin, u.serial, u.lot, u.expiry, int(u.corrected),
                )  # fmt: skip

    def received_refs(self) -> set[tuple[str, str]]:
        return {(a, b) for a, b in self.db.rows("SELECT supplier_org, dc_number FROM inward")}

    def _stock_serials(self, tx, serials: list[str]) -> set[str]:  # type: ignore[no-untyped-def]
        found: set[str] = set()
        for part in chunks(serials):
            rows = tx.rows(
                "SELECT il.sn FROM inward_lines il JOIN inward i ON i.entry_id = il.entry_id "
                f"WHERE il.sn IN {in_clause(len(part))} AND {_IN_STOCK}", *part,
            )  # fmt: skip
            found |= {r[0] for r in rows}
        return found

    def record_dispatch(self, d: NewDispatch) -> Shipment:
        with self.db.tx() as tx:
            missing = {u.serial for u in d.units} - self._stock_serials(tx, [u.serial for u in d.units])
            if missing:
                raise ValueError(f"not in stock: {sorted(missing)[:3]}")
            tx.run(
                "INSERT INTO outward (customer_org, invoice_no, entry_date) VALUES (?, ?, ?)",
                d.to_org, d.shipment_id, _day(d.at),
            )  # fmt: skip
            entry = tx.rows("SELECT last_insert_rowid()")[0][0]
            for u in d.units:
                tx.run(
                    "INSERT INTO outward_lines (entry_id, barcode_raw, gtin, sn) VALUES (?, ?, ?, ?)",
                    entry, u.raw, u.gtin, u.serial,
                )  # fmt: skip
        return Shipment(
            shipment_id=d.shipment_id,
            from_org=self.ORG,
            to_org=d.to_org,
            at=_midnight(_day(d.at)),
            units=d.units,
        )

    def record_sale(self, s: NewSale) -> None:
        raise NotSupported("a distributor does not sell to customers")

    def record_return(self, r: NewReturn) -> None:
        raise NotSupported("a distributor does not take customer returns")

    def unit_view(self, gtin: str, serial: str) -> UnitView:
        ins = self.db.rows(
            "SELECT i.entry_id, i.supplier_org, i.dc_number, i.entry_date, il.lot, il.exp FROM inward_lines il "
            "JOIN inward i ON i.entry_id = il.entry_id WHERE il.sn = ? AND il.gtin = ?", serial, gtin,
        )  # fmt: skip
        outs = self.db.rows(
            "SELECT o.entry_id, o.customer_org, o.invoice_no, o.entry_date FROM outward_lines ol "
            "JOIN outward o ON o.entry_id = ol.entry_id WHERE ol.sn = ? AND ol.gtin = ?", serial, gtin,
        )  # fmt: skip
        if not ins and not outs:
            return view(gtin, serial, [], "never_held")
        events = [
            Event(event_id=f"dist-south:in:{e}:{serial}", org_id=self.ORG, event_type="receive", at=_midnight(day),
                  gtin=gtin, serial=serial, lot=lot, from_org=sup, ref=dc, city=self.city)
            for e, sup, dc, day, lot, _exp in ins
        ]  # fmt: skip
        events += [
            Event(event_id=f"dist-south:out:{e}:{serial}", org_id=self.ORG, event_type="ship", at=_midnight(day),
                  gtin=gtin, serial=serial, to_org=cust, ref=inv, city=self.city)
            for e, cust, inv, day in outs
        ]  # fmt: skip
        last_in = max(((day, 0, e) for e, _s, _d, day, _l, _x in ins), default=None)
        last_out = max(((day, 1, e) for e, _c, _i, day in outs), default=None)
        status = "shipped" if last_out and (last_in is None or last_out[:2] >= last_in[:2]) else "in_stock"
        lot = ins[-1][4] if ins else None
        exp = to_date(ins[-1][5]) if ins and ins[-1][5] else None
        return view(gtin, serial, events, status, lot, exp)

    def stock(self) -> list[StockLine]:
        rows = self.db.rows(
            "SELECT il.gtin, il.sn, il.lot, il.exp, i.entry_date FROM inward_lines il "
            f"JOIN inward i ON i.entry_id = il.entry_id WHERE {_IN_STOCK} ORDER BY il.sn"
        )
        return [
            StockLine(gtin=g, serial=s, lot=lot, expiry=to_date(e) if e else None, since=_midnight(day))
            for g, s, lot, e, day in rows
        ]

    def shipments_to(self, org_id: str, since: datetime | None = None) -> list[Shipment]:
        out = []
        for entry, inv, day in self.db.rows(
            "SELECT entry_id, invoice_no, entry_date FROM outward WHERE customer_org = ? ORDER BY entry_date, entry_id",
            org_id,
        ):
            at = _midnight(day)
            if since is not None and at < since:
                continue
            units = [
                UnitRef(gtin=g, serial=s, raw=raw)
                for g, s, raw in self.db.rows(
                    "SELECT gtin, sn, barcode_raw FROM outward_lines WHERE entry_id = ? ORDER BY sn", entry
                )
            ]
            out.append(Shipment(shipment_id=inv, from_org=self.ORG, to_org=org_id, at=at, units=units))
        return out
