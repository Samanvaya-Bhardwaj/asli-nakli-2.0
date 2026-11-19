"""Western Medilink: MongoDB, one event-sourced movements collection. See schemas/dist-west/MAPPING.md."""

from datetime import datetime
from typing import Any

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


class DistWestStore(MongoStore):
    ORG = "dist-west"

    def _ordered(self, query: dict[str, Any]) -> Any:
        return self.db["movements"].find(query).sort([("at", 1), ("_id", 1)])

    def record_receipt(self, r: NewReceipt) -> None:
        self.db["movements"].insert_one(
            {"dir": "IN", "party": r.from_org, "at": r.at, "ref": r.source_ref, "by": r.by,
             "items": [{"g": u.gtin, "s": u.serial} for u in r.units]}
        )  # fmt: skip

    def received_refs(self) -> set[tuple[str, str]]:
        return {
            (m["party"], m["ref"]) for m in self.db["movements"].find({"dir": "IN"}, {"party": 1, "ref": 1})
        }

    def _last_dir(self, serials: list[str]) -> dict[str, str]:
        last: dict[str, str] = {}
        for m in self._ordered({"items.s": {"$in": serials}}):
            for it in m["items"]:
                if it["s"] in last or it["s"] in serials:
                    last[it["s"]] = m["dir"]
        return last

    def record_dispatch(self, d: NewDispatch) -> Shipment:
        serials = [u.serial for u in d.units]
        last = self._last_dir(serials)
        missing = [s for s in serials if last.get(s) != "IN"]
        if missing:
            raise ValueError(f"not in stock: {missing[:3]}")
        self.db["movements"].insert_one(
            {"dir": "OUT", "party": d.to_org, "at": d.at, "ref": d.shipment_id, "by": d.by, "vehicle": d.vehicle_no,
             "items": [{"g": u.gtin, "s": u.serial} for u in d.units]}
        )  # fmt: skip
        return Shipment(shipment_id=d.shipment_id, from_org=self.ORG, to_org=d.to_org, at=to_ist(d.at),
                        units=[UnitRef(gtin=u.gtin, serial=u.serial) for u in d.units])  # fmt: skip

    def record_sale(self, s: NewSale) -> None:
        raise NotSupported("a distributor does not sell to customers")

    def record_return(self, r: NewReturn) -> None:
        raise NotSupported("a distributor does not take customer returns")

    def unit_view(self, gtin: str, serial: str) -> UnitView:
        moves = list(self._ordered({"items": {"$elemMatch": {"g": gtin, "s": serial}}}))
        if not moves:
            return unknown_unit(gtin, serial)
        events = [
            Event(event_id=f"dist-west:{m['_id']}:{serial}", org_id=self.ORG,
                  event_type="receive" if m["dir"] == "IN" else "ship", at=to_ist(m["at"]), gtin=gtin, serial=serial,
                  from_org=m["party"] if m["dir"] == "IN" else None, to_org=m["party"] if m["dir"] == "OUT" else None,
                  ref=m["ref"], city=self.city)
            for m in moves
        ]  # fmt: skip
        return view(gtin, serial, events, "in_stock" if moves[-1]["dir"] == "IN" else "shipped")

    def stock(self) -> list[StockLine]:
        held: dict[tuple[str, str], datetime | None] = {}
        for m in self._ordered({}):
            for it in m["items"]:
                held[(it["g"], it["s"])] = to_ist(m["at"]) if m["dir"] == "IN" else None
        return sorted(
            (
                StockLine(gtin=g, serial=s, lot=None, expiry=None, since=at)
                for (g, s), at in held.items()
                if at
            ),
            key=lambda x: x.serial,
        )

    def shipments_to(self, org_id: str, since: datetime | None = None) -> list[Shipment]:
        out = []
        for m in self._ordered({"dir": "OUT", "party": org_id}):
            at = to_ist(m["at"])
            if since is None or at >= since:
                units = [UnitRef(gtin=i["g"], serial=i["s"]) for i in m["items"]]
                out.append(
                    Shipment(shipment_id=m["ref"], from_org=self.ORG, to_org=org_id, at=at, units=units)
                )
        return out

    def sold(self) -> list[UnitRef]:
        raise NotSupported("a distributor does not sell to customers")
