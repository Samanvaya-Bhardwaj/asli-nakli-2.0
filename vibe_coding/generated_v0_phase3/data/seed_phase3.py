#!/usr/bin/env python3
"""
seed_phase3.py
--------------
Fills the Phase 3 tables of all four silos, deterministically, from the rows the
Phase 1 seeds and the Phase 2 generator already wrote. Every relationship is
derived from data that is really there, so the joins it enables tell the truth:

  DB3  molecules            one per distinct products.generic_name
       manufacturing_sites  one or two licensed plants per manufacturer
       production_records   the run behind every registered batch
       batch_release_certs  the QC release certificate for that run (was empty)
  DB2  warehouses           every location named on a dispatch note, per distributor
       cold_chain_loggers   one per shipment that had to stay in a temperature band
       temperature_logs     the readings; excursions exactly where DB2 recorded a breach
  DB1  pos_terminals        every till / camera that appears in a checkout scan
       retail_medicines     the pharmacy item master (genuine items received or sold)
       stock_receipts       goods received notes, one per DB2 delivery to a pharmacy
       inventory            stock on hand = received - sold, per pharmacy and item
  DB4  regulatory_authorities  every body officers belong to or alerts are issued by
       recall_notices          one per recall, tied to its complaint, lab report, alert

Seeding reads other silos only here, offline, the same way the Phase 2 generator
does: it is how the demo data is manufactured, not how the running system works.
Existing rows and columns are never modified. Run it again to regenerate the
Phase 3 tables (their previous contents are replaced).

    python data/seed_phase3.py
"""

from __future__ import annotations
import hashlib
import math
import os
import random
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from integration.uncertainty import paths                                    # noqa: E402
from integration.uncertainty.standardize import normalize_vendor_id, to_date  # noqa: E402

SEED = 2026_03
STOCK_TAKE_DATE = "2026-10-31"


# -- helpers ------------------------------------------------------------------

def _conn(db_id: str) -> sqlite3.Connection:
    c = sqlite3.connect(paths.db_path(db_id))
    c.row_factory = sqlite3.Row
    return c


def _h(*parts) -> int:
    """Stable small hash, so a row's derived values do not depend on run order."""
    return int(hashlib.sha1("|".join(map(str, parts)).encode("utf-8")).hexdigest()[:8], 16)


def _d(raw) -> Optional[date]:
    v = to_date(raw)
    return v.date() if v else None


def _iso(d) -> Optional[str]:
    return d.isoformat() if d else None


def _num(code: str) -> str:
    m = re.search(r"(\d+)$", code or "")
    return m.group(1) if m else "000"


def schedule_class(category: Optional[str], controlled) -> str:
    """Drugs and Cosmetics Rules schedule, by therapeutic category (simplified)."""
    if str(controlled) in ("1", "True"):
        return "X"
    c = (category or "").strip().lower()
    if c == "antibiotic":
        return "H1"
    if c in ("analgesic", "antacid", "antihistamine", "supplement", "rehydration", "cough"):
        return "OTC"
    return "H"


def _products() -> Dict[str, sqlite3.Row]:
    c = _conn("db3")
    try:
        return {r["product_uid"]: r for r in c.execute("SELECT * FROM products")}
    finally:
        c.close()


def _shipments() -> List[sqlite3.Row]:
    c = _conn("db2")
    try:
        return list(c.execute("SELECT * FROM distribution_batches ORDER BY batch_id"))
    finally:
        c.close()


# -- DB3: manufacturer registry ------------------------------------------------

_STATES = {"Goa", "Gujarat", "Maharashtra", "Karnataka", "Telangana", "Delhi", "Himachal Pradesh",
           "Sikkim", "Madhya Pradesh", "Andhra Pradesh", "Tamil Nadu", "West Bengal", "Haryana"}
_CITY_STATE = {"Hyderabad": "Telangana", "Bengaluru": "Karnataka", "Mumbai": "Maharashtra",
               "Ahmedabad": "Gujarat", "New Delhi": "Delhi", "Pune": "Maharashtra", "Chennai": "Tamil Nadu",
               "Kolkata": "West Bengal", "Gurugram": "Haryana", "Goa": "Goa"}
