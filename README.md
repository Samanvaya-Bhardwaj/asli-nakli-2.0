# Asali / Nakali Medicine Verification System
## Project 2: Intelligent, Trustworthy and Decision-Centric Integration from Heterogeneous Data

"Asali" (Hindi/Urdu/Swahili) = Genuine
"Nakali" (Hindi/Urdu/Swahili) = Counterfeit / Fake

---

## Phase 3: federated, context-aware integration

**Start here:** [PHASE3_FINAL_REPORT.md](PHASE3_FINAL_REPORT.md) maps each requirement to its
evidence and lists what is still open. Documentation is in [phase3/documentation/](phase3/documentation/).

```bash
python scripts/run_federation.py --env-file deploy/local.env   # 4 database services + coordinator (one machine)
# then open http://127.0.0.1:8030/  and ask a question
python scripts/run_phase3_tests.py                              # every suite, results -> phase3/documentation/evidence/
```

Plan and progress: [PHASE3_IMPLEMENTATION_PLAN.md](PHASE3_IMPLEMENTATION_PLAN.md) (§O is the log).
Requirement 1 is done. Each database now holds 7 related tables, with one medicine spread across
them through primary and foreign keys. DB1 also mirrors its new entities as JSON collections
linked by declared document references.

```bash
python scripts/migrate_phase3.py               # upgrade existing databases in place (keeps every row)
python -m integration.federation.inspect       # tables, PK/FK, integrity check, one join per database
python -m unittest tests.test_phase3_schema    # 23 checks on a throwaway copy
```

Requirement 2 is implemented: four database services and a federated query coordinator. Each
database runs as its own service holding only its own data. Each service executes the subqueries
it is sent and discovers context through its own keys. The coordinator plans each question over
the GAV mapping and combines the answers. Deploying on two machines is described in
[deploy/README.md](deploy/README.md). So far it has only been run as a one-machine simulation.

```bash
python scripts/run_federation.py --env-file deploy/local.env      # local simulation: 4 services + coordinator
python scripts/federated_demo.py "Is MED-ASALI-009 genuine and was its cold chain maintained?"
python -m unittest tests.test_phase3_federation                   # 16 checks; run on its own
```

Query context discovery follows SCORE. Each database keeps the full result of its subquery and
weights its terms by tf x idf. It then joins only the most relevant neighbouring table through a
real foreign key, step by step, up to MAX_AUGMENTATION, and returns its TOP_N context terms with
their provenance. The mediator merges the four local contexts into one ranked query context. The
algorithm is described in [phase3/documentation/PHASE3_CONTEXT_DISCOVERY.md](phase3/documentation/PHASE3_CONTEXT_DISCOVERY.md).

```bash
python scripts/score_demo.py "Was the cold chain of MED-ASALI-009 maintained?"   # needs the services running
python -m unittest tests.test_phase3_score                                         # 12 checks
```

The query context is then used to search 303 documents: quality reviews, inspection reports, shipment
notes, incident reports, recall notices, investigations and complaint letters. Each source keeps
and searches its own documents. The answer keeps verified database facts apart from what documents
report, and documents never change the verdict. The pipeline is described in
[phase3/documentation/PHASE3_UNSTRUCTURED_RETRIEVAL.md](phase3/documentation/PHASE3_UNSTRUCTURED_RETRIEVAL.md).

```bash
python scripts/integrated_demo.py "Find information about batch BATCH-A009 manufactured by Biocon and identify any quality or safety concerns"
python scripts/eval_retrieval.py                     # context-driven search vs the question alone
python -m unittest tests.test_phase3_documents        # 13 checks
```

---

## Phase 2: integration under uncertainty

The four silos record the same medicine pack imperfectly: a pharmacist types a smudged serial, a
phone camera reads a label through glare, a clerk re-keys a dispatch note, a citizen types a code
into a complaint form. Phase 2 links those records back to the registry and cleanses the silos,
without erasing the evidence of counterfeiting they also contain. **Full write-up:
[UNCERTAINTY.md](UNCERTAINTY.md).**

| Rubric item | Where |
|---|---|
| Approximate matching of a noisy pack code (or a label photo) and the reverse | `integration/uncertainty/linkage.py`, dashboard → *Uncertainty* §1–2 |
| Why this algorithm, measured | `integration/uncertainty/train.py`, dashboard §3, [UNCERTAINTY.md §3](UNCERTAINTY.md) |
| Cleansing with image and contextual data, no anomalies left | `integration/uncertainty/cleanser.py`, dashboard §4–5 |
| Prompts, generated code, highlighted changes | [vibe_coding/](vibe_coding/), dashboard → `vibe/index.html` |
| Insert / modify / delete checks | dashboard §6, Explorer, `tests/test_uncertainty.py` |

