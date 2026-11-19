"""Plant scenarios S1-S4, S7 and S9 in the seeded simulation network, through the portal APIs.

    python seed/scenarios.py --simulation

Writes infra/out/SIM/scenarios.json (the codes to check). The expected verdict for each is in seed/expected.json.
S3 and S7 need a pack that reached a shop without the paperwork; the simulation-only force-receipt route
records that, exactly as a careless or dishonest shop could. S5, S6 and S8 are planted in the text milestone
and in the network test.
"""

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "seed"))
sys.path.insert(0, str(ROOT / "infra" / "scripts"))
sys.path.insert(0, str(ROOT / "services" / "node"))
from asali_node.packs import make_serial
from client import Portal, at

OUT = ROOT / "infra" / "out" / "SIM"


def element(gtin: str, serial: str) -> str:
    return f"(01){gtin}(21){serial}"


def swap_and_letter(serial: str) -> str:
    """A typed misread: a swapped pair, and the letter O where a zero is printed."""
    chars = list(serial)
    i = next(k for k in range(3, 9) if chars[k] != chars[k + 1])
    chars[i], chars[i + 1] = chars[i + 1], chars[i]
    return "".join(chars).replace("0", "O", 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--simulation", action="store_true", required=True)
    ap.parse_args()
    state = json.loads((OUT / "seed_state.json").read_text())
    password = json.loads((OUT / "secrets.json").read_text())["staff_password"]
    port = {"shop-delhi": 8201, "shop-mumbai": 8202, "shop-bengaluru": 8203, "tarang": 8301, "medivra": 8302,
            "dist-north": 8101}  # fmt: skip
    p = {k: Portal(k, f"http://127.0.0.1:{v}", password) for k, v in port.items()}
    out: dict[str, Any] = {}

    delhi = [c for b in state["bills"] if b["shop"] == "shop-delhi" for c in b["codes"]]
    g1, s1 = delhi[0]
    out["S1"] = {"gtin": g1, "serial": s1, "raw": element(g1, s1)}

    tarang_gtin = p["tarang"].call("GET", "/api/products")["products"][0]["gtin"]
    s2 = make_serial("TP")  # a valid check character, but never issued
    out["S2"] = {"gtin": tarang_gtin, "serial": s2, "raw": element(tarang_gtin, s2)}

    g3, s3 = delhi[1]  # sold in Delhi, then a copy of its code turns up in Mumbai
    p["shop-mumbai"].call("POST", "/api/sim/force-receipt", json={"from_org": "dist-west", "source_ref": "DSP-FORGED-1",
                                                                   "units": [{"gtin": g3, "serial": s3}], "at": at(900)})  # fmt: skip
    p["shop-mumbai"].scan_session("sell", [(g3, s3)], random.Random(1), 0, {"at": at(910), "prices": {g3: 9900}})
    out["S3"] = {"gtin": g3, "serial": s3, "raw": element(g3, s3), "complaint_city": "Mumbai"}

    mv = next(c for b in state["bills"] for c in b["codes"] if c[1].startswith("MV") and c not in (delhi[0], delhi[1]))
    lot = _lot_of(p["medivra"], *mv)
    p["medivra"].call("POST", "/api/recalls", json={"gtin": mv[0], "lot": lot, "reason": "failed dissolution test", "level": "class II", "at": at(920)})
    out["S4"] = {"gtin": mv[0], "serial": mv[1], "raw": element(*mv), "lot": lot}

    g7, s7 = state["stock"]["dist-north"][0]  # still in North Star's stock, so no dispatch to Bengaluru exists
    p["shop-bengaluru"].call("POST", "/api/sim/force-receipt", json={"from_org": "dist-north", "source_ref": "DSP-GHOST-1",
                                                                      "units": [{"gtin": g7, "serial": s7}], "at": at(930)})  # fmt: skip
    p["shop-bengaluru"].scan_session("sell", [(g7, s7)], random.Random(2), 0, {"at": at(940), "prices": {g7: 9900}})
    out["S7"] = {"gtin": g7, "serial": s7, "raw": element(g7, s7)}

    out["S9"] = {"gtin": g1, "serial": s1, "raw": element(g1, swap_and_letter(s1)), "true_serial": s1}
    (OUT / "scenarios.json").write_text(json.dumps(out, indent=1))
    print("planted:", ", ".join(sorted(out)))
    return 0


def _lot_of(pharma: Portal, gtin: str, serial: str) -> str:
    """The recall needs the batch, which only the maker's own records give."""
    unit = pharma.call("GET", f"/api/unit/{gtin}/{serial}")
    if not unit["known"]:
        raise RuntimeError("pack not found at its maker")
    return str(unit["lot"])


if __name__ == "__main__":
    sys.exit(main())
