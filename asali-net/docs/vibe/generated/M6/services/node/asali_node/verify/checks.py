"""Turn what a consumer typed or scanned into a pack to verify, or into a question (PLAN.md 10.2 for consumers).

A correction is never silently accepted here: a consumer always has to confirm it against the printed pack.
"""

from dataclasses import dataclass, field
from typing import Any

from asali_codes.candidates import serial_candidates
from asali_codes.parse import parse
from asali_codes.read import format_serial, read

from asali_node.network.client import SourceUnavailable

PLACEHOLDER_GTIN = "0" * 14


@dataclass
class Resolution:
    decision: str  # verify | needs_confirmation | needs_choice | unreadable | cannot_ask
    message: str = ""
    gtin: str | None = None
    serial: str | None = None
    read: dict[str, Any] = field(default_factory=dict)
    choices: list[str] = field(default_factory=list)


async def _existing(share: Any, orgs: list[dict[str, Any]], gtin: str | None, serials: list[str]) -> set[str]:
    real: set[str] = set()
    by_code = {o["issuer_code"]: o["org_id"] for o in orgs if o.get("issuer_code")}
    for code, org in by_code.items():
        mine = [s for s in serials if s.startswith(code)]
        if not mine:
            continue
        params: dict[str, Any] = {"serials": ",".join(mine)}
        if gtin:
            params["gtin"] = gtin
        try:
            real |= set((await share.get(org, "/share/v1/units/exists", params))["existing"])
        except SourceUnavailable:
            continue  # candidates from an issuer that does not answer stay out: nothing can be confirmed for them
    return real


async def _gtin_for(share: Any, orgs: list[dict[str, Any]], serial: str) -> str | None:
    org = next((o["org_id"] for o in orgs if o.get("issuer_code") == serial[:2]), None)
    if org is None:
        return None
    try:
        return str((await share.get(org, f"/share/v1/units/by-serial/{serial}"))["gtin"])
    except SourceUnavailable:
        return None


async def resolve_input(raw: str, share: Any, orgs: list[dict[str, Any]]) -> Resolution:
    issuers = {o["issuer_code"] for o in orgs if o.get("issuer_code")}
    first = parse(raw)
    real: set[str] = set()
    if first.status["serial"] not in ("valid", "missing") and first.serial:
        gtin = first.gtin if first.status["gtin"] == "valid" else None
        real = await _existing(share, orgs, gtin, [c.value for c in serial_candidates(first.serial, issuers)])
    res = read(raw, context="consumer", issuers=issuers, exists=lambda _g, ss: {s for s in ss if s in real})
    info = {"raw": raw, "decision": res.decision, "corrections": []}
    if res.decision == "unreadable":
        return Resolution("unreadable", res.message, read=info)
    if res.decision == "needs_choice":
        return Resolution("needs_choice", res.message, read=info, choices=[c.value for c in res.choices])
    if res.serial is None:
        return Resolution("unreadable", res.message, read=info)
    if res.chosen is not None:
        info["corrections"] = [{"field": "serial", "from": first.serial, "to": res.serial, "cost": res.chosen.cost}]
    gtin = res.gtin or await _gtin_for(share, orgs, res.serial)
    if res.decision == "needs_confirmation":
        return Resolution("needs_confirmation", f"Does your pack show {format_serial(res.serial)}?", gtin, res.serial, info)
    return Resolution("verify", "", gtin or PLACEHOLDER_GTIN, res.serial, info)