_STATE_CODE = {"Goa": "GA", "Gujarat": "GJ", "Maharashtra": "MH", "Karnataka": "KA", "Telangana": "TS",
               "Delhi": "DL", "Himachal Pradesh": "HP", "Sikkim": "SK", "Madhya Pradesh": "MP",
               "Andhra Pradesh": "AP", "Tamil Nadu": "TN", "West Bengal": "WB", "Haryana": "HR"}
# Formulation hubs a second plant is placed in
_HUBS = [("Baddi", "Himachal Pradesh"), ("Rangpo", "Sikkim"), ("Pithampur", "Madhya Pradesh"),
         ("Visakhapatnam", "Andhra Pradesh"), ("Dahej", "Gujarat"), ("Aurangabad", "Maharashtra")]
_QC_OFFICERS = ["Dr. Meera Iyer", "Dr. Arjun Nair", "Dr. Kavita Rao", "Dr. Sameer Kulkarni",
                "Dr. Nisha Varghese", "Dr. Rohit Bansal"]


def _site_location(address: Optional[str]):
    parts = [p.strip() for p in (address or "").split(",") if p.strip()]
    if len(parts) >= 2:
        locality, region = parts[0], parts[-1]
        if region in _STATES:
            return locality, region
        return region, _CITY_STATE.get(region)
    if parts:
        return parts[0], _CITY_STATE.get(parts[0])
    return None, None


def seed_db3() -> Dict[str, int]:
    products = _products()
    first_dispatch: Dict[str, date] = {}
    for b in _shipments():
        d = _d(b["dispatch_date"])
        if d and (b["batch_serial"] not in first_dispatch or d < first_dispatch[b["batch_serial"]]):
            first_dispatch[b["batch_serial"]] = d

    c = _conn("db3")
    try:
        for t in ("batch_release_certs", "production_records", "manufacturing_sites", "molecules"):
            c.execute(f"DELETE FROM {t}")

        # molecules: one per generic name actually used in the catalogue
        by_generic = defaultdict(list)
        for p in products.values():
            if p["generic_name"]:
                by_generic[p["generic_name"]].append(p)
        for i, (generic, rows) in enumerate(sorted(by_generic.items()), start=1):
            atc = Counter(r["atc_code"] for r in rows if r["atc_code"]).most_common(1)
            cat = Counter(r["category"] for r in rows if r["category"]).most_common(1)
            c.execute("INSERT INTO molecules VALUES (?,?,?,?,?,?,?)", (
                f"MOL-{i:03d}", generic, atc[0][0] if atc else None, cat[0][0] if cat else None,
                schedule_class(cat[0][0] if cat else None, max(int(r["controlled_substance"] or 0) for r in rows)),
                1 if any(int(r["requires_cold_chain"] or 0) for r in rows) else 0, "registered"))

        # manufacturing sites: the registered address is plant I, a formulation hub plant II
        sites_by_mfg = defaultdict(list)
        mfgs = list(c.execute("SELECT * FROM manufacturers ORDER BY manufacturer_id"))
        for k, m in enumerate(mfgs):
            num = _num(m["manufacturer_id"])
            city, state = _site_location(m["physical_address"])
            hub_city, hub_state = _HUBS[k % len(_HUBS)]
            gmp = "compliant" if int(m["gmp_certified"] or 0) else "under_review"
            plants = [(city or "Head plant", state, "Unit I"), (hub_city, hub_state, "Unit II")]
            for j, (pc, ps, unit) in enumerate(plants, start=1):
                site_id = f"SITE-{num}-{j}"
                inspected = date(2025, 1 + _h(site_id) % 12, 1 + _h(site_id, "d") % 27)
                c.execute("INSERT INTO manufacturing_sites VALUES (?,?,?,?,?,?,?,?)", (
                    site_id, m["manufacturer_id"], f"{m['company_name']} - {pc} {unit}", pc, ps,
                    f"{_STATE_CODE.get(ps, 'IN')}/DRUGS/MFG/{num}/{j}", gmp, inspected.isoformat()))
                sites_by_mfg[m["manufacturer_id"]].append(site_id)

        # production runs and QC release certificates, one per registered batch
        n_prod = n_cert = 0
        for i, uid in enumerate(sorted(products), start=1):
            p = products[uid]
            sites = sites_by_mfg.get(p["manufacturer_id"])
            if not sites:
                continue
            h = _h(uid)
            site = sites[0] if h % 10 < 7 else sites[-1]
            mfd = _d(p["manufacture_date"])
            started = mfd - timedelta(days=4 + h % 10) if mfd else None
            liquid = str(p["dosage_form"] or "").lower() in ("syrup", "injection", "suspension", "vaccine", "drops")
            size = (5_000 + h % 25_000) if liquid else (50_000 + (h % 150) * 1_000)
            generic = (p["generic_name"] or "GEN").upper().replace(" ", "")[:3]
            prod_id = f"PRD-{i:05d}"
            c.execute("INSERT INTO production_records VALUES (?,?,?,?,?,?,?,?,?,?)", (
                prod_id, uid, site, p["batch_number"], f"L{1 + h % 6}", _iso(started), _iso(mfd), size,
                round(95.0 + (h % 47) / 10, 1), f"API-{generic}-{mfd:%y%m}-{100 + h % 900}" if mfd else None))
            n_prod += 1

            # released 1-3 days after the run, and never after the first shipment left
            release = mfd + timedelta(days=1 + h % 3) if mfd else None
            first = first_dispatch.get(uid)
            if release and first and first < release:
                release = max(mfd, first)
            params = ["Assay (HPLC)", "Dissolution", "Related substances", "Microbial limits"]
            if liquid or str(p["category"]).lower() in ("vaccine", "biologic"):
                params += ["Sterility", "Bacterial endotoxins"]
            if int(p["requires_cold_chain"] or 0):
                params.append("Stability at 2-8 C")
            fields = (f"COA-{i:05d}", uid, p["batch_number"], 1,
                      _iso(release) or str(p["manufacture_date"]), _QC_OFFICERS[h % len(_QC_OFFICERS)],
                      "; ".join(params))
            digest = hashlib.sha256("|".join(map(str, fields)).encode("utf-8")).hexdigest()
            c.execute("INSERT INTO batch_release_certs VALUES (?,?,?,?,?,?,?,?)", fields + (digest,))
            n_cert += 1
        c.commit()
        return {"molecules": len(by_generic), "manufacturing_sites": sum(map(len, sites_by_mfg.values())),
                "production_records": n_prod, "batch_release_certs": n_cert}
    finally:
        c.close()


