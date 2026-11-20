#!/usr/bin/env python3
"""
generate_documents.py
---------------------
Builds the Phase 3 unstructured corpus: realistic documents written by the
organisations behind each source, stored as FILES with the source that owns them
(never in a database table):

  data/documents/db1/  pharmacy incident reports                         (retail chain)
  data/documents/db2/  shipment notes, cold-chain incident reports        (distributors)
  data/documents/db3/  manufacturer quality reports, batch inspection
                       reports, product safety documents                  (manufacturers)
  data/documents/db4/  recall notices (HTML), regulatory investigation
                       reports, consumer complaint letters, NSQ bulletins (ministry)

Each document has a small header (doc_id, title, type, source, date - in the
writer's own date format) and free text. Medicine codes, batch numbers and
company ids appear only in the prose, as people write them: sometimes exact,
sometimes damaged ('MED-ASAL1-OO9', 'med asali 009'), brand names sometimes
misspelt. Documents about sibling batches (one character apart) and generic
documents that share only common words are included on purpose: retrieval has to
tell them apart.

Documents are derived deterministically from the structured records (read here,
offline, like the Phase 2 generator), so the identifiers they mention are real.
data/documents/ground_truth.json records which entities each document is truly
about - for evaluation only; search never reads it.

    python data/generate_documents.py
"""

from __future__ import annotations
import html
import json
import os
import random
import shutil
import sqlite3
import sys
from collections import defaultdict
from datetime import date, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from integration.uncertainty import noise, paths                     # noqa: E402
from integration.uncertainty.standardize import canonical_code, to_date  # noqa: E402

OUT = os.environ.get("ASALI_DOCS_ROOT") or os.path.join(BASE, "data", "documents")
SEED = 2026_04
GT = {}


