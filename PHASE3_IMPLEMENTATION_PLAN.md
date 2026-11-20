# Phase 3 Implementation Plan — Federated, Context-Aware Query over Structured + Unstructured Data

**Status (18 Nov 2026):** plan approved with the decisions in §N-Approved.
- **Requirement 1** is implemented and validated (§O.1).
- **Requirement 2** is implemented and validated as a local simulation (§O.2). The two-machine run is configured but **not yet executed**: the Docker engine needs WSL2, and a second machine has not been available.
- **Requirement 3** (and the context half of Requirement 2), the SCORE-inspired query context discovery, is implemented and validated (§O.3). The prompt called it "Requirement 2".
- **Requirement 4**, context-aware unstructured retrieval and the integrated answer, is implemented and validated (§O.4). The prompt called it "Requirement 3".
- Requirement 5's record (prompts, generated code, changes) is kept up to date in `vibe_coding/` as each prompt is implemented; its diff page (`make_diff_report.py` for Phase 3) is not built yet.
- **Integration (prompt P3-5):**
  - one user-facing page, served by the coordinator at `/`;
  - an end-to-end HTTP test (9/9);
  - three generated demonstration scenarios;
  - documentation in `phase3/documentation/`;
  - **`PHASE3_FINAL_REPORT.md`**, which maps every requirement to its evidence and lists what is not done (above all, execution on two machines).
**Audit date:** 18 Nov 2026 · **Repository root:** `Project2_Asali_Nakali/` (audited on branch `main`, HEAD `d16b44f`; work continues on branch `phase3`)

How the audit was done: every Python module, schema, node server, wrapper, config and doc file was read. The live database files were inspected **read-only** (table list, row counts, columns, `PRAGMA foreign_key_list`, sample rows). Python is not installed on the audit machine (only the Windows Store stub), so the inspection used Node 24's built-in `node:sqlite`. No project code was run, so runtime claims below come from reading the code. Where a claim is an inference, it says so.

---

## Contents

- A. Architecture and technology stack
- B. The four databases and their schemas
- C. Tables, collections, API endpoints and relationships
- D. GAV mediator and query execution workflow
- E. Machine / deployment configuration
- F. Structured and unstructured data available today
- G. Reusable components
- H. Components that need modification
- I. Missing components
- J. Compatibility issues and risks
- K. Phase 3 design
- L. Step-by-step implementation plan
- M. Testing and evaluation
- N. Decisions needed before implementation

---

## A. Existing architecture and technology stack

| Aspect | What the code actually uses |
|---|---|
| Language | **Python 3, standard library only.** No third-party packages anywhere (`sqlite3`, `http.server`, `urllib`, `json`, `threading`, `difflib`, `hashlib`). Dockerfile base: `python:3.11-slim`. |
| Structured storage | 4 SQLite files in `databases/`, plus `audit_chain.sqlite`, `activity_log.sqlite`, `data_quality.sqlite` (Phase 2 lineage). |
| NoSQL | DB1 also lives as a **JSON document collection** `data/nosql_store/db1_retail_pos.json` (1,647 nested docs). It is a *mirror* rebuilt from the DB1 SQLite tables by `data/seed_nosql_db1.py::sync_collection()`. Documents inserted only into the collection (`origin != "sqlite_mirror"`) are kept across syncs. |
| REST | DB4 is served as a REST microservice (`api/ministry_service.py`, port 8001, bearer token `CDSCO-MCA-2026-KEY`, envelope `{meta, data}`), backed by SQLite. |
| HTTP servers | `http.server.HTTPServer`, **single-threaded** (RUNNING.md §5.4). |
| Frontend | Static HTML/JS in `dashboard/` (index, verify, explorer, uncertainty, vibe). It talks to the nodes over HTTP (`dashboard/assets/cluster.js`). Also served by the nodes themselves. |
| Architecture | GAV mediator–wrapper (`integration/mediator.py`, `resolver.py`, `wrappers/`), canonical view `GlobalItemHistory` (`canonical_model.py`), two-tier decision engine (hard vetoes + weighted trust score), lifecycle state machine, SHA-256 audit chain, auto ministry report. |
| Phase 2 | `integration/uncertainty/`: similarity measures, learned OCR confusion costs, Fellegi–Sunter linkage with a "no product" hypothesis, context-based cleansing with lineage/undo, training/benchmark, HTTP API under `/api/v1/uncertainty/*`. |
| Distribution | Two node processes: **PC1** (`api/node_pc1.py`, :8011: DB1 + DB2) and **PC2** (`api/node_pc2.py`, :8012: DB3 + DB4 + audit). Both hold **full copies of all databases**, and writes are replicated between them (`integration/replication.py`). |
| Vibe-coding evidence | `vibe_coding/` holds `PROMPTS.md`, `CHANGES.md`, `phase1_baseline/`, `generated_v0/` and `rounds/12…16/`. `make_diff_report.py` builds `dashboard/vibe/index.html`. |

Codebase size: about 14,300 lines of Python in `integration/`, `api/`, `data/`, `scripts/` and `tests/`. There are 28 unit tests (`tests/test_uncertainty.py`, `tests/test_replication.py`).

> **Note on the nested folder.** `Project2_Asali_Nakali/Project2_Asali_Nakali/` is a **separate, older git clone** with its own `.git`, 2 commits and different data and code. It is untracked in the outer repo. It is not used by the running system, but Docker's `COPY . /app` copies it into every image. Phase 3 work will touch **only the outer tree**. See decision N-4.

---

## B. The four database implementations and schemas

Row counts are from the live files today.

### DB1 — Retail POS (`db1_purchase_registry.sqlite` + JSON collection)
Integration key: `scan_code`.

| Table | Rows | PK | FKs (declared) |
|---|---:|---|---|
| `vendors` | 38 | `vendor_id` | – |
| `purchase_events` | 1,647 | `event_id` | `vendor_id → vendors` |
| `scan_anomaly_log` | **0** | `anomaly_id` | **none** (links only by `scan_code` text) |

The JSON collection embeds vendor and license details inside each scan document (`dispensary{license, location{geo}, contact}`, `pos_terminal`, `transaction`, `anomaly_telemetry`, optional `label_capture{ocr_text, image}`). **3 tables, 1 FK, so the 4–5 table requirement is not met.**

### DB2 — Distributor ERP (`db2_distributor_ledger.sqlite`)
Integration key: `batch_serial`.

| Table | Rows | PK | FKs |
|---|---:|---|---|
| `distributors` | 9 | `distributor_id` | – |
| `distribution_batches` | 427 | `batch_id` | `distributor_id → distributors` |
| `distributor_vendor_contracts` | 44 | `contract_id` | `distributor_id → distributors` |
| `return_log` | 2 | `return_id` | **none** (by `batch_serial` text) |

`source_warehouse` is free text and `temperature_log_url` is always NULL. Columns that point to other databases: `destination_vendor_id` (DB1), `manufacturer_ref` (DB3; contains deliberate noise such as `UNKNOWN` and `''`). **4 tables, 2 FKs.**

### DB3 — Manufacturer Registry (`db3_manufacturer_registry.sqlite`)
Integration key: `product_uid`.

| Table | Rows | PK | FKs |
|---|---:|---|---|
| `manufacturers` | 10 | `manufacturer_id` | – |
| `products` | 207 | `product_uid` | `manufacturer_id → manufacturers` |
| `authorized_distributors` | 54 | `auth_id` | `manufacturer_id → manufacturers` (`distributor_ref` points to DB2) |
| `batch_release_certs` | **0** | `cert_id` | `product_uid → products` |

`item_lifecycle` is created on demand by `lifecycle_state.py` (it is not in this copy yet). It is listed in `schema_mapping.json` and `DB_METADATA` but not in `schema_db3.sql`. **4 tables, 3 FKs, one of them empty.**

### DB4 — Ministry Reports (`db4_ministry_reports.sqlite`, served over REST)
Integration key: `complaint_item_ref`.

| Table | Rows | PK | FKs |
|---|---:|---|---|
| `ministry_officers` | 5 | `officer_id` | – |
| `complaints` | 149 | `complaint_id` | `assigned_officer_id → ministry_officers` |
| `ministry_blacklist` | 9 | `blacklist_id` | `complaint_id → complaints` |
| `lab_reports` | 3 | `lab_report_id` | `complaint_id → complaints` |
| `public_alerts` | 3 | `alert_id` | **none** |

**5 tables, 3 FKs. Already meets the count**; needs only enrichment and one FK.

---

## C. Tables, collections, API endpoints and relationships

### C.1 Relationship map today (solid = declared FK, dashed = value-based cross-DB link)

```
DB1  vendors ─< purchase_events          scan_anomaly_log (orphan)
DB2  distributors ─< distribution_batches          return_log (orphan)
                 └─< distributor_vendor_contracts
DB3  manufacturers ─< products ─< batch_release_certs (empty)
                  └─< authorized_distributors
DB4  ministry_officers ─< complaints ─< ministry_blacklist
                                     └─< lab_reports           public_alerts (orphan)

Cross-DB (by value, no FK possible):
  item_code      = DB1.scan_code = DB2.batch_serial = DB3.product_uid = DB4.complaint_item_ref / item_ref
  vendor_id      : DB2.destination_vendor_id, DB2.contracts.vendor_id  ->  DB1.vendors
  distributor_id : DB3.authorized_distributors.distributor_ref         ->  DB2.distributors
  manufacturer_id: DB2.manufacturer_ref                                ->  DB3.manufacturers
```

