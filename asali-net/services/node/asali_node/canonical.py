"""The shapes every node shares, whatever its own storage looks like (PLAN.md section 6).

Times are always timezone-aware; adapters convert their native formats to IST.
"""

from datetime import date, datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import AfterValidator, BaseModel, ConfigDict

IST = ZoneInfo("Asia/Kolkata")


def _aware(v: datetime) -> datetime:
    if v.tzinfo is None or v.utcoffset() is None:
        raise ValueError("datetime must carry a timezone")
    return v


AwareDT = Annotated[datetime, AfterValidator(_aware)]
EventType = Literal["commission", "ship", "receive", "sell", "return", "destroy"]
StatusHere = Literal["in_stock", "shipped", "sold", "returned", "destroyed", "never_held"]
BatchStatus = Literal["released", "quarantine", "recalled"]
Form = Literal["tablet", "capsule", "injection", "syrup", "other"]


class Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# ---- shared read models ----
class Product(Model):
    gtin: str
    brand: str
    generic: str
    strength: str
    form: Form
    pack_size: int
    storage_min_c: float | None
    storage_max_c: float | None
    owner_org: str


class Batch(Model):
    gtin: str
    lot: str
    mfg_date: date
    expiry_date: date
    status: BatchStatus
    owner_org: str


class Event(Model):
    event_id: str
    org_id: str
    event_type: EventType
    at: AwareDT
    gtin: str
    serial: str | None
    lot: str | None = None
    from_org: str | None = None
    to_org: str | None = None
    ref: str | None = None
    city: str


class ServedBy(Model):
    org_id: str
    host_name: str
    at: AwareDT


class UnitView(Model):
    gtin: str
    serial: str
    known: bool
    lot: str | None
    expiry: date | None
    status_here: StatusHere
    events: list[Event]
    served_by: ServedBy | None = None


class UnitRef(Model):
    gtin: str
    serial: str
    lot: str | None = None
    expiry: date | None = None
    raw: str | None = None  # what the scanner sent, when the org keeps it
    corrected: bool = False


class Shipment(Model):
    shipment_id: str
    from_org: str
    to_org: str
    at: AwareDT
    units: list[UnitRef]


class StockLine(Model):
    gtin: str
    serial: str
    lot: str | None
    expiry: date | None
    since: AwareDT | None


class Alert(Model):
    alert_id: str
    kind: Literal["recall", "nsq", "ban"]
    gtin: str
    lot: str | None
    manufacturer_org: str
    issued_at: AwareDT
    reason: str
    doc_id: str | None
    states: list[str] | None = None  # None means national


class Licence(Model):
    org_id: str
    licence_no: str
    licence_type: str
    valid_from: date
    valid_to: date
    status: Literal["active", "suspended", "cancelled"]


class CityCount(Model):
    city: str
    count: int
    first_at: AwareDT
    last_at: AwareDT


class ScanStat(Model):
    gtin: str
    serial: str
    total: int
    by_city: list[CityCount]


class ReportRecord(Model):
    report_id: str
    doc_id: str
    gtin: str | None
    serial: str | None
    city: str
    at: AwareDT


# ---- inputs for writes into the node's own database ----
class NewProduct(Model):
    gtin: str
    brand: str
    generic: str
    strength: str
    form: Form
    pack_size: int
    storage_min_c: float | None = None
    storage_max_c: float | None = None
    schedule: str | None = None


class NewBatch(Model):
    gtin: str
    lot: str
    mfg_date: date
    expiry_date: date
    quantity: int


class NewShipment(Model):
    shipment_id: str
    to_org: str
    at: AwareDT
    units: list[UnitRef]
    by: str
    vehicle_no: str | None = None


class NewReceipt(Model):
    from_org: str
    source_ref: str
    at: AwareDT
    units: list[UnitRef]
    by: str


class SaleLine(Model):
    gtin: str
    serial: str
    mrp_paise: int


class NewSale(Model):
    bill_no: str
    at: AwareDT
    lines: list[SaleLine]
    customer_ref_hash: str | None = None


class NewReturn(Model):
    bill_no: str
    gtin: str
    serial: str
    reason: str
    at: AwareDT


class StaffRecord(Model):
    username: str
    password_hash: str
    role: Literal["admin", "operator"]
    display_name: str


class ScanCorrection(Model):
    at: AwareDT
    raw: str
    field: Literal["gtin", "serial"]
    chosen: str
    cost: float
    confirmed_by: str


class DocLink(Model):
    entity_type: Literal["unit", "batch", "product", "shipment", "org"]
    entity_key: str
    confidence: float
    linked_at: AwareDT


class NewCheck(Model):
    raw_input: str
    gtin: str | None
    serial: str | None
    verdict: str | None
    reasons: list[str]
    city: str
    at: AwareDT
    device_hash: str | None = None


class NewReport(Model):
    check_id: str | None
    doc_id: str
    gtin: str | None
    serial: str | None
    city: str
    at: AwareDT


class NewAlert(Model):
    kind: Literal["recall", "nsq", "ban"]
    gtin: str
    lot: str | None
    manufacturer_org: str
    issued_at: AwareDT
    reason: str
    doc_id: str | None = None
    states: list[str] | None = None


class NewInspection(Model):
    org_id: str
    inspected_at: AwareDT
    outcome: str
    doc_id: str | None = None


NewDispatch = NewShipment  # a distributor's dispatch has the same fields as a pharma shipment
