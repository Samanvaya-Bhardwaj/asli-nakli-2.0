"""A consumer's noisy code is cleaned using the lot printed next to it, through the makers' own records."""

import asyncio
from datetime import date

from asali_codes.candidates import serial_candidates
from asali_node.network.client import SourceUnavailable
from asali_node.verify.checks import resolve_input

GTIN = "08901001000124"
ORGS = [{"org_id": "tarang", "org_type": "pharma", "issuer_code": "TP"}]
NEAR = [c.value for c in serial_candidates("TPM0S346Q37", {"TP"}) if c.cost == 1.0][:3]
LABEL = f"https://id.asali.example/01/{GTIN}/21/TPM0S346Q37?10=TP24A017"


class Share:
    def __init__(self, lots):
        self.lots, self.asked = lots, []

    async def get(self, org, path, params=None):
        self.asked.append(path)
        if path == "/share/v1/units/exists":
            return {"existing": [s for s in params["serials"].split(",") if s in self.lots]}
        if path.startswith("/share/v1/units/by-serial/"):
            s = path.rsplit("/", 1)[1]
            if s in self.lots:
                return {
                    "gtin": GTIN,
                    "serial": s,
                    "known": True,
                    "lot": self.lots[s],
                    "expiry": date(2027, 3, 31).isoformat(),
                }
        raise SourceUnavailable(org, "unreachable")


def run(label, lots):
    share = Share(lots)
    return asyncio.run(resolve_input(label, share, ORGS)), share


def test_the_printed_lot_turns_a_choice_into_a_question_with_one_answer():
    res, _ = run(LABEL, {NEAR[0]: "TP24A017", NEAR[1]: "TP24A018", NEAR[2]: "TP24A018"})
    assert res.decision == "needs_confirmation"
    assert res.serial == NEAR[0]


def test_a_label_with_no_lot_is_not_given_extra_lookups():
    res, share = run(f"https://id.asali.example/01/{GTIN}/21/TPM0S346Q37", {s: "TP24A018" for s in NEAR})
    assert res.decision == "needs_choice"
    assert not any(p.startswith("/share/v1/units/by-serial/") for p in share.asked)
