"""Pull the claims a document makes out of its mentions, by document type (TEXT_ML.md 4.6).

A claim is a statement a document makes about a pack, a shipment or an organisation. Checking a claim
against the structured records happens later, in the verify engine.
"""

import re
from typing import Any

from asali_text.mentions import Mention, by_kind

KIND = {
    "coa": "official", "batch_release_note": "official", "deviation_report": "official", "recall_notice": "official",
    "nsq_alert": "official", "ban_order": "official", "inspection_report": "official",
    "temperature_report": "operational", "delivery_note": "operational", "discrepancy_note": "operational",
    "damage_report": "operational", "return_note": "operational",
    "counter_note": "allegation", "consumer_complaint": "allegation",
}  # fmt: skip
DOC_TYPES = sorted(KIND)


def _first(ms: list[Mention]) -> Any:
    return ms[0].value if ms else None


def _claim(name: str, value: Any, span: Mention | None = None) -> dict[str, Any]:
    return {"name": name, "value": value, "span": [span.start, span.end] if span else None}


def _buying(text: str, ms: list[Mention]) -> list[dict[str, Any]]:
    cities, shops, dates, expiries, lots = (by_kind(ms, k) for k in ("city", "org", "date", "expiry", "lot"))
    out = []
    for name, found in (("purchase_city", cities), ("purchase_shop", shops), ("purchase_date", dates),
                        ("stated_expiry", expiries), ("stated_lot", lots)):  # fmt: skip
        if found:
            value = found[0].value["org_id"] if name == "purchase_shop" else found[0].value
            out.append(_claim(name, value, found[0]))
    return out


def _temperature(text: str, ms: list[Mention]) -> list[dict[str, Any]]:
    temps, refs = by_kind(ms, "temperature"), by_kind(ms, "shipment_ref")
    out = []
    if refs:
        out.append(_claim("shipment_ref", refs[0].value, refs[0]))
    if temps:
        out.append(_claim("max_temp_c", max(t.value for t in temps)))
    readings = []
    for line in text.splitlines():  # one reading per line: "12/11 11:40  13.8 C"
        t = re.search(r"(\d{1,2}):(\d{2})\s+(\d+(?:\.\d+)?)\s?C", line)
        if t:
            readings.append({"minute": int(t[1]) * 60 + int(t[2]), "temp_c": float(t[3])})
    if readings:
        out.append(_claim("readings", readings))
    stated = by_kind(ms, "duration")
    if stated:
        out.append(_claim("stated_minutes", stated[0].value, stated[0]))
    return out


def minutes_above(readings: list[dict[str, Any]], limit_c: float, stated: int | None) -> int | None:
    """From the readings if there are any (time between a high reading and the next), else from the stated duration."""
    if readings:
        total = 0
        for a, b in zip(readings, readings[1:], strict=False):
            if a["temp_c"] > limit_c:
                total += b["minute"] - a["minute"]
        return total if total > 0 or any(r["temp_c"] > limit_c for r in readings) else 0
    return stated


def _rows(text: str, ms: list[Mention]) -> list[dict[str, Any]]:
    """One claim group per list row or notice: a lot, a manufacturer and a reason."""
    out = []
    for line in text.splitlines():
        lots = [m for m in by_kind(ms, "lot") if m.text in line]
        if not lots:
            continue
        maker = next((m.value["org_id"] for m in by_kind(ms, "org") if m.text in line), None)
        reason = line.split("|")[-1].strip() if "|" in line else line.strip()
        out.append({"name": "row", "value": {"lot": lots[0].value, "manufacturer": maker, "reason": reason}, "span": None})
    if not out and by_kind(ms, "lot"):
        lot = by_kind(ms, "lot")[0]
        maker = next((m.value["org_id"] for m in by_kind(ms, "org")), None)
        out.append({"name": "row", "value": {"lot": lot.value, "manufacturer": maker, "reason": text.strip()[:160]}, "span": None})
    return out


def _coa(text: str, ms: list[Mention]) -> list[dict[str, Any]]:
    out = []
    if by_kind(ms, "lot"):
        out.append(_claim("lot", by_kind(ms, "lot")[0].value, by_kind(ms, "lot")[0]))
    low = text.lower()
    failed = re.findall(r"(assay|dissolution|related substances|sterility|endotoxin)[^.\n]{0,25}(?:fail|out of spec|oos)", low)
    result = "fail" if failed or re.search(r"\bnot comply|does not comply|\bfails?\b|rejected", low) else "pass"
    out.append(_claim("result", result))
    if failed:
        out.append(_claim("failed_tests", sorted(set(failed))))
    return out


def _discrepancy(text: str, ms: list[Mention]) -> list[dict[str, Any]]:
    out = []
    if by_kind(ms, "shipment_ref"):
        out.append(_claim("shipment_ref", by_kind(ms, "shipment_ref")[0].value))
    for name, pat in (("expected", r"expected\s+(\d+)"), ("received", r"received\s+(\d+)")):
        m = re.search(pat, text, re.I)
        if m:
            out.append(_claim(name, int(m[1])))
    missing = [s.value for s in by_kind(ms, "serial")]
    if missing:
        out.append(_claim("missing_serials", missing))
    return out


def _inspection(text: str, ms: list[Mention]) -> list[dict[str, Any]]:
    orgs = by_kind(ms, "org")
    low = text.lower()
    outcome = ("licence_action" if re.search(r"suspend|cancel", low) else
               "observations" if re.search(r"observation|deficien|non-?compliance", low) else "satisfactory")  # fmt: skip
    return ([_claim("org", orgs[0].value["org_id"], orgs[0])] if orgs else []) + [_claim("outcome", outcome)]


EXTRACTORS = {
    "consumer_complaint": _buying, "counter_note": _buying, "temperature_report": _temperature, "nsq_alert": _rows,
    "ban_order": _rows, "recall_notice": _rows, "coa": _coa, "discrepancy_note": _discrepancy,
    "inspection_report": _inspection,
}  # fmt: skip


def extract_claims(doc_type: str, text: str, mentions: list[Mention]) -> list[dict[str, Any]]:
    fn = EXTRACTORS.get(doc_type)
    return fn(text, mentions) if fn else []