# -- DB2: distributor ERP --------------------------------------------------------

_JUNK_LOCATIONS = {"", "?", "unknown", "unregistered godown"}
_CITY_FIX = {"Delhi NCR": "New Delhi"}


def _warehouse_city(name: str) -> Optional[str]:
    if name.strip().lower() in _JUNK_LOCATIONS:
        return None
    city = re.sub(r"\s+(Central\s+)?(DC|Hub|Depot)$", "", name.strip(), flags=re.I).strip()
    return _CITY_FIX.get(city, city) or None


def seed_db2() -> Dict[str, int]:
    products = _products()
    rng = random.Random(SEED + 2)
    c = _conn("db2")
    try:
        for t in ("temperature_logs", "cold_chain_loggers", "warehouses"):
            c.execute(f"DELETE FROM {t}")
        dists = {r["distributor_id"]: r for r in c.execute("SELECT * FROM distributors")}
        batches = list(c.execute("SELECT * FROM distribution_batches ORDER BY batch_id"))

        # warehouses
        pairs = sorted({(b["distributor_id"], b["source_warehouse"]) for b in batches
                        if b["source_warehouse"] is not None})
        per_dist = Counter()
        for dist_id, name in pairs:
            per_dist[dist_id] += 1
            k = per_dist[dist_id]
            d = dists.get(dist_id)
            registered = name.strip().lower() not in _JUNK_LOCATIONS
            cold = 1 if (registered and d is not None and int(d["cold_chain_capable"] or 0)) else 0
            c.execute("INSERT INTO warehouses VALUES (?,?,?,?,?,?,?,?)", (
                f"WH-{_num(dist_id)}-{k:02d}", dist_id, name, _warehouse_city(name),
                f"{d['license_no']}/WH-{k:02d}" if (registered and d is not None) else None,
                cold, float(500 + _h(dist_id, name) % 3500) if cold else None,
                "registered" if registered else "unregistered"))

        # cold-chain loggers and readings
        n_log = n_read = n_exc = 0
        for b in batches:
            p = products.get(b["batch_serial"])
            needs = p is not None and int(p["requires_cold_chain"] or 0) == 1
            breach = b["cold_chain_maintained"] == 0
            if not (needs or breach):
                continue
            if p is not None and p["storage_temp_min"] is not None and p["storage_temp_max"] is not None \
                    and float(p["storage_temp_min"]) < float(p["storage_temp_max"]):
                lo, hi = float(p["storage_temp_min"]), float(p["storage_temp_max"])
            elif needs or (dists.get(b["distributor_id"]) and int(dists[b["distributor_id"]]["cold_chain_capable"] or 0)):
                lo, hi = 2.0, 8.0
            else:
                lo, hi = 15.0, 25.0
            profile = "frozen" if hi <= 0 else ("refrigerated_2_8C" if hi <= 8 else "ambient_controlled")

            start = _d(b["dispatch_date"])
            end = _d(b["actual_arrival_date"]) or _d(b["expected_arrival_date"])
            if start and (not end or end <= start):
                end = start + timedelta(days=2)
            n_log += 1
            logger_id = f"LOG-{n_log:05d}"
            c.execute("INSERT INTO cold_chain_loggers VALUES (?,?,?,?,?,?,?,?)", (
                logger_id, b["batch_id"], f"LG{10000 + _h(b['batch_id']) % 90000}", profile, lo, hi,
                f"{start} 06:00:00" if start else None, f"{end} 18:00:00" if end else None))
            if not start:
                continue

            t0 = datetime.combine(start, datetime.min.time()) + timedelta(hours=6)
            t1 = datetime.combine(end, datetime.min.time()) + timedelta(hours=18)
            n = max(3, min(24, math.ceil((t1 - t0).total_seconds() / 21600) + 1))
            step = (t1 - t0) / (n - 1)
            mid, half = (lo + hi) / 2, (hi - lo) / 2
            temps = [round(mid + rng.uniform(-0.6, 0.6) * half, 1) for _ in range(n)]
            if breach:   # an excursion window exactly where DB2 says the cold chain broke
                k = rng.randint(1, n - 2)
                for j in range(k, min(n - 1, k + rng.randint(2, 4))):
                    temps[j] = round(hi + rng.uniform(2.5, 9.0), 1)
            for j, temp in enumerate(temps):
                exc = 1 if (temp < lo or temp > hi) else 0
                where = "warehouse" if j == 0 else ("delivery" if j == n - 1 else "in_transit")
                c.execute("INSERT INTO temperature_logs VALUES (?,?,?,?,?,?)", (
                    f"TR-{n_log:05d}-{j + 1:02d}", logger_id, (t0 + step * j).strftime("%Y-%m-%d %H:%M:%S"),
                    temp, where, exc))
                n_read += 1
                n_exc += exc
        c.commit()
        return {"warehouses": len(pairs), "cold_chain_loggers": n_log, "temperature_logs": n_read,
                "excursion_readings": n_exc}
    finally:
        c.close()