def rows(db, sql, params=()):
    c = sqlite3.connect(f"file:{paths.db_path(db)}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute(sql, params)]
    finally:
        c.close()


def d_of(raw):
    v = to_date(raw)
    return v.date() if v else None


def say_date(d: date, rng: random.Random) -> str:
    """Each writer has their own habit."""
    return rng.choice([d.isoformat(), d.strftime("%d/%m/%Y"), d.strftime("%B %d, %Y"), d.strftime("%d %b %Y")])


def typed(code: str, rng: random.Random, p_noise: float) -> str:
    """A code as a person types or a camera reads it."""
    if rng.random() >= p_noise:
        return code
    kind = rng.choice(["ocr", "fmt", "ocr"])
    out = noise.ocr(code, rng) if kind == "ocr" else noise.fmt(code, rng)
    return out if out.strip() else code


def misspell(name: str, rng: random.Random) -> str:
    if len(name) < 6 or rng.random() > 0.3:
        return name
    i = rng.randrange(1, len(name) - 2)
    return name[:i] + name[i + 1] + name[i] + name[i + 2:]


def write(owner: str, doc_id: str, title: str, dtype: str, source: str, when: str, body: str,
          truth: dict, fmt: str = "md"):
    folder = os.path.join(OUT, owner)
    os.makedirs(folder, exist_ok=True)
    if fmt == "html":
        paras = "".join(f"<p>{html.escape(p)}</p>\n" for p in body.split("\n\n") if p.strip())
        text = (f"<!doctype html>\n<html><head><meta charset='utf-8'><title>{html.escape(title)}</title>\n"
                f"<meta name='doc_id' content='{doc_id}'><meta name='type' content='{dtype}'>\n"
                f"<meta name='source' content='{html.escape(source)}'><meta name='date' content='{when}'>\n"
                f"</head><body><h1>{html.escape(title)}</h1>\n{paras}</body></html>\n")
        path = os.path.join(folder, f"{doc_id}.html")
    else:
        text = f"---\ndoc_id: {doc_id}\ntitle: {title}\ntype: {dtype}\nsource: {source}\ndate: {when}\n---\n\n{body}\n"
        path = os.path.join(folder, f"{doc_id}.{fmt}")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    GT[doc_id] = {"owner": owner, "type": dtype, "title": title, **{k: sorted(set(v)) for k, v in truth.items()}}


def truth(item_codes=(), batch_numbers=(), manufacturer_ids=(), distributor_ids=(), vendor_ids=()):
    # ground truth names each medicine in its tidy form, whatever the source row stored
    return {"item_codes": [canonical_code(c) for c in item_codes if c], "batch_numbers": list(batch_numbers),
            "manufacturer_ids": list(manufacturer_ids), "distributor_ids": list(distributor_ids),
            "vendor_ids": list(vendor_ids)}


# -- the structured facts the documents talk about -------------------------------------------

def load():
    products = {p["product_uid"]: p for p in rows("db3", "SELECT * FROM products")}
    mfgs = {m["manufacturer_id"]: m for m in rows("db3", "SELECT * FROM manufacturers")}
    sites = defaultdict(list)
    for s in rows("db3", "SELECT * FROM manufacturing_sites ORDER BY site_id"):
        sites[s["manufacturer_id"]].append(s)
    prod_rec = {r["product_uid"]: r for r in rows("db3", "SELECT * FROM production_records")}
    certs = {r["product_uid"]: r for r in rows("db3", "SELECT * FROM batch_release_certs")}
    molecules = rows("db3", "SELECT * FROM molecules ORDER BY molecule_id")
    dists = {d["distributor_id"]: d for d in rows("db2", "SELECT * FROM distributors")}
    batches = rows("db2", "SELECT * FROM distribution_batches ORDER BY batch_id")
    loggers = {l["batch_id"]: l for l in rows("db2", "SELECT * FROM cold_chain_loggers")}
    readings = defaultdict(list)
    for t in rows("db2", "SELECT * FROM temperature_logs ORDER BY reading_id"):
        readings[t["logger_id"]].append(t)
    vendors = {v["vendor_id"]: v for v in rows("db1", "SELECT * FROM vendors")}
    events = rows("db1", "SELECT * FROM purchase_events ORDER BY event_id")
    complaints = rows("db4", "SELECT * FROM complaints ORDER BY complaint_id")
    blacklist = rows("db4", "SELECT * FROM ministry_blacklist ORDER BY blacklist_id")
    labs = {l["complaint_id"]: l for l in rows("db4", "SELECT * FROM lab_reports")}
    recalls = rows("db4", "SELECT * FROM recall_notices ORDER BY recall_id")
    officers = {o["officer_id"]: o for o in rows("db4", "SELECT * FROM ministry_officers")}
    return locals()


# -- DB3: manufacturers -------------------------------------------------------------------------

def gen_db3(D, rng):
    products, mfgs = D["products"], D["mfgs"]
    by_mfg = defaultdict(list)
    for p in products.values():
        by_mfg[p["manufacturer_id"]].append(p)
    n = 0
    # quarterly quality reports per manufacturer (H1 / H2 2025)
    for mid, m in sorted(mfgs.items()):
        for half, (d0, d1) in enumerate([(date(2025, 1, 1), date(2025, 6, 30)), (date(2025, 7, 1), date(2025, 12, 31))], 1):
            released = [p for p in by_mfg[mid] if d_of(p["manufacture_date"]) and d0 <= d_of(p["manufacture_date"]) <= d1]
            if not released:
                continue
            n += 1
            lines = [f"- {p['product_name']} ({p['generic_name']}), batch {p['batch_number']}, "
                     f"pack code {p['product_uid']}: released, assay within limits" for p in released[:14]]
            recalled = [p for p in by_mfg[mid] if p["is_recalled"]]
            deviation = ("\n\n## Deviations and investigations\n\n" + "\n".join(
                f"Batch {p['batch_number']} of {p['product_name']} ({p['product_uid']}) is the subject of a "
                f"regulatory recall: {p['recall_reason']}. A root-cause investigation into raw-material "
                f"suppliers is open and further release of this formulation is on hold." for p in recalled)
            ) if recalled and half == 1 else "\n\n## Deviations and investigations\n\nNo critical deviations were raised in the period."
            site_names = ", ".join(s["site_name"] for s in D["sites"][mid])
            body = (f"# {m['company_name']} - Product Quality Review, H{half} 2025\n\n"
                    f"## Scope\n\nThis review covers {len(released)} batch(es) released from {site_names} "
                    f"between {d0:%d %B %Y} and {d1:%d %B %Y}, under manufacturing licence {m['license_no']}.\n\n"
                    f"## Batches released\n\n" + "\n".join(lines) + deviation +
                    "\n\n## Conclusion\n\nThe quality unit confirms that released batches met their specifications "
                    "at the time of release. Stability commitments continue as planned.")
            write("db3", f"DOC-DB3-PQR-{n:03d}", f"{m['company_name']} product quality review H{half} 2025",
                  "manufacturer_quality_report", f"{m['company_name']} quality unit",
                  say_date(d1 + timedelta(days=20), rng), body,
                  truth([p["product_uid"] for p in released[:14]] + [p["product_uid"] for p in recalled if half == 1],
                        [p["batch_number"] for p in released[:14]], [mid]))
    # batch inspection reports: every curated item plus a sample of generated batches
    picks = sorted(u for u in products if not u.startswith("MED-") or u.split("-")[1] in
                   ("ASALI", "RECALL", "UNAUTH", "NAKALI"))
    picks += rng.sample(sorted(set(products) - set(picks)), 30)
    n = 0
    for uid in picks:
        p = products[uid]
        pr, cert = D["prod_rec"].get(uid), D["certs"].get(uid)
        site = next((s for s in D["sites"][p["manufacturer_id"]] if pr and s["site_id"] == pr["site_id"]), None)
        if p["is_recalled"]:
            finding = (f"Retained samples of batch {p['batch_number']} were re-tested after the recall. Finding: "
                       f"{p['recall_reason']}. The batch is quarantined and the deviation classified as critical.")
        elif p["requires_cold_chain"]:
            finding = (f"The product requires storage between {p['storage_temp_min']} and {p['storage_temp_max']} C. "
                       f"Cold-room mapping and packaging validation were reviewed and found adequate.")
        else:
            finding = "No observations. Line clearance, in-process checks and documentation were satisfactory."
        n += 1
        body = (f"# Batch inspection report\n\nProduct: {p['product_name']} ({p['generic_name']} {p['strength']})\n"
                f"Pack code on label: {p['product_uid']}\nBatch: {p['batch_number']}\n"
                f"Manufactured: {p['manufacture_date']}; expiry {p['expiry_date']}\n"
                f"Site: {site['site_name'] if site else 'not recorded'}\n\n"
                f"## Production\n\nLine {pr['production_line'] if pr else '-'}, batch size {pr['batch_size_units'] if pr else '-'} units, "
                f"yield {pr['yield_percent'] if pr else '-'} percent.\n\n"
                f"## Quality control\n\nCertificate {cert['cert_id'] if cert else '-'} signed by "
                f"{cert['qc_officer'] if cert else '-'}; tests: {cert['test_parameters'] if cert else '-'}.\n\n"
                f"## Inspection findings\n\n{finding}")
        write("db3", f"DOC-DB3-BIR-{n:03d}", f"Batch inspection report {p['batch_number']} ({p['product_name']})",
              "batch_inspection_report", f"{D['mfgs'][p['manufacturer_id']]['company_name']} QA inspection",
              say_date(d_of(p["manufacture_date"]) + timedelta(days=5), rng), body,
              truth([uid], [p["batch_number"]], [p["manufacturer_id"]]))
    # product safety documents per molecule (generic: these share words with everything)
    for i, mo in enumerate(D["molecules"], 1):
        brands = sorted({p["product_name"] for p in products.values() if p["generic_name"] == mo["generic_name"]})
        cold = "Store refrigerated between 2 and 8 C; do not freeze. Discard if exposed to heat." if mo["cold_chain_required"] \
            else "Store below 25 C in a dry place, protected from light."
        body = (f"# Product safety information: {mo['generic_name']}\n\nTherapeutic class: {mo['therapeutic_class']}; "
                f"ATC {mo['atc_code']}; schedule {mo['schedule_class']}.\n\nMarketed as: {', '.join(brands[:6])}.\n\n"
                f"## Storage\n\n{cold}\n\n## Safety\n\nReport suspected adverse reactions to the pharmacovigilance "
                f"programme. Check the pack's printed code and hologram; buy only from licensed pharmacies.")
        write("db3", f"DOC-DB3-PSI-{i:03d}", f"Product safety information - {mo['generic_name']}",
              "product_safety_document", "Marketing authorisation holders (registry library)",
              say_date(date(2025, 1, 15), rng), body, truth())


# -- DB2: distributors -------------------------------------------------------------------------

def gen_db2(D, rng):
    n_s = n_c = 0
    breaches = [b for b in D["batches"] if b["cold_chain_maintained"] == 0]
    normal = rng.sample([b for b in D["batches"] if b["cold_chain_maintained"] != 0], 40)
    for b in sorted(breaches + normal, key=lambda x: x["batch_id"]):
        dist = D["dists"].get(b["distributor_id"], {})
        p = D["products"].get(b["batch_serial"])
        lg = D["loggers"].get(b["batch_id"])
        reads = D["readings"].get(lg["logger_id"], []) if lg else []
        exc = [r for r in reads if r["excursion"]]
        temp = (f"Data logger {lg['logger_serial']} (band {lg['setpoint_min_c']}-{lg['setpoint_max_c']} C) recorded "
                f"{len(reads)} readings; {len(exc)} outside the band, peak {max(r['temperature_c'] for r in exc):.1f} C."
                if lg and exc else (f"Data logger {lg['logger_serial']} stayed within {lg['setpoint_min_c']}-"
                                    f"{lg['setpoint_max_c']} C for the whole journey." if lg else
                                    "No temperature logger was required for this consignment."))
        n_s += 1
        body = (f"Dispatch note {b['batch_id']}\n\nConsignment: {p['product_name'] if p else 'item'} pack code "
                f"{typed(b['batch_serial'], rng, 0.15)}, {b['quantity_shipped']} units, from {b['source_warehouse']} "
                f"to pharmacy {b['destination_vendor_id']} by {b['transport_mode']} ({b['vehicle_reg']}).\n\n"
                f"Dispatched {b['dispatch_date']}, received {b['actual_arrival_date'] or 'pending'}.\n\n{temp}\n\n"
                + (f"Discrepancy: {b['discrepancy_details']}." if b["discrepancy_details"] else "No discrepancy recorded."))
        write("db2", f"DOC-DB2-SHP-{n_s:03d}", f"Shipment note {b['batch_id']}", "distributor_shipment_note",
              f"{dist.get('company_name', b['distributor_id'])} ({b['distributor_id']}) dispatch desk",
              say_date(d_of(b["dispatch_date"]) or date(2025, 1, 1), rng), body,
              truth([b["batch_serial"]], [p["batch_number"]] if p else [], [b["manufacturer_ref"]],
                    [b["distributor_id"]], [b["destination_vendor_id"]]))
        if b in breaches and exc and p is not None:
            n_c += 1
            impact = (f"Temperature-sensitive product. The receiving pharmacy {b['destination_vendor_id']} was asked "
                      f"to quarantine the units pending a stability assessment by the manufacturer {b['manufacturer_ref']}."
                      if p["requires_cold_chain"] else
                      "The product is labelled for storage below 25-30 C; the excursion is not expected to affect "
                      "quality, but the consignment is held until the manufacturer confirms.")
            body = (f"# Cold-chain incident report\n\nConsignment {b['batch_id']} of {p['product_name']} "
                    f"(batch {p['batch_number']}, pack code {b['batch_serial']}) left the {lg['setpoint_min_c']}-"
                    f"{lg['setpoint_max_c']} C band for {len(exc)} logged interval(s); peak {max(r['temperature_c'] for r in exc):.1f} C.\n\n"
                    f"## Impact\n\n{impact}\n\n"
                    f"## Corrective action\n\nVehicle {b['vehicle_reg']} withdrawn from cold-chain duty; refrigeration unit to "
                    f"be serviced; driver retraining scheduled.")
            write("db2", f"DOC-DB2-CCI-{n_c:03d}", f"Cold-chain excursion: {b['batch_id']} ({p['product_name']})",
                  "cold_chain_incident_report", f"{dist.get('company_name', b['distributor_id'])} quality desk",
                  say_date(d_of(b["actual_arrival_date"]) or d_of(b["dispatch_date"]) or date(2025, 1, 1), rng), body,
                  truth([b["batch_serial"]], [p["batch_number"]], [b["manufacturer_ref"]], [b["distributor_id"]],
                        [b["destination_vendor_id"]]))


# -- DB1: pharmacies ---------------------------------------------------------------------------

def gen_db1(D, rng):
    products, vendors = D["products"], D["vendors"]
    unknown = [e for e in D["events"] if e["scan_code"] not in products and e["scan_code"].startswith("MED-")]
    flagged = [e for e in D["events"] if e["anomaly_flag"]]
    picks = flagged + rng.sample(unknown, min(28, len(unknown)))
    n = 0
    for e in sorted(picks, key=lambda x: x["event_id"]):
        v = vendors.get(e["vendor_id"], {})
        p = products.get(e["scan_code"])
        if p is None:
            what = (f"A customer returned a strip sold under code {typed(e['scan_code'], rng, 0.3)}. The code is not "
                    f"recognised by our verification app; the foil print is blurred and the hologram is missing. "
                    f"Price paid was Rs {e['price_paid']}.")
        else:
            what = (f"The till flagged the sale of {misspell(p['product_name'], rng)} code {typed(e['scan_code'], rng, 0.3)} "
                    f"({e['anomaly_reason'] or 'unusual pattern'}). Staff checked the pack: seal intact, batch "
                    f"{p['batch_number']} printed clearly.")
        n += 1
        body = (f"Pharmacy incident report\n\nPharmacy: {v.get('vendor_name', e['vendor_id'])} ({e['vendor_id']}), "
                f"{v.get('location_county', '')}\nTerminal: {e['device_id']}\nSale reference: {e['event_id']}\n\n"
                f"{what}\n\nAction: pack set aside, customer offered a replacement, incident forwarded to the "
                f"regional quality manager.")
        write("db1", f"DOC-DB1-PIR-{n:03d}", f"Pharmacy incident at {v.get('vendor_name', e['vendor_id'])}",
              "pharmacy_incident_report", f"{v.get('vendor_name', e['vendor_id'])} store manager",
              say_date(d_of(e["scan_timestamp"]) or date(2025, 1, 1), rng), body,
              truth([e["scan_code"]], [p["batch_number"]] if p else [], [p["manufacturer_id"]] if p else [],
                    [], [e["vendor_id"]]))


# -- DB4: ministry ------------------------------------------------------------------------------

def gen_db4(D, rng):
    products = D["products"]
    for i, r in enumerate(D["recalls"], 1):
        p = products.get(r["item_ref"], {})
        body = (f"Recall notice {r['recall_id']} (Class {r['recall_class']})\n\n"
                f"The Central Drugs Standard Control Organisation directs the immediate recall of "
                f"{p.get('product_name', r['item_ref'])}, batch {r['batch_ref']}, pack code {r['item_ref']}, "
                f"manufactured by {D['mfgs'].get(r['manufacturer_ref'], {}).get('company_name', r['manufacturer_ref'])} "
                f"({r['manufacturer_ref']}).\n\nReason: {r['reason']}.\n\n"
                f"Pharmacies and distributors must stop sale, quarantine all stock of this batch and return it to "
                f"the manufacturer. Patients who have this product should stop using it and consult a doctor.")
        write("db4", f"DOC-DB4-RCL-{i:03d}", f"Recall notice {r['recall_id']}: {p.get('product_name', r['item_ref'])}",
              "recall_notice", "Central Drugs Standard Control Organisation", r["issued_on"], body,
              truth([r["item_ref"]], [r["batch_ref"]], [r["manufacturer_ref"]]), fmt="html")
    # investigation reports for blacklisted items
    for i, b in enumerate(D["blacklist"], 1):
        lab = D["labs"].get(b["complaint_id"])
        p = products.get(b["item_ref"])
        sold = [e for e in D["events"] if e["scan_code"] == b["item_ref"]][:3]
        shp = [s for s in D["batches"] if s["batch_serial"] == b["item_ref"]][:2]
        body = (f"# Investigation report\n\nSubject: packs bearing code {b['item_ref']}"
                + (f" ({p['product_name']})" if p else " (no registered product)") + ".\n\n"
                f"## Basis\n\nComplaint {b['complaint_id'] or 'n/a'}; blacklist entry {b['blacklist_id']} "
                f"({b['severity']}). Reason recorded: {b['reason']}.\n\n"
                f"## Laboratory\n\n" + (f"{lab['lab_name']}: {lab['result']}. {lab['findings_summary']}" if lab else
                                         "No laboratory report on file.") + "\n\n"
                f"## Supply chain\n\n" + ("Sold at: " + ", ".join(f"{e['vendor_id']} ({e['scan_timestamp']})" for e in sold)
                                          if sold else "No retail sale traced.") + " "
                + ("Shipped by: " + ", ".join(f"{s['distributor_id']} ({s['batch_id']})" for s in shp) if shp
                   else "No licensed shipment traced.") +
                "\n\n## Conclusion\n\nThe item remains on the national blacklist pending prosecution.")
        write("db4", f"DOC-DB4-INV-{i:03d}", f"Investigation report: {b['item_ref']}", "regulatory_investigation_report",
              "Ministry of Consumer Affairs enforcement wing", b["blacklisted_on"], body,
              truth([b["item_ref"]], [p["batch_number"]] if p else [], [p["manufacturer_id"]] if p else [],
                    [s["distributor_id"] for s in shp], [e["vendor_id"] for e in sold]))
    # consumer complaint letters (the full text behind a complaints row)
    picks = [c for c in D["complaints"] if c["complainant_type"] == "consumer"]
    picks = sorted(rng.sample(picks, min(60, len(picks))), key=lambda c: c["complaint_id"])
    for i, c in enumerate(picks, 1):
        p = products.get(c["complaint_item_ref"])
        brand = misspell(p["product_name"], rng) if p else "the medicine"
        claim = {"counterfeit": "I believe this is a fake", "substandard": "it did not work at all",
                 "adverse_reaction": "I had a bad reaction after taking it", "price_gouging": "I was overcharged",
                 "mislabeled": "the label does not match the contents", "expired": "the pack was past its expiry"}.get(
                     c["complaint_category"], "something is wrong with it")
        body = (f"Dear Sir/Madam,\n\nI bought {brand} with code {typed(c['complaint_item_ref'], rng, 0.4)} at "
                f"{c['purchase_location'] or 'a local chemist'}. {claim.capitalize()}. {c['description'] or ''}\n\n"
                f"Please look into this.\n\nRegards,\n{c['complainant_name'] or 'A concerned citizen'}")
        write("db4", f"DOC-DB4-CCL-{i:03d}", f"Consumer complaint {c['complaint_id']}", "consumer_complaint",
              "National Consumer Helpline (letters received)", say_date(d_of(c["complaint_date"]) or date(2025, 1, 1), rng),
              body, truth([c["complaint_item_ref"]], [p["batch_number"]] if p else [],
                          [p["manufacturer_id"]] if p else []), fmt="txt")
    # not-of-standard-quality bulletins listing several codes
    nsq = [b["item_ref"] for b in D["blacklist"]]
    for i in range(2):
        listed = nsq[i::2]
        body = ("Monthly drug alert: not of standard quality / spurious\n\nThe following pack codes were declared "
                "spurious or not of standard quality this month. Stockists must not sell them:\n\n"
                + "\n".join(f"- {x}" for x in listed))
        write("db4", f"DOC-DB4-NSQ-{i + 1:03d}", f"Drug alert bulletin {i + 1}", "nsq_bulletin",
              "Central Drugs Standard Control Organisation", say_date(date(2025, 8 + i, 1), rng), body,
              truth([x for x in listed if x in products]))


def main():
    rng = random.Random(SEED)
    D = load()
    if os.path.isdir(OUT):
        for d in ("db1", "db2", "db3", "db4"):
            shutil.rmtree(os.path.join(OUT, d), ignore_errors=True)
    GT.clear()
    gen_db3(D, rng)
    gen_db2(D, rng)
    gen_db1(D, rng)
    gen_db4(D, rng)
    with open(os.path.join(OUT, "ground_truth.json"), "w", encoding="utf-8") as f:
        json.dump({"note": "Evaluation only. Document search never reads this file.", "documents": GT}, f, indent=1)
    by = defaultdict(lambda: defaultdict(int))
    for g in GT.values():
        by[g["owner"]][g["type"]] += 1
    for owner in sorted(by):
        print(f"  {owner}: " + ", ".join(f"{t} {n}" for t, n in sorted(by[owner].items())))
    print(f"  {len(GT)} documents -> {OUT}")


if __name__ == "__main__":
    main()