### C.2 HTTP endpoints

| Service | Method · Path | Purpose |
|---|---|---|
| PC1 :8011 | GET `/health`, `/api/v1/health` | node info |
| | GET `/api/v1/pos/scans?scan_code=` | DB1 JSON docs by exact code |
| | GET `/api/v1/distributor/batches?batch_serial=` | DB2 batches + distributors + returns |
| | GET `/api/v1/explorer/{schema,entries,examples,validate_chain,activity,conflict_scenarios}` | Explorer |
| | POST `/api/v1/explorer/{operation,activity/clear,reset}` | CRUD + `FEDERATED_VIEW/INSERT/DELETE/QUARANTINE` (replicated) |
| | GET/POST `/api/v1/uncertainty/*` | Phase 2 match / reverse / scan / apply / decide / undo / lineage / benchmark |
| | GET `/*` | static dashboard |
| PC2 :8012 | same explorer/uncertainty/health routes, plus GET `/api/v1/cdsco/product?product_uid=`, GET `/api/v1/dossier?item_ref=`, GET/POST `/api/v1/partition/toggle` | DB3 product, DB4 dossier, partition simulation |
| Ministry :8001 | GET `/api/v1/{health,complaints,blacklist,lab_reports,alerts}?item_ref=`, POST `/api/v1/dossier` | DB4 REST |

There is **no** `/api/v1/verify` (RUNNING.md §5.3). The real federated path is `POST /api/v1/explorer/operation {"operation":"FEDERATED_VIEW"}`.

---

## D. Current GAV mediator and query execution workflow

**Main verification path** (`api/verify_item.py::verify`, also behind `FEDERATED_VIEW`):

```
raw code
 → identifier_normalizer.normalize           (Tier-0)
 → resolver.resolve(canon)
     → entity_resolver.resolve_entity        (confusion folding, Jaro-Winkler; reads DB3 locally)
     → WRAPPER_DB1 (NoSQL JSON file, local)   find scan_code
     → WRAPPER_DB2 (SQLite, local)            batches ⋈ distributors, returns
     → WRAPPER_DB3 (SQLite, local)            products ⋈ manufacturers, auth dists, certs
     → WRAPPER_DB4 (HTTP :8001, else IN-PROCESS fallback reading the local SQLite)
     → semantic_transformer (currency, timestamps, temperature)
     → conflict_resolver.arbitrate_conflicts
   = ItemRecord
 → lifecycle tracker → canonical_model.build_global_view (GlobalItemHistory + contradictions)
 → anomaly_detector → hard_veto_engine (V1–V5) → trust_engine (weighted score)
 → audit_chain.log → ministry_reporter (if NAKALI)
```

Key facts for Phase 3:

1. **The verification path reads all four databases from local files** on whichever node runs it. Sources are sequential, not parallel. Only DB4 is ever reached over the network.
2. **The query is a single key lookup** (`item_code`). The mediator never runs a multi-hop or keyword query, and each wrapper uses **hand-written joins one hop deep**.
3. `GavQueryMediator.execute_distributed_query` (`mediator.py`) *does* call PC1/PC2 over HTTP, but it returns only telemetry (found / latency / circuit breaker / schema evolution). It **does not feed the veto or trust engines**.
4. `schema_mapping.json` is descriptive. Its `lookup_query` strings are not executed (the SQL actually used is duplicated inside `sql_wrapper.py` and `node_pc1/2.py`).

---

## E. Existing machine / deployment configuration

| Mechanism | What it does |
|---|---|
| `scripts/run_cluster.py --mode pc1 \| pc2 \| all \| --check-health \| --stop` | Starts the node(s). `all` runs both as threads in one process sharing the same files. |
| `integration/distributed_config.py` | Endpoints from env vars `PC1_HOST/PORT`, `PC2_HOST/PORT`, `DB4_PORT`, `MEDIATOR_PORT`, or from `data/network_topology.json`. **Only two node slots.** |
| `integration/replication.py` | Every write accepted by one node is replayed to the other (`X-Asali-Peer` / `X-Asali-Replica` headers, storage-id dedupe for same folder). |
| `dashboard/assets/cluster.js` | Browser-side config `{pc1, pc2}` in localStorage. `urlFor(db)` sends db1/db2 to PC1 and everything else to PC2. |
| `docker-compose.yml` | 3 containers: `asali-pc1-retail` (:8011), `asali-pc2-authority` (:8012, :8001), and `asali-mediator`, which is just `python -m http.server` serving the dashboard. **Every image contains every database** (`COPY . /app`). |
| RUNNING.md §2/2b | Two-laptop LAN setup tested. A per-silo address layout ("C2") was described but not implemented. |

**Conclusion:** today's "distribution" is two **full replicas**. No machine holds only its own database, and no query is federated in a way where each source does its own reasoning.

---

## F. Structured and unstructured data available today

**Structured:** as in §B. The data includes deliberate Phase 2 noise: noisy codes, duplicate vendors, `UNKNOWN` manufacturer refs, mixed date formats in DB1 JSON (`"01-Dec-2025 14:50"` and `"2026-02-11 10:31:00"`). `data/generated/ground_truth.json` holds the labels for that noise.

**Unstructured or semi-structured, already present:**

| Source | Volume | Content |
|---|---:|---|
| `complaints.description` (DB4) | 149 | Citizen narratives, some with misspelt brands and codes embedded in the text |
| `lab_reports.findings_summary / recommendation` (DB4) | 3 | Forensic text ("Diethylene glycol detected at 0.45% w/v…") |
| `public_alerts.message` (DB4) | 3 | Public notices (one has a noisy ref `MED_EPVOI_696`) |
| `purchase_events.label_text` + `label_image` (DB1) | 176 / 31 JPGs | OCR text of pack labels and photos (`dashboard/samples/labels/`) |
| `distribution_batches.discrepancy_details`, `return_log.notes`, `ministry_blacklist.reason / health_risk` | few | Short free text |
| `reports/*.html` | 42 | Generated verification reports (gitignored runtime output, not a corpus) |

**Missing:** a real **document corpus** that can be searched separately from the structured rows: recall/NSQ circulars, package inserts or monographs, inspection reports, cold-chain incident reports, pharmacovigilance narratives, news items. There is also **no text index** (no BM25/TF-IDF, no inverted index).

---

## G. Components that can be reused for Phase 3

| Component | Reuse in Phase 3 |
|---|---|
| `wrappers/base_wrapper.py` (`BaseWrapper`, `SourceMetadata`) | Interface for the new remote (HTTP) wrappers, so `resolver.resolve()` keeps working unchanged |
| `identifier_normalizer.py`, `uncertainty/standardize.py` (`canonical_code`, `looks_like_code`, `brand_key`, `to_date`) | Seed extraction from the user query, on every node |
| `uncertainty/similarity.py`, `uncertainty/context.fold()` and confusion costs | Approximate seed matching on each node, and fuzzy code mentions in documents |
| `entity_resolver.py` | Mediator-side canonicalisation of item codes (backed by the DB3 node in remote mode) |
| `semantic_transformer.py` | Normalising dates, currency and temperature in discovered rows before accumulation |
| `conflict_resolver.py`, `canonical_model._detect_contradictions` | Cross-source conflicts inside the accumulated context |
| `hard_veto_engine`, `trust_engine`, `anomaly_detector`, `lifecycle_state`, `audit_chain` | **Unchanged.** When a federated query resolves to an item code, the existing verdict is attached |
| `ministry_service.py` (REST envelope, bearer auth, `MinistryDataStore`) | DB4 node keeps its REST character. Phase 3 endpoints are added to it |
| `distributed_config.py`, `run_cluster.py` | Extended (new modes and node slots); existing modes kept |
| `schema_adapter.py` | Applied to DB1 documents returned by discovery (schema-version drift) |
| `uncertainty/paths.py` (env-redirectable paths) | Pattern for per-node data dirs and throwaway test copies |
| `seed_nosql_db1.py::sync_collection` | Extended to mirror the new DB1 tables into new JSON collections |
| `vibe_coding/make_diff_report.py` + `rounds/` convention | Phase 3 prompts / generated code / diffs (requirement 5) |
| Dashboard shell (`nav.js`, `theme.js`, `style.css`, `cluster.js`) | New `federated.html` page in the same design |

---

## H. Components that need modification (all additive and backward-compatible)

