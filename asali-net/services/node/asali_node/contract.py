"""The shapes the portal reads from the node API. The browser's TypeScript types are generated from these
(`infra/scripts/gen_api_types.py`), and `tests/network` checks that live answers match them, so the two cannot drift."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

OrgType = Literal["pharma", "distributor", "shop", "consumer", "regulator"]
Verdict = Literal["genuine", "caution", "do_not_use", "cannot_check"]
Mode = Literal["network", "simulation"]


class Shape(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ShopSettings(Shape):
    area: str
    state_code: str
    receipt_language: Literal["en", "hi", "mr", "kn"]
    drug_licence_no: str
    gstin: str
    helpline: str


class Config(Shape):
    org_id: str
    org_type: OrgType
    name: str
    city: str
    state: str
    mode: Mode
    host_name: str
    issuer_code: str | None
    gs1_prefix: str | None
    shop: ShopSettings | None


class Me(Shape):
    username: str
    role: str
    display_name: str
    org_id: str
    org_type: OrgType


class Reason(Shape):
    code: str
    strength: Literal["do_not_use", "caution", "cannot_check"]
    text: str
    evidence: list[dict[str, Any]]


class HistoryEvent(Shape):
    event_id: str
    org_id: str
    event_type: str
    at: str
    gtin: str
    serial: str
    lot: str | None
    from_org: str | None
    to_org: str | None
    ref: str | None
    city: str


class ServedBy(Shape):
    org_id: str
    host_name: str
    at: str


class HistoryHop(Shape):
    org_id: str
    org_name: str
    city: str
    unavailable: str | None
    events: list[HistoryEvent]
    served_by: ServedBy | None


class Snippet(Shape):
    text: str


class DocLink(Shape):
    entity: str
    confidence: float
    because: list[str]


class ClaimRow(Shape):
    name: str
    value: Any
    check: str
    against: str


class DocHit(Shape):
    doc_id: str
    org_id: str
    org_name: str
    doc_type: str
    kind: Literal["official", "operational", "allegation"]
    title: str
    created_at: str
    snippet: Snippet
    linked_to: list[DocLink]
    claims: list[ClaimRow]
    issue_labels: list[str]
    label: str


class Source(Shape):
    org_id: str
    status: Literal["answered", "unreachable", "skipped"]
    ms: int
    host_name: str | None
    reason: str


class Product(Shape):
    brand: str
    generic: str
    strength: str


class Pack(Shape):
    gtin: str | None
    serial: str
    lot: str | None
    expiry: str | None
    product: Product | None
    found: bool


class CodeRead(Shape):
    raw: str
    decision: str
    corrections: list[dict[str, Any]]
    confirmed: bool | None = None


class VerifyResult(Shape):
    verdict: Verdict
    word: str
    headline: str
    action: str
    reasons: list[Reason]
    pack: Pack
    read: CodeRead | None
    history: list[HistoryHop]
    documents: list[DocHit]
    sources: list[Source]
    mode: Mode
    checked_at: str


class CheckDone(Shape):
    status: Literal["done"]
    result: VerifyResult


class CheckNeedsConfirmation(Shape):
    status: Literal["needs_confirmation"]
    message: str
    read: CodeRead
    choices: list[str]
    check_id: str
    serial: str
    serial_shown: str


class CheckNeedsChoice(Shape):
    status: Literal["needs_choice", "unreadable"]
    message: str
    read: CodeRead | None = None
    choices: list[str]


class NetworkOrg(Shape):
    org_id: str
    org_type: OrgType
    name: str
    city: str
    state: str
    host_name: str
    last_seen: str | None
    online: bool
    latency_ms: int | None
    engine: str | None
    vault: str | None
    reason: str | None = None


class Network(Shape):
    orgs: list[NetworkOrg]
    online: int
    total: int
    mode: Mode
    self: str
    directory_stale: Any


class Party(Shape):
    org_id: str
    org_type: OrgType
    name: str
    city: str
    state: str
    host_name: str
    base_url: str
    serves_here: bool


class Parties(Shape):
    parties: list[Party]


# Name in the generated file -> model. Order is the order in the generated file.
EXPORTS: dict[str, type[BaseModel]] = {
    "Config": Config, "Me": Me, "VerifyResult": VerifyResult, "CheckDone": CheckDone,
    "CheckNeedsConfirmation": CheckNeedsConfirmation, "CheckNeedsChoice": CheckNeedsChoice,
    "Network": Network, "Parties": Parties,
}  # fmt: skip