# -- DB1: retail POS -----------------------------------------------------------------

_SCANNER = {"barcode": "laser", "qrcode": "imager_2d", "ocr": "camera", "nfc": "nfc", "manual": "keyboard"}
_MODEL = {"laser": "CounterScan CS-200", "imager_2d": "CounterScan CS-300 2D",
          "camera": "LabelCam LC-2", "nfc": "TapReader TR-1", "keyboard": "Manual entry console"}


def seed_db1() -> Dict[str, int]:
    products = _products()
    c = _conn("db1")
    try:
        for t in ("inventory", "stock_receipts", "retail_medicines", "pos_terminals"):
            c.execute(f"DELETE FROM {t}")
        vendors = {r["vendor_id"]: r for r in c.execute("SELECT * FROM vendors")}
        events = list(c.execute("SELECT * FROM purchase_events ORDER BY scan_timestamp, event_id"))

        def vendor_of(raw):
            return normalize_vendor_id(raw, vendors.keys())

        # pos_terminals: every device that made a scan
        by_device = defaultdict(list)
        for e in events:
            if e["device_id"]:
                by_device[e["device_id"]].append(e)
        for dev, evs in sorted(by_device.items()):
            m = re.match(r"^POS-(\d+)", dev)
            vendor = f"VND-{int(m.group(1)):03d}" if m and f"VND-{int(m.group(1)):03d}" in vendors else None
            if vendor is None:
                common = Counter(v for v in (vendor_of(e["vendor_id"]) for e in evs) if v).most_common(1)
                vendor = common[0][0] if common else None
            method = Counter(e["scan_method"] or "barcode" for e in evs).most_common(1)[0][0]
            scanner = _SCANNER.get(method, "laser")
            first_scan = min((_d(e["scan_timestamp"]) for e in evs if _d(e["scan_timestamp"])), default=None)
            installed = first_scan - timedelta(days=30 + _h(dev) % 300) if first_scan else None
            c.execute("INSERT INTO pos_terminals VALUES (?,?,?,?,?,?,?)", (
                dev, vendor, _MODEL[scanner], scanner, "v4.1.2-pos", _iso(installed), "registered"))

        # stock receipts: DB2 deliveries of registered medicines to pharmacies of this network
        receipts = []
        for b in _shipments():
            vendor = vendor_of(b["destination_vendor_id"])
            if b["status"] != "delivered" or vendor is None or b["batch_serial"] not in products:
                continue
            got = _d(b["actual_arrival_date"]) or _d(b["expected_arrival_date"]) or _d(b["dispatch_date"])
            if got is None:
                continue
            qty = b["quantity_received"] if b["quantity_received"] is not None else b["quantity_shipped"]
            receipts.append((vendor, b["batch_serial"], b["distributor_id"], b["batch_id"], got, int(qty)))
        receipts.sort(key=lambda r: (r[0], r[4], r[3]))

        sold = Counter()
        first_sale = {}
        for e in events:
            v = vendor_of(e["vendor_id"])
            if v and e["scan_code"] in products:
                sold[(v, e["scan_code"])] += int(e["quantity_bought"] or 1)
            d = _d(e["scan_timestamp"])
            if e["scan_code"] in products and d and (e["scan_code"] not in first_sale or d < first_sale[e["scan_code"]]):
                first_sale[e["scan_code"]] = d

        # retail item master: every registered medicine received or sold here
        items = sorted({r[1] for r in receipts} | {code for (_v, code) in sold})
        first_receipt = {}
        for r in receipts:
            first_receipt.setdefault(r[1], r[4])
        for code in items:
            p = products[code]
            added = min(d for d in (first_receipt.get(code), first_sale.get(code)) if d) \
                if (first_receipt.get(code) or first_sale.get(code)) else None
            c.execute("INSERT INTO retail_medicines VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                code, p["product_name"], p["generic_name"], p["strength"], p["pack_size"], p["batch_number"],
                p["expiry_date"], p["msrp_kes"], schedule_class(p["category"], p["controlled_substance"]),
                p["manufacturer_id"], _iso(added)))

        seq = Counter()
        last_receipt = {}
        received = Counter()
        for vendor, code, dist, dispatch_ref, got, qty in receipts:
            seq[vendor] += 1
            rid = f"GRN-{_num(vendor)}-{seq[vendor]:04d}"
            c.execute("INSERT INTO stock_receipts VALUES (?,?,?,?,?,?,?,?)", (
                rid, vendor, code, dist, dispatch_ref, f"INV/{dist}/{dispatch_ref}", got.isoformat(), qty))
            received[(vendor, code)] += qty
            last_receipt[(vendor, code)] = rid

        for k, (vendor, code) in enumerate(sorted(received), start=1):
            qty_in = received[(vendor, code)]
            h = _h(vendor, code)
            c.execute("INSERT INTO inventory VALUES (?,?,?,?,?,?,?,?)", (
                f"INV-{_num(vendor)}-{k:04d}", vendor, code, max(0, qty_in - sold[(vendor, code)]),
                max(5, round(qty_in * 0.1)), f"{'ABCDEF'[h % 6]}-{1 + h % 20:02d}",
                last_receipt[(vendor, code)], STOCK_TAKE_DATE))
        c.commit()
        return {"pos_terminals": len(by_device), "retail_medicines": len(items),
                "stock_receipts": len(receipts), "inventory": len(received)}
    finally:
        c.close()