```bash
python scripts/rebuild_data.py              # all silos + noisy dataset + images + trained model (~4 min)
python scripts/run_cluster.py --mode all    # then open http://localhost:8011/uncertainty.html
python -m integration.uncertainty match MED-ASAL1-OO7 --vendor VND-005 --price 95
python -m unittest tests.test_uncertainty   # 18 checks on a throwaway copy of the data
```

---

## 1. Problem Statement

Counterfeit medicine detection requires combining records that reside in independently designed systems:
- Whether the medicine was legitimately manufactured and registered.
- Whether it was transported through authorized, cold-chain compliant distributors.
- Whether the item was scanned or sold at a licensed pharmacy.
- Whether regulatory complaints, lab failures, or recall notices exist.

Each database was designed in isolation by different stakeholders and uses a different column name for the primary item code:
- DB1 (Retail POS): `scan_code`
- DB2 (Distributor ERP): `batch_serial`
- DB3 (Manufacturer Registry): `product_uid`
- DB4 (Ministry of Consumer Affairs): `complaint_item_ref`

---

## 2. Integration Architecture

The system uses a Global-as-View (GAV) mediator architecture with a two-tier hybrid decision engine:

```
                      Raw User Barcode / QR
                                |
                                v
                +-------------------------------+
                |  Tier-0: Normalizer           |
                |  (casing, separators, prefix) |
                +---------------+---------------+
                                |
                                v
                +-------------------------------+
                |  GAV Mediator Layer           |
                |  (schema_mapping.json)        |
                +---------------+---------------+
                                |
        +-----------+-----------+-----------+-----------+
        |           |                       |           |
        v           v                       v           v
    +-------+   +-------+               +-------+   +-------+
    |  DB1  |   |  DB2  |               |  DB3  |   |  DB4  |
    | Retail|   | Dist  |               |  Mfg  |   | Govt  |
    +-------+   +-------+               +-------+   +-------+
        |           |                       |           |
        +-----------+-----------+-----------+-----------+
                                |
                                v
                +-------------------------------+
                |  Canonical Unified View       |
                |  (GlobalItemHistory)          |
                |  - Provenance tags            |
                |  - Cross-DB contradictions    |
                |  - Supply chain event timeline|
                +---------------+---------------+
                                |
                                v
                +-------------------------------+
                |  Tier-1: Hard Veto Gates      |
                |  - V1: Phantom serial         |
                |  - V2: Ministry blacklist     |
                |  - V3: Temporal paradox       |
                |  - V4: Replay / duplicate scan|
                |  - V5: Custody bypass         |
                +---------------+---------------+
                                |
               +----------------+----------------+
               | Any Fail                        | All Pass
               v                                 v
        [COUNTERFEIT]                     +-------------------------------+
        Score = 0                         |  Tier-2: Soft Compliance Score|
        Auto-Draft MCA Report             |  (Starts 100, docks points for|
                                          |   cold chain, MRP, expiry)    |
                                          +---------------+---------------+
                                                          |
                                                          v
                                                  Score >= 80 : ASALI
                                                  Score 50-79 : SUSPICIOUS
                                                  Score < 50  : NAKALI
```

---

## 3. The 4 Heterogeneous Databases

| Database | Owner | Table | Integration Column |
|----------|-------|-------|-------------------|
| DB1: Purchase Registry | Retail Vendor POS | `purchase_events` | `scan_code` |
| DB2: Distributor Ledger | Logistics Distributor | `distribution_batches` | `batch_serial` |
| DB3: Manufacturer Registry | Pharma Manufacturer | `products` | `product_uid` |
| DB4: Ministry Reports | Regulatory Authority | `complaints` | `complaint_item_ref` |

---

## 4. Verification Engine

### Tier-1: Hard Veto Gates (Deterministic)
If any of these 5 gates trigger, the item is immediately marked NAKALI with a score of 0:
1. `V1_PHANTOM_SERIAL`: Item does not exist in the manufacturer catalog (DB3).
2. `V2_MINISTRY_BLACKLIST`: Item is actively listed on the government blacklist (DB4).
3. `V3_TEMPORAL_PARADOX`: Manufacture date is after dispatch or retail purchase date.
4. `V4_REPLAY_SCAN`: Duplicate scans across impossible locations or re-dispensing of consumed units.
5. `V5_CUSTODY_BYPASS`: Selling vendor was never part of the authorized distribution targets.

