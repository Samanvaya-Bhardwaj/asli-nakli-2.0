"""The structured records a document can be linked to, as plain data (TEXT_ML.md 4.5).

The node builds one from what it can read through the share APIs; the trainer builds one from the seeded
network's snapshot. The linker only ever sees this, so both go through the same code.
"""

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class ProductInfo:
    gtin: str
    brand: str
    generic: str
    strength: str
    maker_org: str


@dataclass(frozen=True)
class BatchInfo:
    gtin: str
    lot: str
    maker_org: str
    mfg: date
    expiry: date
    status: str = "released"

    @property
    def key(self) -> str:
        return f"batch:{self.gtin}/{self.lot}"


@dataclass(frozen=True)
class UnitInfo:
    gtin: str
    serial: str
    lot: str
    maker_org: str
    chain_orgs: tuple[str, ...]
    chain_cities: tuple[str, ...]
    first: date
    last: date

    @property
    def key(self) -> str:
        return f"unit:{self.gtin}/{self.serial}"


@dataclass(frozen=True)
class ShipmentInfo:
    from_org: str
    ref: str
    to_org: str
    at: date
    gtins: tuple[str, ...] = ()
    cities: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        return f"shipment:{self.from_org}/{self.ref}"


@dataclass(frozen=True)
class OrgInfo:
    org_id: str
    name: str
    org_type: str
    city: str


@dataclass
class World:
    products: list[ProductInfo] = field(default_factory=list)
    batches: list[BatchInfo] = field(default_factory=list)
    units: dict[str, UnitInfo] = field(default_factory=dict)  # by serial
    shipments: list[ShipmentInfo] = field(default_factory=list)
    orgs: dict[str, OrgInfo] = field(default_factory=dict)

    def product(self, gtin: str) -> ProductInfo | None:
        return next((p for p in self.products if p.gtin == gtin), None)

    def batch(self, gtin: str, lot: str) -> BatchInfo | None:
        return next((b for b in self.batches if b.gtin == gtin and b.lot == lot), None)

    def holders(self, gtin: str, lot: str) -> set[str]:
        """Organisations on the route of any known unit of this batch."""
        return {o for u in self.units.values() if u.gtin == gtin and u.lot == lot for o in u.chain_orgs}
