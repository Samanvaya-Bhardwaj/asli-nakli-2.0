"""Build the structured records a document could be linked to, from what this node can read right now."""

import asyncio
import time
from datetime import date
from typing import Any

from asali_codes.candidates import serial_candidates
from asali_text.gazetteer import Gazetteer, ProductName
from asali_text.mentions import by_kind, extract
from asali_text.world import BatchInfo, OrgInfo, ProductInfo, ShipmentInfo, UnitInfo, World

from asali_node.network.client import SourceUnavailable
from asali_node.verify.trace import Tracer

CACHE_S = 60.0
MAX_UNITS_PER_DOC = 6


class WorldBuilder:
    def __init__(self, state: Any, store: Any, org_id: str, org_type: str) -> None:
        self.state, self.store = state, store
        self.org_id, self.org_type = org_id, org_type
        self._catalogue: tuple[float, list[ProductInfo], list[BatchInfo]] | None = None

    @property
    def share(self) -> Any:
        return self.state.share  # set when the node starts its network side

    @property
    def directory(self) -> Any:
        return self.state.directory

    def orgs(self) -> dict[str, dict[str, Any]]:
        return {o["org_id"]: o for o in self.directory.known()}

    async def _catalogue_now(self) -> tuple[list[ProductInfo], list[BatchInfo]]:
        if self._catalogue and time.monotonic() - self._catalogue[0] < CACHE_S:
            return self._catalogue[1], self._catalogue[2]
        pharmas = [o["org_id"] for o in self.orgs().values() if o["org_type"] == "pharma"]
        answers = await asyncio.gather(*[self._both(p) for p in pharmas])
        products = [
            ProductInfo(x["gtin"], x["brand"], x["generic"], x["strength"], p)
            for p, (pr, _) in zip(pharmas, answers, strict=True)
            for x in pr
        ]
        batches = [
            BatchInfo(
                x["gtin"],
                x["lot"],
                p,
                date.fromisoformat(x["mfg_date"]),
                date.fromisoformat(x["expiry_date"]),
                x["status"],
            )
            for p, (_, bt) in zip(pharmas, answers, strict=True)
            for x in bt
        ]
        self._catalogue = (time.monotonic(), products, batches)
        return products, batches

    async def _both(self, org: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        try:
            pr = await self.share.get(org, "/share/v1/products")
            bt = await self.share.get(org, "/share/v1/batches")
            return pr["products"], bt["batches"]
        except SourceUnavailable:
            return [], []

    async def build(self, text: str) -> tuple[World, Gazetteer]:
        orgs = self.orgs()
        products, batches = await self._catalogue_now()
        w = World(products=products, batches=batches,
                  orgs={k: OrgInfo(k, o["name"], o["org_type"], o["city"]) for k, o in orgs.items()})  # fmt: skip
        issuers = tuple(sorted({o["issuer_code"] for o in orgs.values() if o.get("issuer_code")}))
        gaz = Gazetteer(tuple(ProductName(p.gtin, p.brand, p.generic, p.strength) for p in products),
                        {k: o["name"] for k, o in orgs.items() if o["org_type"] != "consumer"}, issuers or ("TP", "MV", "KS"))  # fmt: skip
        mentions = extract(text, gaz)
        for m in by_kind(mentions, "serial")[:MAX_UNITS_PER_DOC]:
            for serial in await self._existing(m.value or "", orgs, issuers):
                unit = await self._unit(serial, orgs, w)
                if unit:
                    w.units[serial] = unit
        w.shipments = await self._shipments(orgs, w)
        return w, gaz

    async def _existing(
        self, seen: str, orgs: dict[str, dict[str, Any]], issuers: tuple[str, ...]
    ) -> set[str]:
        cands = {seen} | {c.value for c in serial_candidates(seen, issuers)} if len(seen) == 11 else set()
        found: set[str] = set()
        for o in orgs.values():
            code = o.get("issuer_code")
            mine = sorted(c for c in cands if code and c.startswith(code))
            if not mine:
                continue
            try:
                found |= set(
                    (
                        await self.share.get(
                            o["org_id"], "/share/v1/units/exists", {"serials": ",".join(mine)}
                        )
                    )["existing"]
                )
            except SourceUnavailable:
                continue
        return found

    async def _unit(self, serial: str, orgs: dict[str, dict[str, Any]], w: World) -> UnitInfo | None:
        maker = next((k for k, o in orgs.items() if o.get("issuer_code") == serial[:2]), None)
        if maker is None:
            return None
        try:
            gtin = (await self.share.get(maker, f"/share/v1/units/by-serial/{serial}"))["gtin"]
        except SourceUnavailable:
            return None
        hops = await Tracer(self.share, list(orgs.values())).chain(maker, gtin, serial)
        events = [e for h in hops if h.view for e in h.view.events]
        if not events:
            return None
        days = sorted(e.at.date() for e in events)
        lot = hops[0].view.lot if hops[0].view else ""
        return UnitInfo(
            gtin,
            serial,
            lot or "",
            maker,
            tuple(h.org_id for h in hops),
            tuple(h.city for h in hops),
            days[0],
            days[-1],
        )

    async def _shipments(self, orgs: dict[str, dict[str, Any]], w: World) -> list[ShipmentInfo]:
        out: list[ShipmentInfo] = []
        city = lambda o: orgs.get(o, {}).get("city", "")  # noqa: E731
        if hasattr(self.store, "shipments_to") and self.org_type in ("pharma", "distributor"):
            for target in orgs:
                if target == self.org_id:
                    continue
                for s in self.store.shipments_to(target):
                    out.append(
                        ShipmentInfo(
                            self.org_id,
                            s.shipment_id,
                            target,
                            s.at.date(),
                            tuple(sorted({u.gtin for u in s.units})),
                            (city(self.org_id), city(target)),
                        )
                    )
        upstream = {"distributor": "pharma", "shop": "distributor"}.get(self.org_type)
        for o in [o for o in orgs.values() if o["org_type"] == upstream]:
            try:
                reply = await self.share.get(o["org_id"], "/share/v1/shipments")
            except SourceUnavailable:
                continue
            for s in reply["shipments"]:
                out.append(
                    ShipmentInfo(
                        o["org_id"],
                        s["shipment_id"],
                        self.org_id,
                        date.fromisoformat(s["at"][:10]),
                        tuple(sorted({u["gtin"] for u in s["units"]})),
                        (city(o["org_id"]), city(self.org_id)),
                    )
                )
        return out
