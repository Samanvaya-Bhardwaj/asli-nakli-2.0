"""Plant scenarios S1-S4, S7, S8 and S9 in the seeded simulation network, through the portal APIs.

    python seed/scenarios.py --simulation

Writes infra/out/SIM/scenarios.json (the codes to check). The expected result for each is in seed/expected.json.
S3 and S7 need a pack that reached a shop without the paperwork; the simulation-only force-receipt route
records that, exactly as a careless or dishonest shop could. S5 and S6 (text only) are planted by the text
milestone. Running twice adds only what is missing.
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
PORTS = {"shop-delhi": 8201, "shop-mumbai": 8202, "shop-bengaluru": 8203, "tarang": 8301, "medivra": 8302}


def element(gtin: str, serial: str) -> str:
    return f"(01){gtin}(21){serial}"


def swap_and_letter(serial: str) -> str:
    """A typed misread: a swapped pair, and the letter O where a zero is printed."""
    chars = list(serial)
    i = next(k for k in range(3, 9) if chars[k] != chars[k + 1])
    chars[i], chars[i + 1] = chars[i + 1], chars[i]
    return "".join(chars).replace("0", "O", 1)


def lot_of(pharma: Portal, gtin: str, serial: str) -> str:
    """The recall needs the batch, which only the maker's own records give."""
    unit = pharma.call("GET", f"/api/unit/{gtin}/{serial}")
    if not unit["known"]:
        raise RuntimeError("pack not found at its maker")
    return str(unit["lot"])


def force_and_sell(shop: Portal, frm: str, ref: str, code: tuple[str, str], hour: float) -> None:
    g, s = code
    shop.call(
        "POST",
        "/api/sim/force-receipt",
        json={"from_org": frm, "source_ref": ref, "units": [{"gtin": g, "serial": s}], "at": at(hour)},
    )
    shop.scan_session("sell", [(g, s)], random.Random(1), 0, {"at": at(hour + 10), "prices": {g: 9900}})


def main() -> int:
    argparse.ArgumentParser().add_argument("--simulation", action="store_true", required=True)
    state = json.loads((OUT / "seed_state.json").read_text())
    password = json.loads((OUT / "secrets.json").read_text())["staff_password"]
    p = {k: Portal(k, f"http://127.0.0.1:{v}", password) for k, v in PORTS.items()}
    planted = OUT / "scenarios.json"
    out: dict[str, Any] = json.loads(planted.read_text()) if planted.exists() else {}
    sold = {
        shop: [c for b in state["bills"] if b["shop"] == shop for c in b["codes"]]
        for shop in PORTS
        if shop.startswith("shop")
    }

    g1, s1 = sold["shop-delhi"][0]
    out.setdefault("S1", {"gtin": g1, "serial": s1, "raw": element(g1, s1)})
    out.setdefault(
        "S9", {"gtin": g1, "serial": s1, "raw": element(g1, swap_and_letter(s1)), "true_serial": s1}
    )

    gtin = p["tarang"].call("GET", "/api/products")["products"][0]["gtin"]
    s2 = make_serial("TP")  # a valid check character, but never issued
    out.setdefault("S2", {"gtin": gtin, "serial": s2, "raw": element(gtin, s2)})

    if "S3" not in out:  # sold in Delhi, then a copy of its code is sold in Mumbai
        g3, s3 = sold["shop-delhi"][1]
        force_and_sell(p["shop-mumbai"], "dist-west", "DSP-FORGED-1", (g3, s3), 900)
        out["S3"] = {"gtin": g3, "serial": s3, "raw": element(g3, s3), "complaint_city": "Mumbai"}

    if "S4" not in out:  # a recalled medivra batch
        mv = next(c for codes in sold.values() for c in codes if c[1].startswith("MV"))
        lot = lot_of(p["medivra"], *mv)
        p["medivra"].call(
            "POST",
            "/api/recalls",
            json={
                "gtin": mv[0],
                "lot": lot,
                "reason": "failed dissolution test",
                "level": "class II",
                "at": at(920),
            },
        )
        out["S4"] = {"gtin": mv[0], "serial": mv[1], "raw": element(*mv), "lot": lot}

    if "S7" not in out:  # a pack still in North Star's stock turns up sold in Bengaluru
        g7, s7 = state["stock"]["dist-north"][0]
        force_and_sell(p["shop-bengaluru"], "dist-north", "DSP-GHOST-1", (g7, s7), 930)
        out["S7"] = {"gtin": g7, "serial": s7, "raw": element(g7, s7)}

    g8, s8 = sold["shop-mumbai"][0]  # received from dist-west, so dist-west is on its route
    out.setdefault("S8", {"gtin": g8, "serial": s8, "raw": element(g8, s8)})

    planted.write_text(json.dumps(out, indent=1))
    print("planted:", ", ".join(sorted(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
