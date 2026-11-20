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

import httpx

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


def clean(codes, used, ok=lambda g, s: True, allow=("genuine",)):
    """The first pack whose check is Genuine with no reasons at all: its batch has no notice, recall or complaint."""
    for g, s in codes:
        if g in used or not ok(g, s):
            continue
        r = httpx.post(
            "http://127.0.0.1:8402/api/check", json={"raw": element(g, s), "city": "Delhi"}, timeout=300
        ).json()
        if (
            r.get("status") == "done"
            and r["result"]["verdict"] in allow
            and (allow != ("genuine",) or not r["result"]["reasons"])
        ):
            used.add(g)
            return g, s
    raise RuntimeError("no clean pack found among the candidates")


def main() -> int:

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

    used: set[str] = set()
    g1, s1 = clean(sold["shop-delhi"], used)
    out.setdefault("S1", {"gtin": g1, "serial": s1, "raw": element(g1, s1)})
    out.setdefault(
        "S9", {"gtin": g1, "serial": s1, "raw": element(g1, swap_and_letter(s1)), "true_serial": s1}
    )

    gtin = p["tarang"].call("GET", "/api/products")["products"][0]["gtin"]
    s2 = make_serial("TP")  # a valid check character, but never issued
    out.setdefault("S2", {"gtin": gtin, "serial": s2, "raw": element(gtin, s2)})

    if "S3" not in out:  # sold in Delhi, then a copy of its code is sold in Mumbai
        g3, s3 = clean(sold["shop-delhi"], used)
        force_and_sell(p["shop-mumbai"], "dist-west", "DSP-FORGED-1", (g3, s3), 900)
        out["S3"] = {"gtin": g3, "serial": s3, "raw": element(g3, s3), "complaint_city": "Mumbai"}

    if "S4" not in out:  # a recalled medivra batch
        mv = clean([c for codes in sold.values() for c in codes if c[1].startswith("MV")], used)
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
        g7, s7 = clean(state["stock"]["dist-north"], used)
        force_and_sell(p["shop-bengaluru"], "dist-north", "DSP-GHOST-1", (g7, s7), 930)
        out["S7"] = {"gtin": g7, "serial": s7, "raw": element(g7, s7)}

    g8, s8 = clean(sold["shop-mumbai"], set())  # received from dist-west, so dist-west is on its route
    out.setdefault("S8", {"gtin": g8, "serial": s8, "raw": element(g8, s8)})

    planted.write_text(json.dumps(out, indent=1))
    print("planted:", ", ".join(sorted(out)))
    return 0


def plant_text() -> None:
    """The text-only scenarios: S3's complaint, S5 (a regulator notice with no structured alert), S6 (a cold chain report)."""
    out = json.loads((OUT / "scenarios.json").read_text())
    state = json.loads((OUT / "seed_state.json").read_text())
    password = json.loads((OUT / "secrets.json").read_text())["staff_password"]
    ports = {
        "regulator": 8401,
        "dist-north": 8101,
        "dist-west": 8102,
        "dist-south": 8103,
        "kesar": 8303,
        "tarang": 8301,
        "medivra": 8302,
    }
    p = {k: Portal(k, f"http://127.0.0.1:{v}", password) for k, v in ports.items()}
    used = {tuple(out[k]["raw"].split(")")[1::2]) for k in out}  # noqa: F841
    kesar = [tuple(c) for b in state["bills"] for c in b["codes"] if c[1].startswith("KS")]
    brand = {x["gtin"]: x for x in p["kesar"].call("GET", "/api/products")["products"]}
    at_text = "2026-11-18T10:00:00+05:30"

    makers = {"TP": "tarang", "MV": "medivra", "KS": "kesar"}
    names = {"tarang": "Tarang Pharma", "medivra": "Medivra Labs", "kesar": "Kesar Biologics"}
    sold_all = [tuple(c) for b in state["bills"] for c in b["codes"]]

    if (
        "S5" not in out
    ):  # an official notice that exists only as text, for a batch with nothing else against it
        g, s = clean(
            sold_all, {v["gtin"] for v in out.values()}, allow=("genuine", "caution")
        )  # not a product another scenario uses
        maker = makers[s[:2]]
        lot = p[maker].call("GET", f"/api/unit/{g}/{s}")["lot"]
        generic = next(
            x["generic"] for x in p[maker].call("GET", "/api/products")["products"] if x["gtin"] == g
        )
        text = f"Drugs declared not of standard quality, November 2026.\n1. {generic.title()} | B.No. {lot} | Mfd by {names[maker]} | Dissolution failed"
        r = p["regulator"].call(
            "POST", "/api/documents", json={"text": text, "declared_type": "nsq_alert", "at": at_text}
        )
        out["S5"] = {"gtin": g, "serial": s, "raw": element(g, s), "lot": lot, "doc_id": r["doc_id"]}

    if "S6" not in out:  # a temperature report for the shipment that carried a cold-chain (insulin) pack
        blocked = {"RECALLED", "QUALITY_FAILED", "COPIED_CODE", "NOT_ISSUED"}
        for g, s in (c for c in kesar if brand[c[0]]["generic"] == "insulin glargine"):
            reply = httpx.post(
                "http://127.0.0.1:8402/api/check", json={"raw": element(g, s), "city": "Delhi"}, timeout=300
            ).json()
            if reply["status"] == "done" and not blocked & {x["code"] for x in reply["result"]["reasons"]}:
                break
        else:
            raise RuntimeError("no cold-chain pack without a stronger problem")
        view = p["kesar"].call("GET", f"/api/unit/{g}/{s}")
        dist = next(e["to_org"] for e in view["events"] if e["event_type"] == "ship")
        ship = next(
            e for e in p[dist].call("GET", f"/api/unit/{g}/{s}")["events"] if e["event_type"] == "ship"
        )
        text = (
            f"Shipment {ship['ref']} ({dist} to {ship['to_org']}). Logger TL-22.\n12/10 09:10  6.1 C\n12/10 11:40  13.8 C\n12/10 14:30  14.2 C\n"
            "Reefer unit failed near Panipat. Temperature above 8 C for about 3 h 20 min. Cartons delivered."
        )
        r = p[dist].call("POST", "/api/documents", json={"text": text, "at": at_text})
        out["S6"] = {
            "gtin": g,
            "serial": s,
            "raw": element(g, s),
            "shipment": ship["ref"],
            "doc_id": r["doc_id"],
        }

    if "complaint" not in out["S3"]:  # a customer in a third city says they bought the same code
        s3 = out["S3"]
        maker = {"TP": "tarang", "MV": "medivra", "KS": "kesar"}[s3["serial"][:2]]
        name = next(
            x["brand"] for x in p[maker].call("GET", "/api/products")["products"] if x["gtin"] == s3["gtin"]
        )
        text = f"Maine 3 Nov ko Namma Pharmacy Bengaluru se {name} liya. Code {s3['serial'][:4]}-{s3['serial'][4:8]}-{s3['serial'][8:]}. Packing alag hai aur dawai se koi fayda nahi hua."
        r = httpx.post(
            "http://127.0.0.1:8403/api/report",
            json={"text": text, "city": "Mumbai", "at": at_text},
            timeout=60,
        )
        out["S3"]["complaint"] = r.json()["doc_id"]
    (OUT / "scenarios.json").write_text(json.dumps(out, indent=1))
    print("text scenarios planted: S3 complaint, S5, S6")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--simulation", action="store_true", required=True)
    ap.add_argument(
        "--text", action="store_true", help="plant the text scenarios (after the corpus is posted)"
    )
    args = ap.parse_args()
    sys.exit(plant_text() or 0 if args.text else main())