| File | Change |
|---|---|
| `schema/schema_db1..4.sql` | Append the Phase 3 tables / nullable FK columns (`CREATE TABLE IF NOT EXISTS`). Fresh builds get them; existing builds get them from the migration script. |
| `data/seed_nosql_db1.py` | Also write the new DB1 collections (`pos_terminals`, `pharmacists`, `prescriptions`, `vendors`) as separate JSON files. The existing `db1_retail_pos.json` keeps its **exact** shape. |
| `integration/distributed_config.py` | Add `db1_node … db4_node`, `mediator_node` URLs (env `DB1_URL…`, or the topology file). `pc1_node` / `pc2_node` are kept. |
| `integration/wrappers/rest_wrapper.py` | Base URL from config instead of hard-coded `127.0.0.1:8001`. **Turn off the in-process fallback when `ASALI_FEDERATION=remote`**; otherwise it silently reads a local copy. |
| `integration/resolver.py` | Choose local wrappers (default, Phase 1/2) or remote wrappers (`ASALI_FEDERATION=remote`) at import time. No other logic change. |
| `api/ministry_service.py` | `--host` argument (default stays `127.0.0.1` for Phase 1/2, `0.0.0.0` for Phase 3). Use `ThreadingHTTPServer`. Mount the Phase 3 routes. Fix the `complainant_type` value in `create_dossier` (see J-8). |
| `scripts/run_cluster.py` | New modes `db1 \| db2 \| db3 \| db4 \| mediator \| phase3-all`. `pc1/pc2/all` untouched. |
| `scripts/rebuild_data.py` | Run the Phase 3 migration, seed and document generation at the end. |
| `integration/db_explorer.py` | `DB_METADATA[*].tables` and column descriptions include the new tables, so the Explorer shows them. |
| `integration/schema_mapping.json` | New `phase3` section: bridge-key equivalences (`vendor_id`, `distributor_id`, `manufacturer_id`, `item_code`) and node ownership. Phase 1/2 keys untouched. |
| `dashboard/assets/cluster.js` | Optional per-silo URLs (the "C2" layout in RUNNING.md). The old `{pc1, pc2}` config keeps working. |
| `vibe_coding/make_diff_report.py` | Parameterise the baseline / v0 directories so it can also build `dashboard/vibe/phase3.html`. |
| `docker-compose.yml` | Left as is. A new `docker-compose.phase3.yml` is added beside it. |
| `README.md`, `RUNNING.md` | Phase 3 section. |

---

## I. Missing components that must be implemented

1. **Schema extension and backfill** for DB1 (and its NoSQL collections), DB2, DB3, plus minor DB4 enrichment (§K.1).
2. **One node server per database** (`api/node_db.py --db dbN`). Each one opens **only its own database** and exposes Phase 3 endpoints.
3. **Local FK–PK schema graph**: built from `PRAGMA foreign_key_list` for SQLite, and from a declared reference manifest for the JSON collections.
4. **Local context discovery engine** on every node: seed matching followed by relevance-scored multi-hop FK traversal (§K.3).
5. **Federated query mediator** with parallel fan-out, a bounded second round over bridge keys, and a **context accumulator** with relevance pruning (§K.4).
6. **Unstructured document corpus**, generated deterministically from the data and stored with its owning node (§K.5).
7. **Text index and search**: pure-Python BM25 inverted index on each document-holding node, with context-driven query expansion and fuzzy code matching.
8. **Integration of documents with structured results**: entity mentions in documents linked back to the structured entities, then one combined answer.
9. **Remote wrappers** so the existing verification pipeline runs against separate machines.
10. **Dashboard page** `federated.html`: query box, per-node discovery trace (FK paths), accumulated context, ranked documents with highlighted snippets, verdict.
11. **Tests and a relevance benchmark** (§M).
12. **Phase 3 vibe-coding record**: prompts, `generated_v0_phase3/`, change log, diff page.

---

## J. Compatibility issues and risks

| # | Issue | Impact | Mitigation |
|---|---|---|---|
| J-1 | **Full replication versus "separate machines".** PC1/PC2 each hold all DBs and replicate writes. | Phase 3 must show each machine holds only its own database. | Phase 3 nodes refuse to start if they find other databases in their data directory (`ASALI_NODE_DB=db2` → only `db2_*.sqlite` allowed). They do **not** replicate. Legacy pc1/pc2 + replication stay as they are for Phase 1/2 demos. |
| J-2 | **The verification path reads local files** (`resolver.py`, `entity_resolver._load_dynamic_db_records`, `uncertainty/context.py`). | On a DB1-only machine, `verify()` would see DB2–DB4 as absent, so every item would trigger the phantom-serial veto. | Remote wrappers (I-9) behind `ASALI_FEDERATION=remote`, running on the mediator. Entity resolution goes through the DB3 node (`/api/v3/resolve`). Phase 2 uncertainty pages stay on the legacy replica layout; this is stated explicitly, not hidden. |
| J-3 | **DB4 REST fallback** silently reads `GLOBAL_DATASTORE` (local SQLite) when HTTP fails. | Hidden centralisation, and stale data on another machine. | Disabled in remote mode. The node is reported as `UNREACHABLE` and the existing circuit-breaker semantics apply. |
| J-4 | **`ministry_service` binds `127.0.0.1`**; `rest_wrapper` hard-codes `127.0.0.1:8001`. | DB4 cannot be reached from another machine. | `--host` argument plus a config-driven URL (H). |
| J-5 | **DB1 is two representations** (SQLite authoritative for writes, JSON mirror for reads). The JSON has no FK catalog. | New DB1 tables must exist in both forms, with a risk of drift. | SQLite stays authoritative. `sync_collection` mirrors the new tables into **separate collection files** (`db1_vendors.json`, `db1_pos_terminals.json`, `db1_pharmacists.json`, `db1_prescriptions.json`). Discovery on DB1 runs over the **JSON collections** (keeping the NoSQL paradigm), using a reference manifest (`$ref`-style fields such as `vendor_ref`, `terminal_ref`). `db1_retail_pos.json` keeps its exact shape, so `NoSqlDocumentWrapper`, `SchemaEvolutionAdapter` and Phase 2 are unaffected. |
| J-6 | `node_pc1` opens the JSON file with `encoding="ascii"`. | A UTF-8 character (₹, é) in new content crashes the read. | New collections are written with `ensure_ascii=True` (the current default). The document corpus is read as UTF-8 by new code only. |
| J-7 | **Single-threaded `HTTPServer`.** | Parallel fan-out and second-round calls queue up, and a slow node blocks others. | New nodes and the mediator use `ThreadingHTTPServer`. Legacy nodes are unchanged. |
| J-8 | `ministry_service.create_dossier` inserts `complainant_type='automated_ai_sentinel'`, which violates the `complaints` CHECK constraint (allowed: `…,'auto_system'`). | `POST /api/v1/dossier` very likely fails with an IntegrityError. Found by reading the code; not executed. | One-line fix to `'auto_system'`, recorded in the Phase 3 change log. |
| J-9 | **FKs are not enforced** (no `PRAGMA foreign_keys=ON` in wrappers), and the data contains intentional dangling refs (`manufacturer_ref='UNKNOWN'`, counterfeit codes with no DB3 row). | Turning enforcement on would break Phase 2 noise and Explorer inserts. | New FK columns are **nullable** and backfilled where a match exists. Enforcement stays off for legacy connections. Discovery treats dangling refs as evidence ("reference to a missing parent"), not as errors. |
| J-10 | `create_databases.py` **deletes** and recreates the DBs. | Rerunning it wipes Phase 2 cleansing state. | Phase 3 uses an **additive, idempotent** `scripts/migrate_phase3.py` (`CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ADD COLUMN … REFERENCES … DEFAULT NULL`, guarded by `PRAGMA table_info`). `rebuild_data.py` still gives a clean full rebuild. |
| J-11 | **New columns appear in `SELECT *` results** (`sql_wrapper`, node handlers, explorer). | Extra keys in dicts. Downstream code reads by key, so this is expected to be harmless. | Covered by running the existing 28 tests and a Phase 1 verdict regression (all 20 curated items keep their verdicts and scores). |
| J-12 | **Phase 2 model / ground truth** are tied to existing row ids and values. | Changing existing values would invalidate the benchmark. | Phase 3 never edits existing values. It only adds rows to new tables and fills **new** nullable columns. Benchmark re-run as a regression check. |
| J-13 | **Docker images contain every DB** (`COPY . /app`), including the nested old clone. | Containers do not prove separation. | `docker-compose.phase3.yml` mounts **only the owning DB file** into each container (named volume, or a data dir per service) and starts nodes with `ASALI_NODE_DB` (J-1 guard). Add a `.dockerignore` for the nested clone, runtime DBs and PDFs. |
| J-14 | Cross-DB identifiers are noisy (codes, duplicate vendors `VND-036`, `MED_EPVOI_696`). | Bridge keys may not join exactly across nodes. | Each node matches incoming bridge keys approximately, using the Phase 2 `fold()` / similarity functions. Matches are returned with a confidence that feeds the relevance score. |
| J-15 | Uncommitted changes in the working tree (`ground_truth.json`, DB1 JSON, 3 SQLite files). | The Phase 3 baseline snapshot would contain uncommitted state. | Commit or snapshot before starting (decision N-5). `vibe_coding/phase2_baseline/` is frozen from that state. |
| J-16 | No Python on the audit machine. | Nothing can be run or tested here. | Install Python 3.11 (matching the Dockerfile) or run through Docker. |
| J-17 | The dashboard's two-slot `urlFor`. | New pages need per-silo addresses. | Additive per-silo config. The old keys are still read. |

---

## K. Phase 3 design

### K.1 Requirement 1 — 4–6 related tables per database, entity spread across tables

> **Superseded by what was built (§O).** The design below was the proposal. Implementation changed it in two ways. First, **no column was added to any existing table**: the Phase 1 seeds and a Phase 2 test insert by position, so a new column would have broken them, and keys were added to existing columns instead. Second, the tables follow the examples in prompt P3-1 (item master, inventory, recall notices). The table below is kept for the record.

