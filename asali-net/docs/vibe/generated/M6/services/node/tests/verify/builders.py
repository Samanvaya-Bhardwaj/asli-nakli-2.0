"""Hand-made facts for the rule tests: a normal pack made by Kesar, via Dakshin, sold by Sharma Medicos."""

from dataclasses import replace
from datetime import date, datetime, timedelta

from asali_node.canonical import IST, Alert, CityCount, Event, Licence, Product, ScanStat, UnitView
from asali_node.verify.models import Facts, Hop

G, S, LOT = "08901003000111", "KS000000001", "K/26/0001"
TODAY = date(2026, 11, 20)
NAMES = {"kesar": "Kesar Biologics", "dist-south": "Dakshin Pharma Agencies", "shop-delhi": "Sharma Medicos",
         "shop-mumbai": "Apna Chemist", "regulator": "Drug Control"}  # fmt: skip
CITY = {"kesar": "Pune", "dist-south": "Bengaluru", "shop-delhi": "Delhi", "shop-mumbai": "Mumbai"}


def at(day: int, hour: int = 10) -> datetime:
    return datetime(2026, 11, day, hour, tzinfo=IST)


def ev(org: str, kind: str, day: int, **kw) -> Event:
    return Event(event_id=f"{org}:{kind}:{day}:{kw.get('ref', '')}", org_id=org, event_type=kind, at=at(day), gtin=G,
                 serial=S, city=CITY[org], **kw)  # fmt: skip


def hop(org: str, kind: str, events: list[Event], known: bool = True, status: str = "in_stock") -> Hop:
    view = UnitView(gtin=G, serial=S, known=known, lot=LOT, expiry=date(2027, 3, 31), status_here=status, events=events)  # type: ignore[arg-type]
    return Hop(org, kind, NAMES[org], CITY[org], view)


def normal_chain() -> tuple[Hop, ...]:
    return (
        hop("kesar", "pharma", [ev("kesar", "commission", 1), ev("kesar", "ship", 2, to_org="dist-south", ref="S1")]),
        hop("dist-south", "distributor", [ev("dist-south", "receive", 3, from_org="kesar", ref="S1"),
                                          ev("dist-south", "ship", 4, to_org="shop-delhi", ref="D1")]),  # fmt: skip
        hop("shop-delhi", "shop", [ev("shop-delhi", "receive", 5, from_org="dist-south", ref="D1"),
                                   ev("shop-delhi", "sell", 12, ref="B1")], status="sold"),  # fmt: skip
    )


PRODUCT = Product(gtin=G, brand="Glargikes", generic="insulin glargine", strength="100 IU/ml", form="injection",
                  pack_size=1, storage_min_c=2, storage_max_c=8, owner_org="kesar")  # fmt: skip


def facts(**kw) -> Facts:
    base = Facts(gtin=G, serial=S, issuer_known=True, issuer_reachable=True, today=TODAY, product=PRODUCT,
                 batch_status="released", expiry=date(2027, 3, 31), lot=LOT, chain=normal_chain(), names=NAMES)  # fmt: skip
    return replace(base, **kw)


def alert(kind: str = "recall", lot: str | None = LOT, gtin: str = G) -> Alert:
    return Alert(alert_id="A1", kind=kind, gtin=gtin, lot=lot, manufacturer_org="kesar", issued_at=at(10), reason="r",
                 doc_id=None)  # type: ignore[arg-type]


def licence(org: str, status: str = "active", valid_to: date = date(2027, 12, 31)) -> Licence:
    return Licence(org_id=org, licence_no="L", licence_type="retail", valid_from=date(2020, 1, 1), valid_to=valid_to,
                   status=status)  # type: ignore[arg-type]


def scans(city: str, first_day: int, last_day: int, count: int = 1) -> ScanStat:
    return ScanStat(gtin=G, serial=S, total=count, by_city=[CityCount(city=city, count=count, first_at=at(first_day),
                                                                       last_at=at(last_day))])  # fmt: skip


def later(days: int) -> datetime:
    return at(1) + timedelta(days=days)


def edit(h: Hop, events: list[Event]) -> Hop:
    """The same hop with different events."""
    return replace(h, view=h.view.model_copy(update={"events": events}))  # type: ignore[union-attr]
