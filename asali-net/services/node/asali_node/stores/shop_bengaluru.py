"""Namma Pharmacy, Bengaluru: MongoDB, one document per pack. See schemas/shop-bengaluru/MAPPING.md."""

from datetime import datetime

from pymongo.errors import DuplicateKeyError

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
from asali_node.stores.mongobase import MongoStore, unknown_unit, view
from asali_node.stores.protocols import NotSupported
from asali_node.stores.sqlbase import to_ist


def _key(gtin: str, serial: str) -> str:
    return f"{gtin}/{serial}"


class ShopBengaluruStore(MongoStore):
    ORG = "shop-bengaluru"

    def record_receipt(self, r: NewReceipt) -> None:
        for u in r.units:
            try:
                self.db["stock"].insert_one(
                    {"_id": _key(u.gtin, u.serial), "in": {"from": r.from_org, "at": r.at, "ref": r.source_ref},
                     "sale": None, "ret": None}
                )  # fmt: skip
            except DuplicateKeyError as e:
                raise ValueError(f"{u.serial} was already received") from e

    def received_refs(self) -> set[tuple[str, str]]:
        return {(d["in"]["from"], d["in"]["ref"]) for d in self.db["stock"].find({}, {"in": 1})}

    def record_dispatch(self, d: NewDispatch) -> Shipment:
        raise NotSupported("a shop does not dispatch to other organisations")

    def record_sale(self, s: NewSale) -> None:
        for line in s.lines:
            doc = self.db["stock"].find_one({"_id": _key(line.gtin, line.serial)})
            if doc is None or doc["sale"] is not None or doc["ret"] is not None:
                raise ValueError(f"{line.serial} is not in stock")
        for line in s.lines:
            res = self.db["stock"].update_one(
                {"_id": _key(line.gtin, line.serial), "sale": None, "ret": None},
                {"$set": {"sale": {"bill": s.bill_no, "at": s.at}}},
            )
            if res.matched_count != 1:
                raise ValueError(f"{line.serial} was sold at the same moment")
        self.db["bills"].insert_one(
            {"_id": s.bill_no, "at": s.at, "lines": [_key(x.gtin, x.serial) for x in s.lines],
             "amountPaise": sum(x.mrp_paise for x in s.lines), "customerRef": s.customer_ref_hash}
        )  # fmt: skip

    def record_return(self, r: NewReturn) -> None:
        res = self.db["stock"].update_one(
            {"_id": _key(r.gtin, r.serial), "sale.bill": r.bill_no, "ret": None},
            {"$set": {"ret": {"at": r.at, "why": r.reason}}},
        )
        if res.matched_count != 1:
            raise ValueError(f"{r.serial} was not sold on bill {r.bill_no}")

    def unit_view(self, gtin: str, serial: str) -> UnitView:
        d = self.db["stock"].find_one({"_id": _key(gtin, serial)})
        if d is None:
            return unknown_unit(gtin, serial)
        events = [Event(event_id=f"shop-bengaluru:in:{serial}", org_id=self.ORG, event_type="receive",
                        at=to_ist(d["in"]["at"]), gtin=gtin, serial=serial, from_org=d["in"]["from"],
                        ref=d["in"]["ref"], city=self.city)]  # fmt: skip
        if d["sale"]:
            events.append(Event(event_id=f"shop-bengaluru:sale:{serial}", org_id=self.ORG, event_type="sell",
                                at=to_ist(d["sale"]["at"]), gtin=gtin, serial=serial, ref=d["sale"]["bill"],
                                city=self.city))  # fmt: skip
        if d["ret"]:
            events.append(Event(event_id=f"shop-bengaluru:ret:{serial}", org_id=self.ORG, event_type="return",
                                at=to_ist(d["ret"]["at"]), gtin=gtin, serial=serial, ref=d["sale"]["bill"],
                                city=self.city))  # fmt: skip
        status = "returned" if d["ret"] else "sold" if d["sale"] else "in_stock"
        return view(gtin, serial, events, status)

    def stock(self) -> list[StockLine]:
        out = []
        for d in self.db["stock"].find({"sale": None, "ret": None}).sort("_id", 1):
            gtin, serial = d["_id"].split("/")
            out.append(
                StockLine(gtin=gtin, serial=serial, lot=None, expiry=None, since=to_ist(d["in"]["at"]))
            )
        return sorted(out, key=lambda x: x.serial)

    def shipments_to(self, org_id: str, since: datetime | None = None) -> list[Shipment]:
        return []

    def sold(self) -> list[UnitRef]:
        out = []
        for d in self.db["stock"].find({"sale": {"$ne": None}, "ret": None}).sort("_id", 1):
            gtin, serial = d["_id"].split("/")
            out.append(UnitRef(gtin=gtin, serial=serial))
        return out