New items are marked **(new)**. Every new table is derived **deterministically from existing rows**, so links are real rather than invented. For example, terminals come from the distinct `purchase_events.device_id`, warehouses from the distinct `source_warehouse`, and molecules from the distinct `generic_name` + `atc_code`.

**DB1 Retail POS — 3 → 6 tables** (SQLite + matching JSON collections)

| Table | PK | FK(s) | Content |
|---|---|---|---|
| `vendors` | `vendor_id` | – | existing |
| `pos_terminals` **(new)** | `device_id` | `vendor_id → vendors` | model, firmware, installed_on, scanner type (from the distinct `device_id`s) |
| `pharmacists` **(new)** | `pharmacist_id` | `vendor_id → vendors` | name, pharmacy-council reg. no., shift |
| `purchase_events` | `event_id` | `vendor_id → vendors`, **+`device_id → pos_terminals`** (backfilled), **+`pharmacist_id → pharmacists`** (new nullable) | existing |
| `prescriptions` **(new)** | `prescription_id` | `event_id → purchase_events` | prescriber, hospital, short **free-text note** (unstructured) for a subset of sales |
| `scan_anomaly_log` | `anomaly_id` | **+`event_id → purchase_events`** (new nullable) | currently **0 rows**; populated from the flagged `purchase_events` |

Entity spread: a *sale* is spread over `purchase_events` + `pos_terminals` + `pharmacists` + `vendors` + `prescriptions` + `scan_anomaly_log`.

**DB2 Distributor ERP — 4 → 6 tables**

| Table | PK | FK(s) | Content |
|---|---|---|---|
| `distributors` | `distributor_id` | – | existing |
| `warehouses` **(new)** | `warehouse_id` | `distributor_id → distributors` | name, city, cold-storage capacity (from the distinct `source_warehouse`) |
| `distribution_batches` | `batch_id` | `distributor_id → distributors`, **+`source_warehouse_id → warehouses`** | existing |
| `temperature_logs` **(new)** | `reading_id` | `batch_id → distribution_batches` | time-series readings. Values agree with `cold_chain_maintained` (excursions for breached batches) |
| `distributor_vendor_contracts` | `contract_id` | `distributor_id → distributors` | existing |
| `return_log` | `return_id` | **+`batch_id → distribution_batches`** | existing (2 rows; a few more derived from `status='returned'`) |

Entity spread: a *shipment* is spread over batches + warehouse + distributor + temperature readings + returns.

**DB3 Manufacturer Registry — 4 → 6 tables**

| Table | PK | FK(s) | Content |
|---|---|---|---|
| `manufacturers` | `manufacturer_id` | – | existing |
| `manufacturing_sites` **(new)** | `site_id` | `manufacturer_id → manufacturers` | plant address, state, GMP inspection date |
| `molecules` **(new)** | `molecule_id` | – | generic name, ATC code, therapeutic class, cold-chain flag (from the distinct `generic_name`/`atc_code`) |
| `products` | `product_uid` | `manufacturer_id → manufacturers`, **+`molecule_id → molecules`**, **+`site_id → manufacturing_sites`** | existing |
| `batch_release_certs` | `cert_id` | `product_uid → products`, **+`site_id → manufacturing_sites`** | currently **0 rows**; one cert per genuine registered batch. Counterfeits get none, which is a useful signal |
| `authorized_distributors` | `auth_id` | `manufacturer_id → manufacturers` | existing |

Entity spread: a *medicine* is spread over products + molecules + manufacturer + site + release cert + authorisations.

**DB4 Ministry — already 5; enriched to 6**

| Table | Change |
|---|---|
| `ministry_officers`, `complaints`, `ministry_blacklist`, `lab_reports` | unchanged |
| `public_alerts` | **+`blacklist_id → ministry_blacklist`** (new nullable, backfilled by `item_ref`) |
| `inspections` **(new)** | `inspection_id` PK, `officer_id → ministry_officers`, `complaint_id → complaints` (nullable); vendor_ref / site_ref, findings text |

All Phase 1/2 tables, columns and values are preserved.

### K.2 Requirement 2 — databases on different machines, federated query

Target topology (one database per machine; mediator stateless):

```
                  ┌──────────────────────────────────────────────┐
  Browser ──────▶ │  Mediator (machine M)  :8030                   │
  dashboard       │  - parses query, fans out, accumulates context │
                  │  - NO database; in-memory per-query state only │
                  └──────┬──────────┬───────────┬──────────┬───────┘
             HTTP/JSON   │          │           │          │  (parallel, timeouts, circuit breaker)
                 ┌───────▼──┐ ┌─────▼────┐ ┌────▼─────┐ ┌──▼────────────┐
                 │ DB1 node │ │ DB2 node │ │ DB3 node │ │ DB4 node      │
                 │ machine A│ │ machine B│ │ machine C│ │ machine D     │
                 │ :8021    │ │ :8022    │ │ :8023    │ │ :8024 (+:8001)│
                 │ JSON coll│ │ SQLite   │ │ SQLite   │ │ REST+SQLite   │
                 │ + docs   │ │ + docs   │ │ + docs   │ │ bearer auth   │
                 └──────────┘ └──────────┘ └──────────┘ └───────────────┘
```

