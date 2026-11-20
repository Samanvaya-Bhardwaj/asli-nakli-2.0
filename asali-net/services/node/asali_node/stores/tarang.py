"""Tarang Pharma: PostgreSQL, normalised. See schemas/tarang/MAPPING.md."""

from datetime import datetime

from asali_node.canonical import (
    Batch,
    Event,
    NewBatch,
    NewProduct,
    NewShipment,
    Product,
    Shipment,
    StockLine,
    UnitRef,
    UnitView,
)  # fmt: skip
from asali_node.stores.sqlbase import new_id, to_ist
from asali_node.stores.sqlcommon import SqlStore, batch_from, chunks, in_clause, product_from, view

STATUS = {"commissioned": "in_stock", "shipped": "shipped", "destroyed": "destroyed"}


def _f(x: object) -> float | None:
    return None if x is None else float(x)  # type: ignore[arg-type]


class TarangStore(SqlStore):
    ENGINE = "pg"
    ORG = "tarang"
    CONTEXT_ROOTS = (("units", "serial", "serial"), ("shipment_units", "serial", "serial"))

    def add_product(self, p: NewProduct) -> Product:
        self.db.run(
            "INSERT INTO products (gtin, brand_name, generic_name, strength, dosage_form, pack_size, "
            "storage_min_c, storage_max_c, schedule) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            p.gtin, p.brand, p.generic, p.strength, p.form, p.pack_size, p.storage_min_c, p.storage_max_c, p.schedule,
        )  # fmt: skip
        return next(x for x in self.products() if x.gtin == p.gtin)

    def products(self) -> list[Product]:
        rows = self.db.rows(
            "SELECT gtin, brand_name, generic_name, strength, dosage_form, pack_size, storage_min_c, storage_max_c "
            "FROM products ORDER BY gtin"
        )
        return [
            product_from(g, b, n, s, f, int(p), _f(lo), _f(hi), self.ORG) for g, b, n, s, f, p, lo, hi in rows
        ]

    def create_batch(self, b: NewBatch) -> Batch:
        self.db.run(
            "INSERT INTO batches (lot, gtin, mfg_date, expiry_date, quantity, status) VALUES (?, ?, ?, ?, ?, 'released')",
            b.lot, b.gtin, b.mfg_date, b.expiry_date, b.quantity,
        )  # fmt: skip
        return next(x for x in self.batches(b.gtin) if x.lot == b.lot)

    def batches(self, gtin: str | None = None) -> list[Batch]:
        sql = "SELECT gtin, lot, mfg_date, expiry_date, status FROM batches"
        rows = self.db.rows(
            sql + (" WHERE gtin = ?" if gtin else "") + " ORDER BY lot", *([gtin] if gtin else [])
        )
        return [batch_from(g, lot, m, e, s, self.ORG) for g, lot, m, e, s in rows]

    def commission_units(self, gtin: str, lot: str, serials: list[str], at: datetime) -> int:
        with self.db.tx() as tx:
            if not tx.rows("SELECT 1 FROM batches WHERE lot = ? AND gtin = ?", lot, gtin):
                raise ValueError(f"lot {lot} does not belong to {gtin}")
            for s in serials:
                tx.run(
                    "INSERT INTO units (serial, gtin, lot, status, commissioned_at) VALUES (?, ?, ?, 'commissioned', ?)",
                    s, gtin, lot, at,
                )  # fmt: skip
        return len(serials)

    def record_shipment(self, s: NewShipment) -> Shipment:
        with self.db.tx() as tx:
            for u in s.units:
                st = tx.rows("SELECT status FROM units WHERE serial = ? AND gtin = ?", u.serial, u.gtin)
                if not st or st[0][0] != "commissioned":
                    raise ValueError(f"{u.serial} is not in stock to ship")
            tx.run(
                "INSERT INTO shipments (shipment_id, to_org_id, shipped_at, vehicle_no, created_by) "
                "VALUES (?, ?, ?, ?, ?)", s.shipment_id, s.to_org, s.at, s.vehicle_no, s.by,
            )  # fmt: skip
            for u in s.units:
                tx.run(
                    "INSERT INTO shipment_units (shipment_id, serial) VALUES (?, ?)", s.shipment_id, u.serial
                )
                tx.run("UPDATE units SET status = 'shipped' WHERE serial = ?", u.serial)
        return Shipment(shipment_id=s.shipment_id, from_org=self.ORG, to_org=s.to_org, at=to_ist(s.at),
                        units=self._units_of(s.shipment_id))  # fmt: skip

    def recall_batch(self, gtin: str, lot: str, reason: str, level: str, at: datetime) -> None:
        with self.db.tx() as tx:
            tx.run("INSERT INTO recalls (recall_id, lot, reason, level, issued_at) VALUES (?, ?, ?, ?, ?)",
                   new_id("RC"), lot, reason, level, at)  # fmt: skip
            tx.run("UPDATE batches SET status = 'recalled' WHERE lot = ? AND gtin = ?", lot, gtin)

    def unit_view(self, gtin: str, serial: str) -> UnitView:
        rows = self.db.rows(
            "SELECT u.status, u.commissioned_at, u.lot, b.expiry_date FROM units u JOIN batches b ON b.lot = u.lot "
            "WHERE u.serial = ? AND u.gtin = ?", serial, gtin,
        )  # fmt: skip
        if not rows:
            return view(gtin, serial, [], "never_held")
        status, at, lot, exp = rows[0]
        events = [Event(event_id=f"tarang:commission:{serial}", org_id=self.ORG, event_type="commission",
                        at=to_ist(at), gtin=gtin, serial=serial, lot=lot, city=self.city)]  # fmt: skip
        for sid, to_org, shipped_at in self.db.rows(
            "SELECT sh.shipment_id, sh.to_org_id, sh.shipped_at FROM shipment_units su "
            "JOIN shipments sh ON sh.shipment_id = su.shipment_id WHERE su.serial = ?", serial,
        ):  # fmt: skip
            events.append(Event(event_id=f"tarang:ship:{sid}:{serial}", org_id=self.ORG, event_type="ship",
                                at=to_ist(shipped_at), gtin=gtin, serial=serial, lot=lot, to_org=to_org, ref=sid,
                                city=self.city))  # fmt: skip
        if status not in STATUS:
            raise ValueError(f"unknown unit status {status!r}")
        return view(gtin, serial, events, STATUS[status], lot, exp)

    def existing_serials(self, gtin: str | None, serials: list[str]) -> set[str]:
        found: set[str] = set()
        for part in chunks(serials):
            sql = f"SELECT serial FROM units WHERE serial IN {in_clause(len(part))}"
            args: list[str] = list(part)
            if gtin:
                sql += " AND gtin = ?"
                args.append(gtin)
            found |= {r[0] for r in self.db.rows(sql, *args)}
        return found

    def _units_of(self, shipment_id: str) -> list[UnitRef]:
        rows = self.db.rows(
            "SELECT u.gtin, u.serial, u.lot, b.expiry_date FROM shipment_units su "
            "JOIN units u ON u.serial = su.serial JOIN batches b ON b.lot = u.lot "
            "WHERE su.shipment_id = ? ORDER BY u.serial", shipment_id,
        )  # fmt: skip
        return [UnitRef(gtin=g, serial=s, lot=lot, expiry=e) for g, s, lot, e in rows]

    def shipments_to(self, org_id: str, since: datetime | None = None) -> list[Shipment]:
        rows = self.db.rows(
            "SELECT shipment_id, shipped_at FROM shipments WHERE to_org_id = ? ORDER BY shipped_at", org_id
        )
        return [
            Shipment(shipment_id=i, from_org=self.ORG, to_org=org_id, at=to_ist(at), units=self._units_of(i))
            for i, at in rows
            if since is None or to_ist(at) >= since
        ]

    def stock(self) -> list[StockLine]:
        rows = self.db.rows(
            "SELECT u.gtin, u.serial, u.lot, b.expiry_date, u.commissioned_at FROM units u "
            "JOIN batches b ON b.lot = u.lot WHERE u.status = 'commissioned' ORDER BY u.serial"
        )
        return [StockLine(gtin=g, serial=s, lot=lot, expiry=e, since=to_ist(t)) for g, s, lot, e, t in rows]
