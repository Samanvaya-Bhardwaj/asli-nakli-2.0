"""Medivra Labs: MongoDB, lots with embedded units, consignments. See schemas/medivra/MAPPING.md."""

import re
from datetime import datetime
from typing import Any

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
from asali_node.stores.mongobase import MongoStore, d2dt, dt2d, unknown_unit, view
from asali_node.stores.sqlbase import to_ist
from asali_node.stores.sqlcommon import batch_from, party_kind, product_from

STATE = {"C": "in_stock", "S": "shipped", "D": "destroyed"}


def _split_strength(s: str) -> dict[str, Any]:
    m = re.fullmatch(r"([\d.]+)\s*(.+)", s)
    if not m:
        raise ValueError(f"cannot read strength {s!r}")
    v = float(m[1])
    return {"v": int(v) if v == int(v) else v, "u": m[2]}


def _join_strength(d: dict[str, Any]) -> str:
    return f"{d['v']} {d['u']}"


class MedivraStore(MongoStore):
    ORG = "medivra"
    CONTEXT_COLLECTIONS = ("skus", "lots", "consignments", "consignmentLines", "parties", "recalls")
    CONTEXT_REFS = (
        ("lots", "sku", "skus", "_id"), ("consignments", "consignee", "parties", "_id"),
        ("consignmentLines", "consignment", "consignments", "_id"), ("consignmentLines", "lot", "lots", "_id"),
        ("recalls", "lot", "lots", "_id"),
    )  # fmt: skip
    CONTEXT_ROOTS = (("lots", "units.sn", "serial"),)

    def add_product(self, p: NewProduct) -> Product:
        self.db["skus"].insert_one(
            {"_id": p.gtin, "brand": p.brand, "molecule": p.generic, "strength": _split_strength(p.strength),
             "form": p.form, "packOf": p.pack_size, "schedule": p.schedule,
             "storage": {"minC": p.storage_min_c, "maxC": p.storage_max_c}}
        )  # fmt: skip
        return next(x for x in self.products() if x.gtin == p.gtin)

    def products(self) -> list[Product]:
        return [
            product_from(d["_id"], d["brand"], d["molecule"], _join_strength(d["strength"]), d["form"], d["packOf"],
                         d["storage"]["minC"], d["storage"]["maxC"], self.ORG)
            for d in self.db["skus"].find().sort("_id", 1)
        ]  # fmt: skip

    def create_batch(self, b: NewBatch) -> Batch:
        if self.db["skus"].find_one({"_id": b.gtin}) is None:
            raise ValueError(f"unknown product {b.gtin}")
        self.db["lots"].insert_one(
            {"_id": b.lot, "sku": b.gtin, "made": d2dt(b.mfg_date), "expires": d2dt(b.expiry_date),
             "qty": b.quantity, "recall": None, "units": []}
        )  # fmt: skip
        return next(x for x in self.batches(b.gtin) if x.lot == b.lot)

    def batches(self, gtin: str | None = None) -> list[Batch]:
        q = {"sku": gtin} if gtin else {}
        return [
            batch_from(d["sku"], d["_id"], dt2d(d["made"]), dt2d(d["expires"]),
                       "recalled" if d.get("recall") else "released", self.ORG)
            for d in self.db["lots"].find(q, {"units": 0}).sort("_id", 1)
        ]  # fmt: skip

    def commission_units(self, gtin: str, lot: str, serials: list[str], at: datetime) -> int:
        if self.db["lots"].find_one({"_id": lot, "sku": gtin}, {"_id": 1}) is None:
            raise ValueError(f"lot {lot} does not belong to {gtin}")
        if self.existing_serials(None, serials):
            raise ValueError("some serials already exist")
        self.db["lots"].update_one(
            {"_id": lot, "sku": gtin},
            {
                "$push": {
                    "units": {"$each": [{"sn": s, "state": "C", "out": None, "at": at} for s in serials]}
                }
            },
        )
        return len(serials)

    def record_shipment(self, s: NewShipment) -> Shipment:
        by_lot: dict[str, tuple[str, list[str]]] = {}
        for u in s.units:
            doc = self.db["lots"].find_one(
                {"sku": u.gtin, "units": {"$elemMatch": {"sn": u.serial, "state": "C"}}}, {"_id": 1}
            )
            if doc is None:
                raise ValueError(f"{u.serial} is not in stock to ship")
            by_lot.setdefault(doc["_id"], (u.gtin, []))[1].append(u.serial)
        out = {"consignment": s.shipment_id, "to": s.to_org, "at": s.at}
        self._ensure("parties", s.to_org, {"orgType": party_kind(s.to_org)})
        self.db["consignmentLines"].insert_many(
            [{"_id": f"{s.shipment_id}/{lot}", "consignment": s.shipment_id, "lot": lot, "sku": sku, "count": len(sns)}
             for lot, (sku, sns) in by_lot.items()]
        )  # fmt: skip
        self.db["consignments"].insert_one(
            {"_id": s.shipment_id, "consignee": s.to_org, "dispatchedAt": s.at, "by": s.by, "vehicle": s.vehicle_no,
             "lines": [{"sku": sku, "lot": lot, "sns": sns} for lot, (sku, sns) in by_lot.items()]}
        )  # fmt: skip
        for lot, (_sku, sns) in by_lot.items():
            self.db["lots"].update_one(
                {"_id": lot},
                {"$set": {"units.$[u].state": "S", "units.$[u].out": out}},
                array_filters=[{"u.sn": {"$in": sns}}],
            )
        return next(x for x in self.shipments_to(s.to_org) if x.shipment_id == s.shipment_id)

    def recall_batch(self, gtin: str, lot: str, reason: str, level: str, at: datetime) -> None:
        self.db["lots"].update_one(
            {"_id": lot, "sku": gtin}, {"$set": {"recall": {"reason": reason, "at": at, "level": level}}}
        )
        self.db["recalls"].update_one(
            {"_id": lot}, {"$set": {"lot": lot, "reason": reason, "level": level, "at": at}}, upsert=True
        )

    def unit_view(self, gtin: str, serial: str) -> UnitView:
        d = self.db["lots"].find_one({"sku": gtin, "units.sn": serial}, {"units.$": 1, "expires": 1})
        if d is None:
            return unknown_unit(gtin, serial)
        u, lot = d["units"][0], d["_id"]
        events = [Event(event_id=f"medivra:C:{serial}", org_id=self.ORG, event_type="commission", at=to_ist(u["at"]),
                        gtin=gtin, serial=serial, lot=lot, city=self.city)]  # fmt: skip
        if u.get("out"):
            o = u["out"]
            events.append(Event(event_id=f"medivra:S:{o['consignment']}:{serial}", org_id=self.ORG,
                                event_type="ship", at=to_ist(o["at"]), gtin=gtin, serial=serial, lot=lot,
                                to_org=o["to"], ref=o["consignment"], city=self.city))  # fmt: skip
        if u["state"] not in STATE:
            raise ValueError(f"unknown unit state {u['state']!r}")
        return view(gtin, serial, events, STATE[u["state"]], lot, dt2d(d["expires"]))

    def existing_serials(self, gtin: str | None, serials: list[str]) -> set[str]:
        q: dict[str, Any] = {"units.sn": {"$in": serials}}
        if gtin:
            q["sku"] = gtin
        wanted = set(serials)
        return {
            u["sn"] for d in self.db["lots"].find(q, {"units.sn": 1}) for u in d["units"] if u["sn"] in wanted
        }

    def shipments_to(self, org_id: str, since: datetime | None = None) -> list[Shipment]:
        out = []
        for c in self.db["consignments"].find({"consignee": org_id}).sort("dispatchedAt", 1):
            at = to_ist(c["dispatchedAt"])
            if since is not None and at < since:
                continue
            units: list[UnitRef] = []
            for line in c["lines"]:
                exp = self.db["lots"].find_one({"_id": line["lot"]}, {"expires": 1})
                units += [UnitRef(gtin=line["sku"], serial=sn, lot=line["lot"], expiry=dt2d(exp["expires"]))
                          for sn in line["sns"]]  # fmt: skip
            out.append(Shipment(shipment_id=c["_id"], from_org=self.ORG, to_org=org_id, at=at,
                                units=sorted(units, key=lambda x: x.serial)))  # fmt: skip
        return out

    def stock(self) -> list[StockLine]:
        out = []
        for d in self.db["lots"].find({"units.state": "C"}):
            out += [StockLine(gtin=d["sku"], serial=u["sn"], lot=d["_id"], expiry=dt2d(d["expires"]),
                              since=to_ist(u["at"])) for u in d["units"] if u["state"] == "C"]  # fmt: skip
        return sorted(out, key=lambda x: x.serial)