- **Node = one process + only its own data directory.** `python scripts/run_cluster.py --mode db2` on machine B, with only `db2_distributor_ledger.sqlite` (and DB2's documents) present. A start-up guard refuses to run if other silos are visible (J-1).
- **Mediator** (`--mode mediator`) reads node URLs from `DB1_URL…DB4_URL` or `data/network_topology.json`. It stores nothing permanently. A per-query result cache is optional, in memory, and TTL-bounded. **No centralised database.**
- **Deployment options**, all using the same code:
  1. **4 physical machines + mediator on one of them.** This is the literal requirement. Start each node with its `--mode`, then set the URLs on the mediator.
  2. **2–3 laptops:** several nodes per laptop, each still a separate process with its own data dir and port. Acceptable as a fallback, but the report should name it honestly.
  3. **Docker** `docker-compose.phase3.yml`: 5 containers on a bridge network. Each DB container mounts **only** its own data volume.
  4. **One machine (dev/tests):** `--mode phase3-all` launches the 4 nodes with 4 separate temporary data dirs.
- **Legacy compatibility:** ports 8011/8012/8001 and modes pc1/pc2/all are unchanged. Phase 3 uses new ports (8021–8024, 8030) and a new API prefix `/api/v3/`, so nothing collides.

### K.3 Each database discovers context locally through its FK–PK relationships

Node endpoint: `POST /api/v3/context/discover`

```json
{ "query": "counterfeit Novamox sold in Mumbai last month",
  "seeds": {"item_codes": ["MED-ASALI-001"], "terms": ["novamox","mumbai","counterfeit"],
            "bridge": {"vendor_id": [], "distributor_id": [], "manufacturer_id": []}},
  "max_hops": 2, "row_budget": 200, "round": 1 }
```

Algorithm, the same on every node and **driven by the schema, not hard-coded joins**:

1. **Schema graph.** At start-up the node builds `G = (tables, FK edges)` from `PRAGMA foreign_key_list` (SQLite) or from `nosql_manifest.json` (DB1 collections: reference fields and embedded paths). Edges can be traversed in both directions (child → parent and parent → children).
2. **Seed matching (local only).**
   - item codes, matched exactly or approximately against the node's own key column (`scan_code` / `batch_serial` / `product_uid` / `complaint_item_ref`) using `canonical_code` + `fold` + Phase 2 similarity;
   - query terms against the node's own text and name columns (brand, generic, city, vendor/distributor names), with a per-node vocabulary built at start-up;
   - bridge keys from the mediator's round 2 (`vendor_id`, `distributor_id`, `manufacturer_id`).
   Each seed row gets `seed_score ∈ (0,1]`.
3. **FK traversal (BFS, bounded).** From the seed rows, follow FK edges up to `max_hops`. A reached row's relevance is
   `r(row) = max over paths [ seed_score · Π_edges (λ_hop · w_edge) ] · (1 + α · term_overlap(row, query))`,
   with `λ_hop = 0.6`. `w_edge = 1 / log2(2 + fanout)` penalises hub fan-out: a vendor with 300 sales does not pull in all 300. `α = 0.5`. Per-table caps and the global `row_budget` keep it bounded. Rows below `τ_node = 0.15` are pruned.
4. **Packet.** The node returns:
   - `rows[]` with provenance `{db, table, pk, hop, fk_path:["purchase_events.vendor_id→vendors.vendor_id"], score}`;
   - `terms{}`: weighted context vocabulary extracted from the rows (brand, generic, batch, city, dates);
   - `bridge_keys{}`: values of cross-DB columns found (`destination_vendor_id`, `distributor_ref`, `manufacturer_ref`, item codes);
   - `trace`: SQL / filter statements executed and timings, for the "generated query" demo.

DB4 serves the same endpoint behind its bearer token and REST envelope `{meta, data}`, so it stays a REST source. DB1 runs discovery over JSON collections (a `find` + reference-lookup engine), so it stays a document source.

### K.4 Requirement 3 — accumulating a highly relevant overall context

Mediator `POST /api/v3/federated/query {query, max_hops, top_k, include_documents}`:

1. **Parse** (lightweight, shared helpers): item codes (normaliser), intent keywords (counterfeit / recall / cold chain / expiry / price), place and date expressions. This produces the **seeds only**; the nodes decide relevance locally.
2. **Round 1:** send to all 4 nodes **in parallel** (thread pool, 3 s timeout each, existing circuit-breaker semantics, partial results flagged).
3. **Round 2 (bounded, at most 1 more):** bridge keys found by one node, and not yet given to another node that owns that key, are sent back as seeds. Example: DB3 finds `MFG-001` and authorised `DIST-001`; DB2 then expands from `DIST-001`. Each node still discovers through its own FKs.
4. **Accumulate:**
   - **Entity consolidation** across nodes on the canonical keys (`item_code`, `vendor_id`, `distributor_id`, `manufacturer_id`), using `schema_mapping.json` alias equivalences + Phase 2 approximate matching (with confidence);
   - **Semantic normalisation** (`SemanticTransformer`) of dates, currency and temperature;
   - **Conflict detection** (`conflict_resolver`), with conflicts kept as context items;
   - **Global relevance:** `R(e) = Σ_nodes r_n(e) · corroboration(e) · query_affinity(e)`. `corroboration = 1 + 0.25·(#nodes mentioning e − 1)`. `query_affinity` is term overlap with the original query only (not with the expanded terms), which stops topic drift;
   - **Pruning:** keep the top-k entities per type and drop rows reached only through round-2 expansion with `R < τ_global` (0.25).
5. **Verdict attachment:** for each resolved item code, the existing `verify()` runs through the **remote wrappers**, so the vetoes, score, audit and lifecycle are unchanged.
6. **Output — `QueryContext`:** entities (with per-DB facts and provenance), FK paths, conflicts, weighted context terms, bridge-key graph, per-node trace and timings, and relevance metrics.

### K.5 Requirement 4 — search unstructured data with the discovered context

**Corpus** (`data/generate_documents.py`, deterministic, about 300–500 documents). Each document is stored on its **owning node**, so no central store is needed:

| Owner node | Document types |
|---|---|
| DB4 (Ministry) | Recall / NSQ monthly bulletins, drug-alert circulars, inspection reports, pharmacovigilance case narratives, press releases. Also indexes the existing complaint descriptions, lab findings and alert messages |
| DB3 (Registry) | Package inserts / monographs per molecule, GMP inspection summaries per site, batch-release notes |
| DB2 (Distributor) | Cold-chain excursion incident reports, warehouse audit notes, return/destruction memos |
| DB1 (Retail) | Pharmacy incident notes, label OCR texts (existing), prescription notes |

The documents are realistic and noisy: misspelt brands, codes embedded in prose (`MED-ASAL1-OO7`), different date formats, some documents about look-alike products (hard negatives). Each document has a metadata header (`doc_id`, owner, date, type), and the **ground truth** of which entities it truly concerns is stored for evaluation.

**Search:** `POST /api/v3/docs/search` on each document-holding node, fanned out by the mediator.

- Index: pure-Python **BM25** inverted index built at node start-up and rebuilt on file change (Phase 2's mtime-stamp pattern).
- Query: `q = original query terms (weight 1.0) ∪ context terms from §K.4 (weight ∝ R)`. This is context-driven query expansion.
- Score: `BM25(q) + β·entity_match + γ·recency`. `entity_match` covers codes, batch numbers and brand/generic names from the context found in the document. Codes are matched approximately with Phase 2 `fold()` + similarity, so a circular quoting `MED-ASAL1-OO7` still links to `MED-ASALI-007`.
- Snippets with highlighted matched terms.

**Integration with structured results.** For each top document, entity mentions are extracted and **linked to `QueryContext` entities**. Each entity in the final answer carries: structured facts (by DB and table) + supporting documents (score, snippet, which context terms matched) + conflicts between the documents and the structured data. An example: a recall circular exists for a batch that DB3 shows as `is_recalled=0`, which is reported through the existing `conflict_resolver` statutory-precedence policy. Documents are **explanatory evidence only by default**. The Phase 1/2 verdict logic is unchanged, unless you decide otherwise (N-3).

### K.6 Requirement 5 — prompt, generated code, modified code

Following the Phase 2 convention exactly:

- `vibe_coding/phase2_baseline/`: snapshot of every file Phase 3 will touch, taken **before** any change.
- `vibe_coding/PROMPTS_PHASE3.md`: Prompt 0 (your message, verbatim) + component prompts P3-1…P3-n + later prompts.
- `vibe_coding/generated_v0_phase3/`: the code exactly as first generated, before it is run.
- `vibe_coding/CHANGES_PHASE3.md`: every later change, with what was observed, what changed, and where.
- `vibe_coding/rounds/17-…`: one folder per follow-up prompt (ROUND.md, FILES.txt, before/).
- `make_diff_report.py` parameterised to build `dashboard/vibe/phase3.html`: prompt → generated → highlighted diff.

---

## L. Step-by-step implementation plan

Each step ends with a checkpoint that must pass before moving on.

| Step | Work | Files | Checkpoint |
|---|---|---|---|
| **0. Freeze** | Commit/snapshot the current state; copy the files to be touched into `vibe_coding/phase2_baseline/`; write Prompt 0; install Python 3.11 | `vibe_coding/` | Existing 28 tests pass; the 20 curated items' verdicts and scores recorded as the regression baseline |
| **1. Schema** | Append the Phase 3 DDL; write the idempotent `migrate_phase3.py` | `schema/*.sql`, `scripts/migrate_phase3.py` | Migration run twice is a no-op; Phase 1 verdicts unchanged; 28 tests pass |
| **2. Seed / backfill** | `data/seed_phase3.py`: derive terminals, pharmacists, prescriptions, warehouses, temperature logs, sites, molecules, certs, inspections; backfill the new FK columns; extend `sync_collection` with the new DB1 collections + `nosql_manifest.json` | `data/`, `data/nosql_store/` | Each DB has 6 tables with declared FKs; FK coverage report (% backfilled); Phase 2 benchmark numbers unchanged |
| **3. Schema graph + local discovery** | `integration/federation/schema_graph.py`, `discovery_sql.py`, `discovery_nosql.py`, `relevance.py` | new | Unit tests: graph matches `PRAGMA`; BFS respects hops, budget and fan-out penalty; deterministic output |
| **4. Per-DB node servers** | `api/node_db.py --db dbN` (threading, own-data guard, `/api/v3/node/info`, `/schema/graph`, `/context/discover`, `/resolve` on DB3); DB4 routes in `ministry_service.py` with bearer auth + `--host`; `run_cluster.py` modes; `distributed_config.py` slots | `api/`, `scripts/`, `integration/distributed_config.py` | 4 nodes in 4 separate temp dirs; each answers discover; a node refuses to start with foreign DB files present |
| **5. Mediator + accumulator** | `integration/federation/query_parser.py`, `accumulator.py`, `federated_mediator.py`; `api/mediator_service.py` (`/api/v3/federated/query`) | new | End-to-end query across 4 processes; trace shows FK paths per node; one node killed gives a partial result plus a circuit-breaker flag |
| **6. Remote wrappers** | `integration/wrappers/remote_wrapper.py`; selection in `resolver.py`; REST fallback disabled in remote mode | `integration/` | `verify()` in remote mode gives **identical** verdicts and scores to local mode for all 20 curated items |
| **7. Documents** | `data/generate_documents.py` (+ ground truth); `integration/federation/doc_index.py` (BM25), `doc_search.py`, `doc_linker.py`; `/api/v3/docs/search` | `data/unstructured/`, new | Search returns ranked documents with snippets; noisy-code documents link to the correct entity |
| **8. Integration** | Merge documents into `QueryContext`; document-versus-structure conflicts through `conflict_resolver` | `accumulator.py` | Integrated JSON answer for the demo queries (§M) |
| **9. Dashboard** | `dashboard/federated.html` + `federated.js`; per-silo config in `cluster.js`; Explorer metadata | `dashboard/`, `db_explorer.py` | Page shows query → per-node discovery → context → documents → verdict; works from another machine's browser |
| **10. Deployment** | `docker-compose.phase3.yml`, `.dockerignore`; RUNNING.md Phase 3 section with a 4-machine walkthrough (IP discovery, firewall, `DB*_URL` env) | root | `docker compose -f docker-compose.phase3.yml up`, then a query succeeds; `docker exec` shows each container holding only its own DB |
| **11. Evaluation + docs** | `tests/test_phase3_*.py`; `scripts/eval_phase3.py`; `PHASE3.md` write-up; vibe-coding diff page | `tests/`, `scripts/`, `vibe_coding/` | All old + new tests pass; metrics table produced; `dashboard/vibe/phase3.html` generated |

Estimated new code: about 2,500–3,500 lines of Python plus about 600 lines of JS/HTML. Modifications to existing files stay small and additive.

---

## M. Testing and evaluation

**Regression (Phase 1/2 preservation)**
- The existing 28 tests pass after every step.
- All 20 curated items: verdict, score and veto codes identical before and after (local mode) and between local and remote modes.
- Phase 2 benchmark (`benchmark_results.json`) unchanged after migration and seeding.
- Legacy `--mode pc1/pc2/all`, replication and the dashboard pages work unchanged.

**Phase 3 functional tests**
- Every DB has ≥ 4 (target 6) tables with declared FKs, and an entity is spread across them.
- A node started with another silo's file present refuses to start.
- Discovery respects `max_hops`, `row_budget` and the fan-out penalty, and is deterministic.
- Federation works with one node down (partial result, flagged).
- DB4 discovery requires the bearer token (401 without it).

**Relevance evaluation** (`scripts/eval_phase3.py`, about 20 labelled queries)

Example demo queries:
1. `MED-ASALI-009`: cold-chain breach (DB2 temperature logs → DB3 molecule cold-chain flag → DB2 excursion report document).
2. `counterfeit Novamox in Mumbai`: no code given; context found from brand and city.
3. `Coughcure syrup recall diethylene glycol`: DB3 recall + DB4 lab report + DB4 recall circular.
4. `MED-ASAL1-OO7`: noisy code; Phase 2 matching at the seed stage.
5. `which pharmacies got batches from DIST-003 that later had complaints`: needs round-2 bridge keys DB2 → DB1 / DB4.

Metrics: context precision@k and recall against labelled relevant entities; document nDCG@10 / P@5. Each is compared with ablations: **(a)** seeds only, no FK expansion; **(b)** FK expansion without relevance pruning; **(c)** document search with the raw query only, without context expansion. The expected result, which is the argument for "highly relevant context", is that FK expansion raises recall, pruning keeps precision, and context expansion raises document nDCG.

---

## N. Decisions needed before implementation

1. **Machines.** How many physical machines can you use for the demo: 4 (one per DB, as the requirement says), or 2–3 plus Docker? The code supports all of these; only the RUNNING.md walkthrough and demo script change.
2. **Where documents live.** *Recommended:* each document lives with its owning node (§K.5), which fits the federated design with no central store. *Alternative:* a fifth "document repository" node, which is simpler to explain but adds a sixth process.
3. **Documents and the verdict.** *Recommended:* documents are explanatory evidence only, and Phase 1/2 verdicts are unchanged. *Alternative:* add an optional, off-by-default soft signal (for example, −10 for a recall circular naming the batch).
4. **Nested old clone `Project2_Asali_Nakali/Project2_Asali_Nakali/`.** Leave untouched and exclude it from Docker (recommended), or remove it? Removal is not reversible from the outer repo.
5. **Uncommitted changes.** Five data files are modified in the working tree. Should they be committed as-is before the Phase 3 baseline snapshot is taken?
6. **New ports and prefix.** Is it acceptable to use 8021–8024 / 8030 and `/api/v3/`, keeping all existing ports and routes?

### N-Approved — decisions taken (prompt P3-0)

| # | Decision |
|---|---|
| N-1 | **Two physical machines with Docker**, two database services per machine; GAV mediator and federated coordinator on Machine 1. Each database runs its own queries and context discovery. Documented as a two-machine deployment. |
| N-2 | Documents are stored **with the source that owns them**; each source has its own storage and retrieval; the mediator aggregates. |
| N-3 | Documents are **explanatory only** and never change the ASALI/NAKALI verdict. |
| N-4 | The nested old clone is left untouched and excluded from Docker build contexts. |
| N-5 | The five modified data files were checked and committed separately (`857d932`, branch `phase3`). They removed leftover manual test registrations `MED-shagun-190` and `MED-sam-001`, restoring the documented 1,647 / 427 / 207 baseline. |
| N-6 | Ports 8021–8024 (DB1–DB4) and 8030 (coordinator) approved; none in use. New endpoints under `/api/v3/`. |

Tooling installed: Python 3.11.9 (`%LOCALAPPDATA%\Programs\Python\Python311\python.exe`) and Docker Desktop 4.99. **Docker's engine still needs WSL2**, which needs an administrator `wsl --install --no-distribution` and a restart.

---

## O. Implementation log

### O.1 Requirement 1 — related tables (completed)

**Rule followed: no existing column was added, removed, renamed or retyped, and no existing row was changed.** The Phase 1 seeds (`seed_db1..4.py`), the Phase 2 generator and one Phase 2 test insert into the original tables **by position** (`INSERT INTO products VALUES (?,?,…)`), so a new column would have broken the rebuild. Relationships were added in two ways:
- **New tables** whose foreign keys point at existing primary keys.
- **Foreign-key constraints on existing columns** whose values are clean: `purchase_events.device_id`, `(distribution_batches.distributor_id, source_warehouse)`, `products.generic_name`, `ministry_officers.department` and `public_alerts.issued_by`. SQLite can only add a constraint by rebuilding the table, so the migration rebuilds it and checks the rows are identical.

#### Tables per database (live counts after migration)

| DB | Tables (new in **bold**) | FK-connected |
|---|---|---|
| DB1 Retail POS | vendors 38 (Pharmacy), **pos_terminals 62**, purchase_events 1,647 (Sales; one row per item sold), **retail_medicines 206** (Medicine / item master), **stock_receipts 358** (goods received), **inventory 345**, scan_anomaly_log 0 | 6 of 7 |
| DB2 Distributor ERP | distributors 9, **warehouses 21**, distribution_batches 427 (Shipment lines), **cold_chain_loggers 64**, **temperature_logs 884**, distributor_vendor_contracts 44, return_log 2 | 6 of 7 |
| DB3 Manufacturer Registry | manufacturers 10, **molecules 42** (Medicine), products 207 (registered Batch), **manufacturing_sites 20**, **production_records 207**, batch_release_certs 207 (Quality certificates; was empty), authorized_distributors 54 | 7 of 7 |
| DB4 Ministry Reports | **regulatory_authorities 8**, ministry_officers 5, complaints 149, ministry_blacklist 9, lab_reports 3, public_alerts 3, **recall_notices 3** | 7 of 7 |

#### Foreign keys (as reported by `PRAGMA foreign_key_list`)

- **DB1**
  - `pos_terminals.vendor_id → vendors`
  - `purchase_events.vendor_id → vendors` and **`purchase_events.device_id → pos_terminals`**
  - `stock_receipts.vendor_id → vendors`, `stock_receipts.item_code → retail_medicines`
  - `inventory.vendor_id → vendors`, `inventory.item_code → retail_medicines`, `inventory.last_receipt_id → stock_receipts`
- **DB2**
  - `warehouses.distributor_id → distributors`
  - `distribution_batches.distributor_id → distributors` and **composite `(distributor_id, source_warehouse) → warehouses(distributor_id, warehouse_name)`**
  - `cold_chain_loggers.batch_id → distribution_batches`
  - `temperature_logs.logger_id → cold_chain_loggers`
  - `distributor_vendor_contracts.distributor_id → distributors`
- **DB3**
  - `products.manufacturer_id → manufacturers` and **`products.generic_name → molecules(generic_name)`**
  - `manufacturing_sites.manufacturer_id → manufacturers`
  - `production_records.product_uid → products`, `production_records.site_id → manufacturing_sites`
  - `batch_release_certs.product_uid → products`
  - `authorized_distributors.manufacturer_id → manufacturers`
- **DB4**
  - **`ministry_officers.department → regulatory_authorities(authority_name)`**
  - **`public_alerts.issued_by → regulatory_authorities(authority_name)`**
  - `regulatory_authorities.parent_authority_id → regulatory_authorities` (the government hierarchy)
  - `complaints.assigned_officer_id → ministry_officers`
  - `ministry_blacklist.complaint_id → complaints`, `lab_reports.complaint_id → complaints`
  - `recall_notices`: `→ regulatory_authorities`, `→ ministry_officers`, `→ complaints`, `→ lab_reports`, `→ public_alerts`

#### Deliberately **not** foreign keys

These columns are cross-database business identifiers, or values Phase 2 deliberately corrupts:
- `purchase_events.scan_code`, `distribution_batches.batch_serial`, `complaints.complaint_item_ref`: noisy or counterfeit codes. Sales join the item master on `scan_code = item_code`.
- `stock_receipts.supplier_dispatch_ref` / `supplier_distributor_id`: DB2 ids.
- `retail_medicines.manufacturer_id`, `recall_notices.manufacturer_ref` / `batch_ref` / `item_ref`: DB3 ids.
- `distribution_batches.destination_vendor_id`: a DB1 id.

These identifiers are what Requirement 2 federates on. DB4 keeps **no medicine master**: it refers to medicines by the reference written on the complaint or order, and DB3 is the register of record. `return_log` and `scan_anomaly_log` keep their Phase 1 shape and link only by item code.

#### How each source keeps its technology

- **DB2 and DB3:** SQLite, unchanged in kind.
- **DB4:** still SQLite behind the REST service; the new tables will be exposed through `/api/v3/` in Requirement 2.
- **DB1 (NoSQL):** SQLite stays authoritative for writes, as in Phase 1/2. Each new entity is also mirrored as **its own JSON collection** in `data/nosql_store/`: `db1_vendors.json`, `db1_pos_terminals.json`, `db1_retail_medicines.json`, `db1_stock_receipts.json` and `db1_inventory.json`. The links between collections are **document references declared in `db1_collections.json`**, explicitly marked as not SQL foreign keys, and checked by `nosql_store.check_references()`. `db1_retail_pos.json` keeps its exact shape (byte-identical after migration). The collections are rebuilt on every DB1 write by the existing `sync_collection()`.

#### Integrity triggers

Phase 1/2 code writes with FK enforcement off, which is deliberate, because it stores noisy references. So a legacy write that names an unknown terminal, warehouse, molecule or authority **registers it** (`registration_status = 'auto_registered'`) instead of leaving a dangling key. There are 10 triggers in total, each covered by a test.

#### Files

| New | Purpose |
|---|---|
| `integration/federation/schema_catalog.py` | Tables, PKs, FKs (composite included) and integrity checks, read from the file itself |
| `integration/federation/migrate.py`, `scripts/migrate_phase3.py` | In-place, idempotent migration: create missing tables, rebuild tables that gained FKs and check their rows, refuse on column drift |
| `data/seed_phase3.py` | Deterministic derivation of every new row from existing rows |
| `integration/federation/nosql_store.py` | DB1 JSON collections, manifest and reference checker |
| `integration/federation/medicine_views.py` | Per-source multi-table joins (data-access functions) |
| `integration/federation/inspect.py` | Validation report: `python -m integration.federation.inspect [--db dbN]` |
| `tests/test_phase3_schema.py` | 23 tests |

Modified: `schema/schema_db1..4.sql`, `create_databases.py` (prints table counts), `scripts/rebuild_data.py` (step 3b), `data/seed_nosql_db1.py` (writes the collections), `integration/db_explorer.py` (new tables in the Explorer), `tests/test_uncertainty.py` (fixture seeds Phase 3, so Phase 2 is tested against the Phase 3 schema). Prompts and changes: `vibe_coding/PROMPTS_PHASE3.md`, `CHANGES_PHASE3.md`, `phase2_baseline/`, `generated_v0_phase3/`.

#### Validation results

| Check | Result |
|---|---|
| Phase 1/2 tables after migration versus commit `857d932` | **16 of 16 identical**, columns and rows |
| Second migration run | Created 0, rebuilt 0 (idempotent) |
| Migrated schema versus fresh build from `schema/` | Identical columns and FKs |
| `PRAGMA integrity_check` | `ok` on all four |
| `PRAGMA foreign_key_check` | **0 violations in DB2, DB3, DB4.** DB1: 30 rows on `purchase_events.vendor_id → vendors`, pre-existing Phase 2 noise (`vnd-10`, `VND 11`) that the cleanser repairs. **No Phase 3 key is violated.** |
| JSON document references | All resolve, except the same 30 noisy vendor ids in scan documents |
| Join demos | MED-ASALI-009 through 4 DB1 tables, 5 DB2 tables (a cold-chain breach shows 119 excursion readings overall), 6 DB3 tables; MED-RECALL-001 through 7 DB4 tables |
| Phase 2 suite (`test_uncertainty` + `test_replication`) | **28/28 OK** before and after; the after run builds from the Phase 3 schema with Phase 3 data |
| Phase 3 suite | **23/23 OK** |
| Explorer, Phase 1 resolver, Phase 2 matcher | Explorer lists and browses the new tables; `resolve()` reaches DB1–DB4; `MED-ASAL1-OO9` still auto-links to MED-ASALI-009 |
| Verdict regression (`verify()` for 218 items: the 20 curated, all 207 registered and 6 noisy or fake codes, on copies of the project before and after) | **218 of 218 identical** verdict, score, vetoes, coverage and lifecycle (198 ASALI, 4 SUSPICIOUS, 16 NAKALI). Filling the previously empty `batch_release_certs` does not change any verdict. |

#### Known limitations

- Deriving the Phase 3 rows reads DB3 (and, for DB1, DB2) **offline at seed time**, as the Phase 2 generator already does. On the two-machine deployment the databases are seeded once and each file is shipped to its host; no running service reads another database.
- `FEDERATED_REGISTER` (Explorer) still writes only the Phase 1 tables. The triggers keep its rows consistent, but it does not create item-master or inventory rows for the new medicine.
- `lab_reports` and `recall_notices` are small (3 rows each) because they are tied to the real recall cases. They are not padded with invented cases.

### O.2 Requirement 2 — distributed services and federated queries (implemented; multi-machine run pending)

#### What runs where

| Component | Process | Holds | Speaks |
|---|---|---|---|
| DB1 Retail POS | `api/node_db.py --db db1` :8021 | its SQLite file + its JSON collections, nothing else | document queries (`db.<collection>.find(...)`) over its collections |
| DB2 Distributor ERP | `api/node_db.py --db db2` :8022 | `db2_distributor_ledger.sqlite` | parameterised SQL |
| DB3 Manufacturer Registry | `api/node_db.py --db db3` :8023 | `db3_manufacturer_registry.sqlite` | parameterised SQL |
| DB4 Ministry Reports | `api/node_db.py --db db4` :8024 | `db4_ministry_reports.sqlite` | SQL, answering in its REST envelope `{meta, data}`; Phase 1 `/api/v1/*` kept |
| Coordinator | `api/coordinator_service.py` :8030 | no database (only its own audit ledger) | HTTP to the four services |

Approved two-machine layout: **Machine 1 = DB1, DB2 and the coordinator; Machine 2 = DB3 and DB4** (`deploy/docker-compose.machine1.yml` / `machine2.yml`, or `scripts/run_federation.py --only ...`). Step-by-step instructions are in `deploy/README.md`.

#### Database service interface (each service, on its own machine)

- `GET /health`: identity, machine label, physical host, pid, data files, isolation status, and the address the caller was seen from. No token.
- `GET /api/v3/schema`: tables or collections, primary keys, and FK–PK relationships read from the file (`PRAGMA foreign_key_list`); for DB1, the declared document references, plus its authoritative SQLite schema.
- `POST /api/v3/subquery`: receives a **declarative** subquery (target, conditions, operator, limit, expansion). It checks every name against its own schema, so raw SQL is never accepted. It compiles the subquery to its native language, executes it, and then **discovers context itself**, walking its own FK graph breadth-first in both directions. Rows are scored by hop decay (0.6 per hop), fan-out and query-term overlap. It returns the matches, the context rows with their FK path, the business identifiers it shares with other databases, the native query, and timings.
- `POST /api/v3/context/discover`: the same discovery, returning context only.
- `POST /api/v3/legacy/lookup` and `GET /api/v3/legacy/catalog`: the Phase 1 wrapper result and entity-resolver catalogue, computed on that machine.

Other properties of the services:
- **Credentials:** each service requires its own bearer token (`ASALI_DBn_TOKEN`) and refuses to start without one. No address or token is in the code (`integration/federation/runtime.py`). `deploy/local.env` holds loopback-only development tokens; the machine profiles are `.example` templates, and the real files are git-ignored.
- **Isolation guard:** a service refuses to start if its data directory shows another database's file. `scripts/prepare_node_data.py` builds the per-database directories.
- **Concurrency:** `ThreadingHTTPServer`, unlike the single-threaded Phase 1 nodes.

#### Coordinator pipeline (built on the GAV mediator)

`integration/federation/coordinator.py`, also reachable as `GavQueryMediator.execute_federated_query()`:

1. **Understand** (`query_parser.py`, rule-based, standard library only):
   - medicine codes, including damaged ones;
   - batch numbers, vendor, distributor and manufacturer ids;
   - nine intents: authenticity, cold chain, recall, complaint, lab, stock, sales, shipment, manufacturing;
   - free terms.

   Every decision is listed in the output. The coordinator holds no product, pharmacy or city list; terms are matched by each database against its own columns.
2. **Route:** pick the databases that can answer, each with its reason. Those not queried are listed, also with a reason.
3. **Unfold (GAV):** `schema_mapping.json` gained a `phase3` section. It defines each global concept (item code, batch number, vendor, distributor, manufacturer, free text) as views over each source's own tables and fields. One subquery is generated per (database, view); identifiers that share a table are combined with AND.
4. **Send** to all routed databases in parallel, each with its own token and timeout.
5. **Collect** with provenance: database, pid and host that executed it, native query, FK path of every context row. Status per database: ok, timeout, unreachable, auth_failed, refused or partial. One dead database never blocks the others; after its first timeout, its remaining subqueries are skipped.
6. **Combine** on the shared business identifiers into three lists, kept separate: matched medicines, medicines found only in discovered context, and cross-source links such as `distributor_id=DIST-001` held by DB1, DB2 and DB3.
7. **Verify:** for each medicine code, the **unchanged Phase 1 pipeline** (GAV resolver → GlobalItemHistory → conflict resolver → anomaly detector → hard vetoes → trust engine) runs over `RemoteSourceWrapper`s, which satisfy the Phase 1 `BaseWrapper` contract over HTTP.

   **A verdict is withheld unless all four databases answered**, because the vetoes read a missing source as missing evidence: an unreachable registry would look like a phantom serial. One-edit "near misses" are never verified in place of the typed code, so a counterfeit printed one character away from a real code still meets the phantom-serial veto.

#### Changes to existing modules

All gated by `ASALI_FEDERATION=remote`; the local Phase 1/2 behaviour is byte-for-byte the default.

| Module | In federated mode |
|---|---|
| `resolver.py` | the four wrappers are `RemoteSourceWrapper`s; the rest is unchanged |
| `entity_resolver.py` | the catalogue comes from the DB3/DB2 services; their data version drives the cache |
| `lifecycle_state.py` | state inferred, not stored. The verdict is unchanged, because `infer_and_sync` always returns the inferred state; before this change, opening DB3's path on the coordinator would have created an empty registry file |
| `verify_item.py` | no automatic complaint filing (read-only query; DB4 is elsewhere: `auto_report_due` says one is due); no Phase 2 "did you mean" hint (it reads all four silos locally) |

In both modes, the wrappers, the audit chain, `ministry_reporter` and `ministry_service` follow `ASALI_DB_DIR` / `ASALI_NOSQL_FILE`, and the DB4 Phase 1 address and token are configurable. Defaults are unchanged.

#### Validation (one Windows laptop)

| Check | Result |
|---|---|
| `tests/test_phase3_federation.py` | **16/16 OK**: four separate processes with separate data; isolation guard; token required; schema exposure; injection-proof subqueries; local discovery stays within that database's tables; document-query native language on DB1; look-alike match versus one-edit near miss; routing; end-to-end provenance; unreachable database gives a partial result and `WITHHELD`; slow database gives `timeout` in under 6 s; coordinator creates no database file |
| **Verdict parity, network versus local** | **25 of 25 identical** (verdict, score, vetoes, lifecycle, coverage): the 20 curated items, `MED-ASAL1-OO1`, `BATCH-A001`, `Novamox`, `MED-TOTALLY-FAKE-9999`, `MED-ASALI-999` |
| Phase 2 suite | **28/28 OK** after the changes |
| Phase 3 schema suite | **23/23 OK** after the changes |
| Phase 1/2 local paths | GAV mediator in local mode finds all four sources and arbitrates conflicts; legacy `node_pc1/pc2` and `ministry_service` import and run unchanged |
| Demonstration | `phase3/documentation/evidence/requirement2_local_simulation.txt`: three questions through `scripts/federated_demo.py`, showing the services and their addresses, understanding, routing, per-database subqueries, native execution with FK paths, per-database results, and the combined result with the Phase 1 verdict |
| Compose files | `docker compose config` passes for `docker-compose.local.yml`, `machine1.yml` and `machine2.yml` |

#### Local simulation versus multi-machine: what is and is not shown

Everything above ran on **one machine over loopback**. That demonstrates process and data isolation: separate processes and data directories, a guard that refuses a shared directory, and only HTTP between them. It does **not** demonstrate execution on different machines, and the coordinator says so: `GET /api/v3/federation/nodes` reported `LOCAL_SIMULATION`.

The coordinator classifies each run:
- `LOCAL_SIMULATION`: all services at loopback addresses.
- `SINGLE_HOST_NETWORKED`: network addresses, but one physical host, e.g. Docker on one computer.
- `MULTI_MACHINE`: two or more physical hosts.

It also reports the evidence a genuine two-machine run must show: each service's resolved address, and the address each service saw the coordinator connect *from*. `deploy/README.md` §5 lists the five checks. **Not yet executed:** Layouts B–D (Docker single host, two machines with Docker, two machines without Docker). They need WSL2 (an administrator `wsl --install --no-distribution` and a restart) and a second machine.

#### Known limitations

- Query understanding is keyword- and pattern-based. It is transparent and testable, but it will miss phrasings outside its vocabulary. Anything unrecognised falls back to a free-text query against every database.
- Discovery scoring is deliberately simple (hop decay, fan-out, term overlap); hub expansion can pull in many loosely related rows (e.g. other shipments of the same distributor). Ranking and pruning the accumulated context is **Requirement 3**.
- Federated queries are read-only. Writes (Explorer, cleansing) remain on the Phase 1/2 nodes and replication.

### O.3 SCORE-inspired query context discovery (implemented)

The full algorithm, formulas, parameters and a worked example are in **`phase3/documentation/PHASE3_CONTEXT_DISCOVERY.md`**.

**What changed against §K.3/§K.4 of the plan.** The plan's per-node context step (hop-decayed breadth-first walk) is replaced, as the default, by SCORE's greedy augmentation:
- the result relation R0 is kept whole and its terms are weighted by tf × idf;
- every FK to an unexplored neighbour is actually joined and scored by the new terms it adds, the neighbour's schema affinity to the question, and its fan-out;
- only the single most relevant FK is joined per step, up to `MAX_AUGMENTATION`;
- `TOP_N` terms are returned with provenance.

The plain walk remains as `"method": "bfs"`, the baseline. The aggregation (§K.4) is now `context_aggregator.py`: per-subquery normalisation, deduplication by term key, corroboration across databases, query-match boost, the question's identifiers listed separately as anchors, and a "why relevant" explanation for each term.

| Step of the prompt | Where |
|---|---|
| 1. Query result analysis (all columns kept; column kinds) | `score_context.discover()` → `query_result` |
| 2. Schema graph from real FK–PK relationships | `local_engine` engines (`PRAGMA foreign_key_list`; DB1 document references) → `schema_graph` |
| 3. Terms: text, numeric, categorical, identifiers, dates; tf × idf weights | `extract_terms()` → `result_terms` |
| 4. Iterative FK exploration, FK relevance, MAX_AUGMENTATION, no indiscriminate exploration | `discover()` → `augmentation` (every candidate with its relevance), `joins_performed`, `stop_reason` |
| 5. Ranking with term, database, table, column, score, path, entity ids | `ranked_context` |
| 6. Database-local response | `result.score_context` of `POST /api/v3/subquery`, computed by the database's own service |
| 7. Aggregation in the mediator | `context_aggregator.aggregate()` ← `coordinator.federated_query()` ← `GavQueryMediator.execute_federated_query()` → `query_context` |

**Validation.**

| Check | Result |
|---|---|
| `tests/test_phase3_score.py` | **12/12 OK**: only real FKs joined; MAX_AUGMENTATION and TOP_N respected; the question changes which FK is joined first (cold chain → `cold_chain_loggers`; recall → `ministry_blacklist`/`recall_notices`); tf × idf (`cold_chain_maintained=0` > 5 × `status=delivered`); zero-gain FKs never followed and a high threshold stops exploration; provenance on every term; document-store joins are `$lookup` on declared references; entity matching only chooses R0 (damaged and clean code give identical context); deterministic; aggregation merges identifiers across databases, keeps anchors apart, ranks with reasons |
| `tests/test_phase3_federation.py` | **16/16 OK** (two assertions moved to `method="bfs"`; SCORE expectations added) |
| Phase 2 / Phase 3 schema suites | **28/28**, **23/23 OK** |
| Demonstration | `phase3/documentation/evidence/score_context_demo.txt`: four questions (cold chain, recall, pharmacy stock and sales, shipments between two parties) with initial results, candidates and joins per step, explored and unexplored tables, terms, each database's local context, aggregated context and reasons. Recorded on the local simulation |

**Interpretations to check against the lecture.** The tf × idf weight, the top-5 gain, the affinity and fan-out factors, the decay (0.7) and the thresholds are this implementation's choices (§K and `phase3/documentation/PHASE3_CONTEXT_DISCOVERY.md` §6); the Week-11 L1 slides were not available. All of them are parameters.

### O.4 Context-aware unstructured retrieval and integration (implemented)

The pipeline, formulas and evaluation are in **`phase3/documentation/PHASE3_UNSTRUCTURED_RETRIEVAL.md`**. It follows decisions N-2 (documents stored and searched by the source that owns them, aggregated by the mediator) and N-3 (documents explain; they never change the verdict).

| Step of the prompt | Where |
|---|---|
| 1. Dataset | 303 generated documents in `data/documents/db1..db4/` (8 types; .md / .txt / .html), derived from the structured records, with damaged codes, misspellings, mixed date formats, sibling-batch hard negatives; ground truth for evaluation only. Files, not table rows |
| 2. Ingestion | `doc_store.py`, in each source's service: extract (incl. HTML), clean, chunk (~120 words, 30 overlap), metadata, entities (codes incl. damaged ones; batches; ids; company names via the owner's own DB), BM25 index. Code linkage: 91.6% recall, 95.0% precision vs ground truth |
| 3. Context-aware search | `retrieval.build_search_request()`: question + top context terms + anchor identifiers (1.0) + identifiers found through FK joins (0.5) + names + intents; sent to all four document stores |
| 4. Relevance filtering | `DocStore.search()`: saturated weighted BM25 + entity matches, informative-term gate, different-medicine penalty, document-type prior, mild recency, minimum score |
| 5. Integration | `retrieval.integrated_response()` → `result["integrated"]` A–H; links to structured entities (reliable / probable / weak); verified facts separate from reported information; unverified allegations carry a caution with what the structured records say |
| 6. Output | `scripts/integrated_demo.py`; `phase3/documentation/evidence/integrated_retrieval_demo.txt` (four questions, including the prompt's example with the real BATCH-A009 / Biocon) |

**Validation.**

| Check | Result |
|---|---|
| `tests/test_phase3_documents.py` | **13/13 OK**: all documents ingested with metadata; HTML extraction; date normalisation; chunking; entity extraction against ground truth; documents are files, not rows; the context reaches a document the question alone cannot; different questions give disjoint top-5; sibling batches never returned; common words alone return nothing; a damaged code in a document still links; every result explains itself; unverified complaints marked as allegations, and documents never change the verdict |
| Retrieval evaluation (10 questions) | context vs question alone: P@5 **0.84** vs 0.78, R@10 **1.00** vs 0.93, nDCG **1.00** vs 0.95. The gain is on batch questions (0.80 vs 0.60; 1.00 vs 0.60), where the pack code and manufacturer come from SCORE's FK joins |
| Earlier suites | Phase 2 28/28, schema 23/23, SCORE 12/12, federation 16/16 (incl. network verdict parity) |

**Limitations.** The corpus is synthetic and its ground truth comes from the same generator. Relevance is lexical plus identifiers (no semantic embeddings). Codes damaged beyond scanner look-alikes are deliberately not linked.