### Tier-2: Soft Compliance Signals (Weighted)
When all Tier-1 gates pass, the item starts at 100 points:
- Cold chain breach for temperature-sensitive drug: -25
- Unauthorized distributor route: -20
- Supply chain gap (retail event with no distribution record): -20
- Retail price below 40% of MRP (counterfeit dumping indicator): -15
- Unlicensed distributor: -15
- Active consumer complaints with ministry: -10
- Product expired: -10
- All checks clean bonus: +5

### Verdict Thresholds
- `80 - 100`: ASALI (Genuine)
- `50 - 79` : SUSPICIOUS (Quality or custody issue)
- `0 - 49`  : NAKALI (Counterfeit)

---

## 5. Quick Start

### 1. Initialize Databases and Seed Data
```bash
python3 scripts/rebuild_data.py          # everything below, plus the phase-2 dataset and model
```
or step by step (phase-1 seeds only):
```bash
python3 create_databases.py
python3 data/seed_db3.py
python3 data/seed_db2.py
python3 data/seed_db1.py
python3 data/seed_db4.py
python3 data/generate_uncertain_data.py  # phase 2: noisy records + ground truth
python3 data/seed_nosql_db1.py
python3 -m integration.uncertainty.train # phase 2: fit and benchmark the matcher
```

### 2. Run the Full Integration Demo
```bash
python3 demo.py
```

### 3. Verify Individual Items via CLI
```bash
# Verify a genuine antibiotic
python3 api/verify_item.py MED-ASALI-001

# Verify an item with a broken cold chain
python3 api/verify_item.py MED-ASALI-009

# Verify a counterfeit item (not registered in DB3)
python3 api/verify_item.py MED-NAKALI-001

# Run full batch verification across all items
python3 api/verify_item.py --all

# Check tamper-evident SHA-256 audit chain
python3 api/verify_item.py --audit

# View system statistics
python3 api/verify_item.py --stats
```

### 4. Interactive Web Dashboard
Open `dashboard/index.html` in any web browser.
To start the live backend server:
```bash
python3 demo.py --serve
```

---

## 6. Directory Structure

```
Project2_Asali_Nakali/
|-- api/
|   `-- verify_item.py          # Main CLI entry point
|-- integration/
|   |-- identifier_normalizer.py# Tier-0 input cleaner
|   |-- schema_mapping.json     # GAV ontology bridge
|   |-- resolver.py             # Cross-DB wrapper queries
|   |-- canonical_model.py      # GlobalItemHistory unified view
|   |-- hard_veto_engine.py     # Tier-1 deterministic veto gates
|   |-- lifecycle_state.py      # Digital twin state tracker
|   |-- trust_engine.py         # Tier-2 soft score engine
|   |-- anomaly_detector.py     # Multi-signal anomaly detector
|   |-- audit_chain.py          # SHA-256 tamper-evident log
|   |-- ministry_reporter.py    # Auto-drafts MCA complaints
|   `-- uncertainty/            # Phase 2: matching and cleansing under uncertainty
|       |-- similarity.py       #   Levenshtein, Damerau, Jaro-Winkler, q-gram, Soundex
|       |-- confusion.py        #   learned OCR noisy-channel edit distance
|       |-- standardize.py      #   codes, dates, currency, vendor ids, label OCR text
|       |-- context.py          #   live evidence snapshot + blocking index
|       |-- linkage.py          #   Fellegi-Sunter + posterior with a "no product" hypothesis
|       |-- cleanser.py         #   scan / apply / review / undo with lineage
|       |-- train.py            #   fit on a training split, benchmark on held-out data
|       `-- http_api.py         #   /api/v1/uncertainty/* for both nodes
|-- databases/                  # SQLite database files (+ data_quality.sqlite lineage)
|-- schema/                     # SQL DDL schemas (DB1 - DB4)
|-- data/                       # Seed scripts, generate_uncertain_data.py, render_label_images.py
|   `-- generated/              # ground_truth.json, linkage_model.json, benchmark_results.json
|-- dashboard/                  # Web dashboard (HTML, CSS, JS); uncertainty.html is phase 2
|-- tests/                      # Phase-2 regression suite
|-- vibe_coding/                # Prompts, generated snapshot, change log, diff report generator
|-- reports/                    # Generated verification reports
|-- create_databases.py         # DB initialization script
|-- demo.py                     # Automated demonstration script
|-- UNCERTAINTY.md              # Phase-2 write-up
`-- README.md                   # System documentation
```
