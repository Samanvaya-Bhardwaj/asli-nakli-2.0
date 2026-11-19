"""What the rules look at (Facts) and what they produce (Reason). Pure data; no network in here."""

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from asali_node.canonical import Alert, Event, Licence, Product, ScanStat, UnitView

Strength = Literal["do_not_use", "caution", "cannot_check"]
DocKind = Literal[
    "official_quality_notice", "official_recall_notice", "temperature_excursion", "complaint", "contradiction"
]
COMPLAINT_LABELS = {"suspected_fake", "packaging_different", "no_effect"}


@dataclass(frozen=True)
class DocSignal:
    """One finding from a linked document. The text pipeline (M7) produces these; the rules only read them."""

    kind: DocKind
    doc_id: str
    confidence: float
    org_id: str
    quote: str = ""
    labels: tuple[str, ...] = ()
    city: str | None = None
    reporter_key: str = ""  # one per independent reporter; two complaints from the same person count once
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Hop:
    org_id: str
    org_type: str
    name: str
    city: str
    view: UnitView | None  # None when the node did not answer
    unavailable: str | None = None  # the reason, when it did not answer


@dataclass(frozen=True)
class Reason:
    code: str
    strength: Strength
    text: str
    evidence: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class Facts:
    gtin: str
    serial: str
    issuer_known: bool
    issuer_reachable: bool
    today: date
    product: Product | None = None
    batch_status: str | None = None
    expiry: date | None = None
    lot: str | None = None
    chain: tuple[Hop, ...] = ()
    other_sells: tuple[Event, ...] = ()  # sell events found at shops, whether or not the chain reached them
    other_receives: tuple[Event, ...] = ()  # receive events at those shops
    alerts: tuple[Alert, ...] = ()
    licences: tuple[Licence, ...] = ()
    scan_stats: tuple[ScanStat, ...] = ()
    doc_signals: tuple[DocSignal, ...] = ()
    missing: tuple[str, ...] = ()  # organisations whose answer was needed and did not come
    names: dict[str, str] = field(default_factory=dict)  # org id to the name people know it by

    @property
    def issuer_view(self) -> UnitView | None:
        return self.chain[0].view if self.chain else None