# -- DB4: ministry ---------------------------------------------------------------------

# (id, name, short, type, jurisdiction, parent)
AUTHORITIES = [
    ("AUTH-MOHFW", "Ministry of Health and Family Welfare", "MoHFW", "ministry", "India", None),
    ("AUTH-MOCA", "Ministry of Consumer Affairs", "MoCA", "ministry", "India", None),
    ("AUTH-CDSCO", "Central Drugs Standard Control Organisation", "CDSCO", "drug_regulator", "India", "AUTH-MOHFW"),
    ("AUTH-CDSCO-INSP", "CDSCO Inspectorate", "CDSCO-I", "drug_regulator", "India", "AUTH-CDSCO"),
    ("AUTH-CDL-KOL", "Central Drug Laboratory Kolkata", "CDL", "laboratory", "India", "AUTH-CDSCO"),
    ("AUTH-CCPA", "Central Consumer Protection Authority", "CCPA", "consumer_protection", "India", "AUTH-MOCA"),
    ("AUTH-NCDRC", "National Consumer Commission", "NCDRC", "quasi_judicial", "India", "AUTH-MOCA"),
    ("AUTH-NCH", "National Consumer Helpline", "NCH", "helpline", "India", "AUTH-MOCA"),
]


def _recall_class(reason: str) -> str:
    r = (reason or "").lower()
    if any(w in r for w in ("glycol", "toxic", "fatal", "above permissible")):
        return "I"
    if any(w in r for w in ("microbial", "contamination", "sub-potent", "dissolution")):
        return "II"
    return "III"


