"""North Star Distributors: PostgreSQL, receipts and dispatches. See schemas/dist-north/MAPPING.md."""

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
from asali_node.stores.sqlbase import new_id, to_ist
from asali_node.stores.sqlcommon import SqlStore, chunks, in_clause, party_kind, view


class DistNorthStore(SqlStore):
    ENGINE = "pg"
    ORG = "dist-north"
    CONTEXT_ROOTS = (("receipt_items", "serial", "serial"), ("dispatch_items", "serial", "serial"))

    def record_receipt(self, r: NewReceipt) -> None:
        rid = new_id("RCP")
        with self.db.tx() as tx:
            tx.run(
                "INSERT INTO parties (org_id, org_type) VALUES (?, ?) ON CONFLICT (org_id) DO NOTHING",
                r.from_org,
                party_kind(r.from_org),
            )
            tx.run(
                "INSERT INTO receipts (receipt_id, from_org_id, source_ref, received_at, received_by) "
                "VALUES (?, ?, ?, ?, ?)", rid, r.from_org, r.source_ref, r.at, r.by,
            )  # fmt: skip
            for u in r.units:
                tx.run(
                    "INSERT INTO receipt_items (receipt_id, gtin, serial) VALUES (?, ?, ?)",
                    rid,
                    u.gtin,
                    u.serial,
                )

    def received_refs(self) -> set[tuple[str, str]]:
        return {(a, b) for a, b in self.db.rows("SELECT from_org_id, source_ref FROM receipts")}

    def record_dispatch(self, d: NewDispatch) -> Shipment:
        serials = [u.serial for u in d.units]
        with self.db.tx() as tx:
            have: set[str] = set()
            for part in chunks(serials):
                have |= {
                    r[0]
                    for r in tx.rows(
                        f"SELECT serial FROM stock_now WHERE serial IN {in_clause(len(part))}", *part
                    )
                }
            if set(serials) - have:
                raise ValueError(f"not in stock: {sorted(set(serials) - have)[:3]}")
            tx.run(
                "INSERT INTO parties (org_id, org_type) VALUES (?, ?) ON CONFLICT (org_id) DO NOTHING",
                d.to_org,
                party_kind(d.to_org),
            )
            tx.run("INSERT INTO dispatches (dispatch_id, to_org_id, dispatched_at, vehicle_no) VALUES (?, ?, ?, ?)",
                   d.shipment_id, d.to_org, d.at, d.vehicle_no)  # fmt: skip
            for u in d.units:
                tx.run("INSERT INTO dispatch_items (dispatch_id, gtin, serial) VALUES (?, ?, ?)",
                       d.shipment_id, u.gtin, u.serial)  # fmt: skip
        return Shipment(shipment_id=d.shipment_id, from_org=self.ORG, to_org=d.to_org, at=to_ist(d.at),
                        units=[UnitRef(gtin=u.gtin, serial=u.serial) for u in d.units])  # fmt: skip

    def record_sale(self, s: NewSale) -> None:
        raise NotSupported("a distributor does not sell to customers")

    def record_return(self, r: NewReturn) -> None:
        raise NotSupported("a distributor does not take customer returns")

    def unit_view(self, gtin: str, serial: str) -> UnitView:
        ins = self.db.rows(
            "SELECT r.receipt_id, r.from_org_id, r.source_ref, r.received_at FROM receipt_items ri "
            "JOIN receipts r ON r.receipt_id = ri.receipt_id WHERE ri.serial = ? AND ri.gtin = ?", serial, gtin,
        )  # fmt: skip
        outs = self.db.rows(
            "SELECT d.dispatch_id, d.to_org_id, d.dispatched_at FROM dispatch_items di "
            "JOIN dispatches d ON d.dispatch_id = di.dispatch_id WHERE di.serial = ? AND di.gtin = ?", serial, gtin,
        )  # fmt: skip
        if not ins and not outs:
            return view(gtin, serial, [], "never_held")
        events = [
            Event(event_id=f"dist-north:{rid}:{serial}", org_id=self.ORG, event_type="receive", at=to_ist(at),
                  gtin=gtin, serial=serial, from_org=org, ref=ref, city=self.city)
            for rid, org, ref, at in ins
        ]  # fmt: skip
        events += [
            Event(event_id=f"dist-north:{did}:{serial}", org_id=self.ORG, event_type="ship", at=to_ist(at),
                  gtin=gtin, serial=serial, to_org=to, ref=did, city=self.city)
            for did, to, at in outs
        ]  # fmt: skip
        last_in = max((to_ist(a) for *_, a in ins), default=None)
        last_out = max((to_ist(a) for *_, a in outs), default=None)
        shipped = last_out is not None and (last_in is None or last_out >= last_in)
        return view(gtin, serial, events, "shipped" if shipped else "in_stock")

    def stock(self) -> list[StockLine]:
        rows = self.db.rows("SELECT gtin, serial, since FROM stock_now ORDER BY serial")
        return [StockLine(gtin=g, serial=s, lot=None, expiry=None, since=to_ist(t)) for g, s, t in rows]

    def shipments_to(self, org_id: str, since: datetime | None = None) -> list[Shipment]:
        out = []
        for did, at in self.db.rows(
            "SELECT dispatch_id, dispatched_at FROM dispatches WHERE to_org_id = ? ORDER BY dispatched_at",
            org_id,
        ):
            if since is not None and to_ist(at) < since:
                continue
            units = [UnitRef(gtin=g, serial=s) for g, s in self.db.rows(
                "SELECT gtin, serial FROM dispatch_items WHERE dispatch_id = ? ORDER BY serial", did)]  # fmt: skip
            out.append(
                Shipment(shipment_id=did, from_org=self.ORG, to_org=org_id, at=to_ist(at), units=units)
            )
        return out

    def sold(self) -> list[UnitRef]:
        raise NotSupported("a distributor does not sell to customers")
