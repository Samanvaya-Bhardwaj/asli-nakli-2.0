"""Read a scanned or typed code and decide what to do with it (PLAN.md section 10.2 steps 4-8).

A correction never becomes a fact on its own: for consumers it always needs confirmation, for staff
it is only made when the expected set leaves one clear candidate.
"""

from collections.abc import Callable, Collection
from dataclasses import dataclass
from datetime import date
from typing import Literal

from asali_codes.candidates import Candidate, gtin_candidates, serial_candidates
from asali_codes.confusion import weighted_distance
from asali_codes.parse import Reading, parse

Decision = Literal["accepted", "corrected", "needs_confirmation", "needs_choice", "unreadable"]
Context = Literal["staff", "consumer"]
ExistsFn = Callable[[str | None, list[str]], set[str]]
# What the records say about each candidate pack: its lot and expiry, when known. Used to check a candidate
# against what else is printed on the label (Phase 2: clean a noisy reading with the context around it).
FactsFn = Callable[[list[str]], dict[str, tuple[str | None, date | None]]]

AUTO_MAX_COST = 1.0
AUTO_MIN_MARGIN = 0.5
MAX_CHOICES = 5
EXPECTED_MAX_COST = 2.0

UNREADABLE = "We could not read this code. Scan again or type the code printed after SN."
PRODUCT_ONLY = (
    "This is the product number, not the pack's own code. "
    "Scan the QR code or type the 11-character code printed after SN."
)
CHOOSE = "This could be more than one pack. Choose the code printed on the pack."


@dataclass(frozen=True)
class ReadResult:
    reading: Reading
    decision: Decision
    gtin: str | None
    serial: str | None
    lot: str | None
    expiry: date | None
    chosen: Candidate | None
    choices: tuple[Candidate, ...]
    message: str


def format_serial(serial: str) -> str:
    return "-".join(serial[i : i + 4] for i in range(0, len(serial), 4))


def read(
    raw: str,
    *,
    context: Context,
    issuers: Collection[str],
    expected: Collection[tuple[str, str]] | None = None,
    exists: ExistsFn | None = None,
    known_gtins: Collection[str] = (),
    facts: FactsFn | None = None,
) -> ReadResult:
    r = parse(raw)

    def result(decision: Decision, message: str, **kw: object) -> ReadResult:
        fields: dict[str, object] = {
            "gtin": r.gtin if r.status["gtin"] == "valid" else None,
            "serial": r.serial if r.status["serial"] == "valid" else None,
            "lot": r.lot,
            "expiry": r.expiry,
            "chosen": None,
            "choices": (),
        }
        fields.update(kw)
        return ReadResult(reading=r, decision=decision, message=message, **fields)  # type: ignore[arg-type]

    if r.grammar == "bare_gtin":
        return result("unreadable", PRODUCT_ONLY)
    if r.status["serial"] == "missing":
        return result("unreadable", UNREADABLE)

    gtin, gtin_fix = _resolve_gtin(r, known_gtins, expected)
    if r.status["gtin"] not in ("valid", "missing") and gtin is None:
        return result("unreadable", UNREADABLE)

    if r.status["serial"] == "valid":
        if gtin_fix is None:
            return result("accepted", "")
        return _corrected(result, context, gtin_fix, gtin, r.serial or "", "product number", r.gtin or "")

    pool = _serial_pool(r.serial or "", gtin, issuers, expected, exists)
    if facts is not None and len(pool) > 1 and (r.lot or r.expiry):
        pool = _by_label(pool, facts, r.lot, r.expiry)
    if not pool or len(pool) > MAX_CHOICES:
        return result("unreadable", UNREADABLE)
    best = pool[0]
    margin_ok = len(pool) == 1 or pool[1].cost - best.cost >= AUTO_MIN_MARGIN
    if best.cost <= AUTO_MAX_COST and margin_ok:
        return _corrected(result, context, best, gtin, best.value, "code", r.serial or "")
    return result("needs_choice", CHOOSE, gtin=gtin, choices=tuple(pool))


def _corrected(
    result: Callable[..., ReadResult],
    context: Context,
    chosen: Candidate,
    gtin: str | None,
    serial: str,
    what: str,
    seen: str,
) -> ReadResult:
    if what == "code":
        shown_seen, shown_true = format_serial(seen), format_serial(serial)
    else:
        shown_seen, shown_true = seen, chosen.value
    if context == "staff":
        prefix = "Read as" if what == "code" else "Read the product number as"
        msg = f"{prefix} {shown_seen}, corrected to {shown_true}."
        return result("corrected", msg, gtin=gtin, serial=serial, chosen=chosen)
    shown = format_serial(serial) if what == "code" else f"{format_serial(serial)} with product number {gtin}"
    msg = f"Does your pack show {shown}?"
    return result("needs_confirmation", msg, gtin=gtin, serial=serial, chosen=chosen)


def _resolve_gtin(
    r: Reading, known_gtins: Collection[str], expected: Collection[tuple[str, str]] | None
) -> tuple[str | None, Candidate | None]:
    if r.status["gtin"] == "valid":
        return r.gtin, None
    if r.status["gtin"] == "missing":
        return None, None
    known = set(known_gtins) | {g for g, _ in (expected or ())}
    cands = gtin_candidates(r.gtin or "", known)
    if len(cands) == 1 or (len(cands) > 1 and cands[1].cost - cands[0].cost >= AUTO_MIN_MARGIN):
        return cands[0].value, cands[0]
    return None, None


def _by_label(pool: list[Candidate], facts: FactsFn, lot: str | None, expiry: date | None) -> list[Candidate]:
    """Keep the candidates whose lot and expiry fit what the label also says, when that rules some out.

    A candidate the records know nothing about is not ruled out. If no candidate fits, or all of them do,
    the pool is left as it was: the context only counts when it separates one candidate from another.
    """
    known = facts([c.value for c in pool])
    fits: list[Candidate] = []
    for c in pool:
        c_lot, c_exp = known.get(c.value, (None, None))
        if (lot is None or c_lot is None or c_lot == lot) and (
            expiry is None or c_exp is None or c_exp == expiry
        ):
            fits.append(c)
    if not fits or len(fits) == len(pool):
        return pool
    said = " and ".join(x for x in ("lot" if lot else "", "expiry" if expiry else "") if x)
    return [
        Candidate(c.value, c.cost, (*c.edits, f"the {said} printed on the pack matches this code's record"))
        for c in fits
    ]


def _serial_pool(
    seen: str,
    gtin: str | None,
    issuers: Collection[str],
    expected: Collection[tuple[str, str]] | None,
    exists: ExistsFn | None,
) -> list[Candidate]:
    if expected is not None:
        pool = []
        for g, s in expected:
            if gtin is not None and g != gtin:
                continue
            d = weighted_distance(s, seen)
            if d <= EXPECTED_MAX_COST:
                pool.append(Candidate(s, d))
        return sorted(pool, key=lambda c: (c.cost, c.value))
    cands = serial_candidates(seen, issuers)
    if exists is not None and cands:
        real = exists(gtin, [c.value for c in cands])
        cands = [c for c in cands if c.value in real]
    return cands