def seed_db4() -> Dict[str, int]:
    recalled = sorted((p for p in _products().values() if int(p["is_recalled"] or 0)),
                      key=lambda p: p["product_uid"])
    c = _conn("db4")
    try:
        for t in ("recall_notices", "regulatory_authorities"):
            c.execute(f"DELETE FROM {t}")
        for row in AUTHORITIES:
            c.execute("INSERT INTO regulatory_authorities VALUES (?,?,?,?,?,?,?)", row + ("registered",))
        known = {a[1] for a in AUTHORITIES}
        used = {r[0] for r in c.execute("SELECT department FROM ministry_officers")} | \
               {r[0] for r in c.execute("SELECT issued_by FROM public_alerts WHERE issued_by IS NOT NULL")}
        for k, name in enumerate(sorted(used - known), start=1):   # names on file but not in the list
            c.execute("INSERT INTO regulatory_authorities VALUES (?,?,?,?,?,?,?)",
                      (f"AUTH-X{k:02d}", name, None, None, "India", None, "registered"))
        auth_by_name = {r["authority_name"]: r["authority_id"] for r in c.execute("SELECT * FROM regulatory_authorities")}
        officer_by_dept = {}
        for o in c.execute("SELECT * FROM ministry_officers WHERE active = 1 ORDER BY officer_id"):
            officer_by_dept.setdefault(o["department"], o["officer_id"])

        n = 0
        for p in recalled:
            uid = p["product_uid"]
            authority = auth_by_name.get(p["recall_authority"] or "", "AUTH-CDSCO")
            officer = officer_by_dept.get("CDSCO Inspectorate")
            complaint = c.execute("SELECT complaint_id FROM complaints WHERE complaint_item_ref = ? "
                                  "ORDER BY complaint_date LIMIT 1", (uid,)).fetchone()
            lab = c.execute("SELECT lab_report_id FROM lab_reports WHERE item_ref = ? "
                            "ORDER BY (result = 'fail') DESC, test_completed_on LIMIT 1", (uid,)).fetchone()
            alert = c.execute("SELECT alert_id FROM public_alerts WHERE item_ref = ? ORDER BY issued_on LIMIT 1",
                              (uid,)).fetchone()
            issued = _d(p["recall_date"])
            n += 1
            c.execute("INSERT INTO recall_notices VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                f"RCL-{issued.year if issued else 2026}-{n:03d}", authority, officer, uid, p["batch_number"],
                p["manufacturer_id"], _recall_class(p["recall_reason"]),
                p["recall_reason"] or "Recall ordered by the drug regulator", _iso(issued) or str(p["recall_date"]),
                "active", complaint[0] if complaint else None, lab[0] if lab else None, alert[0] if alert else None))
        c.commit()
        return {"regulatory_authorities": len(auth_by_name), "recall_notices": n}
    finally:
        c.close()


def main() -> Dict[str, Dict[str, int]]:
    out = {}
    for db_id, fn in (("db3", seed_db3), ("db2", seed_db2), ("db1", seed_db1), ("db4", seed_db4)):
        out[db_id] = fn()
        print(f"  {db_id}: " + ", ".join(f"{k} {v}" for k, v in out[db_id].items()))
    return out


if __name__ == "__main__":
    print("Seeding Phase 3 tables")
    main()
