"""Follow a pack along its custody chain (PLAN.md 12.1): a dependent join, each hop asks where the last one sent it.

The side queries (alerts, shops, consumer nodes) do not depend on the chain and run alongside it.
Every call is timed and recorded, so the result can say who answered, who did not, and from which computer.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from asali_node.canonical import Alert, Event, Licence, Product, ScanStat, UnitView
from asali_node.network.client import SourceUnavailable
from asali_node.verify.models import Facts, Hop

MAX_HOPS = 6


@dataclass
class Trace:
    facts: Facts
    sources: list[dict[str, Any]] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    lot: str | None = None


class Tracer:
    def __init__(self, share: Any, orgs: list[dict[str, Any]], budget_s: float = 6.0) -> None:
        self.share, self.orgs, self.budget_s = share, orgs, budget_s
        self.by_id = {o["org_id"]: o for o in orgs}
        self.sources: dict[str, dict[str, Any]] = {}

    def of_type(self, kind: str) -> list[str]:
        return [o["org_id"] for o in self.orgs if o["org_type"] == kind]

    async def ask(self, org: str, path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | SourceUnavailable:
        started = time.monotonic()
        try:
            body: dict[str, Any] | SourceUnavailable = await self.share.get(org, path, params)
            status = "answered"
        except SourceUnavailable as e:
            body, status = e, "unreachable" if e.reason != "skipped" else "skipped"
        host = (body.get("served_by") or {}).get("host_name") if isinstance(body, dict) else None
        host = host or self.by_id.get(org, {}).get("host_name")
        self.sources[org] = {"org_id": org, "status": status, "ms": round((time.monotonic() - started) * 1000),
                             "host_name": host, "reason": body.reason if isinstance(body, SourceUnavailable) else ""}  # fmt: skip
        return body

    async def chain(self, issuer: str, gtin: str, serial: str) -> list[Hop]:
        path, hops, seen, org = f"/share/v1/units/{gtin}/{serial}", [], {issuer}, issuer
        while len(hops) < MAX_HOPS:
            body = await self.ask(org, path)
            info = self.by_id[org]
            if isinstance(body, SourceUnavailable):
                hops.append(Hop(org, info["org_type"], info["name"], info["city"], None, body.reason))
                break
            view = UnitView.model_validate(body)
            hops.append(Hop(org, info["org_type"], info["name"], info["city"], view))
            ships = [e for e in view.events if e.event_type == "ship" and e.to_org]
            nxt = ships[-1].to_org if ships else None
            if not nxt or nxt in seen or nxt not in self.by_id:
                break
            seen.add(nxt)
            org = nxt
        return hops

    async def run(self, gtin: str, serial: str, today: date, with_alerts_for: str | None = None) -> Trace:
        issuer = next((o for o in self.orgs if o["org_type"] == "pharma" and o.get("issuer_code") == serial[:2]), None)
        if issuer is None:
            return Trace(Facts(gtin, serial, issuer_known=False, issuer_reachable=False, today=today))
        regs, shops, consumers = self.of_type("regulator"), self.of_type("shop"), self.of_type("consumer")
        side = {
            "alerts": [self.ask(r, "/share/v1/alerts", {"gtin": gtin}) for r in regs],
            "shops": [self.ask(s, f"/share/v1/units/{gtin}/{serial}") for s in shops],
            "scans": [self.ask(c, f"/share/v1/scans/{gtin}/{serial}") for c in consumers],
        }
        chain_task = asyncio.create_task(self.chain(issuer["org_id"], gtin, serial))
        side_tasks = {k: [asyncio.create_task(c) for c in v] for k, v in side.items()}
        pending = [chain_task, *(t for ts in side_tasks.values() for t in ts)]
        await asyncio.wait(pending, timeout=self.budget_s)
        for t in pending:
            if not t.done():
                t.cancel()
        chain = chain_task.result() if chain_task.done() and not chain_task.cancelled() else []
        late = [] if chain else [issuer["org_id"]]
        return await self._assemble(gtin, serial, today, issuer, chain, side_tasks, regs, late)

    async def _assemble(self, gtin: str, serial: str, today: date, issuer: dict[str, Any], chain: list[Hop],
                        side: dict[str, list[asyncio.Task[Any]]], regs: list[str], late: list[str]) -> Trace:  # fmt: skip
        def done(task: asyncio.Task[Any]) -> Any:
            return task.result() if task.done() and not task.cancelled() and task.exception() is None else None

        def answered(tasks: list[asyncio.Task[Any]]) -> list[dict[str, Any]]:
            return [r for r in map(done, tasks) if isinstance(r, dict)]

        missing = list(late)
        for key in ("alerts", "shops"):  # their answers feed do-not-use checks, so a missing one blocks a verdict
            missing += [org for org, t in zip(regs if key == "alerts" else self.of_type("shop"), side[key], strict=True)
                        if not isinstance(done(t), dict)]  # fmt: skip
        alerts = [Alert.model_validate(a) for r in answered(side["alerts"]) for a in r["alerts"]]
        stats = [ScanStat.model_validate(r) for r in answered(side["scans"])]
        on_chain = {h.org_id for h in chain}
        sells: list[Event] = []
        receives: list[Event] = []
        for r in answered(side["shops"]):
            view = UnitView.model_validate(r)
            if view.served_by and view.served_by.org_id not in on_chain:
                sells += [e for e in view.events if e.event_type == "sell"]
                receives += [e for e in view.events if e.event_type == "receive"]
        product, batch_status, lot, expiry = await self._catalogue(issuer, gtin, chain)
        licences = await self._licences(regs, chain)
        facts = Facts(
            gtin=gtin, serial=serial, issuer_known=True, issuer_reachable=bool(chain and chain[0].view is not None),
            today=today, product=product, batch_status=batch_status, expiry=expiry, lot=lot, chain=tuple(chain),
            other_sells=tuple(sells), other_receives=tuple(receives), alerts=tuple(alerts), licences=tuple(licences),
            scan_stats=tuple(stats), missing=tuple(missing), names={o["org_id"]: o["name"] for o in self.orgs},
        )  # fmt: skip
        history = [{"org_id": h.org_id, "org_name": h.name, "city": h.city, "unavailable": h.unavailable,
                    "events": [e.model_dump(mode="json") for e in (h.view.events if h.view else [])],
                    "served_by": h.view.served_by.model_dump(mode="json") if h.view and h.view.served_by else None}
                   for h in chain]  # fmt: skip
        return Trace(facts, sorted(self.sources.values(), key=lambda s: s["org_id"]), history, lot)

    async def _catalogue(self, issuer: dict[str, Any], gtin: str, chain: list[Hop]) -> tuple[Product | None, str | None, str | None, date | None]:
        view = chain[0].view if chain else None
        if view is None or not view.known:
            return None, None, None, None
        org = issuer["org_id"]
        prods, batches = await asyncio.gather(self.ask(org, "/share/v1/products"), self.ask(org, "/share/v1/batches", {"gtin": gtin}))
        product = next((Product.model_validate(p) for p in prods["products"] if p["gtin"] == gtin), None) if isinstance(prods, dict) else None
        status = next((b["status"] for b in batches["batches"] if b["lot"] == view.lot), None) if isinstance(batches, dict) else None
        return product, status, view.lot, view.expiry

    async def _licences(self, regs: list[str], chain: list[Hop]) -> list[Licence]:
        ids = ",".join(h.org_id for h in chain if h.org_type in ("distributor", "shop"))
        if not regs or not ids:
            return []
        body = await self.ask(regs[0], "/share/v1/licences", {"org_ids": ids})
        return [Licence.model_validate(x) for x in body["licences"]] if isinstance(body, dict) else []
