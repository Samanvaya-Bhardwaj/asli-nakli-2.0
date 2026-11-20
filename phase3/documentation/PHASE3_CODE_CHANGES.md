# Phase 3 code changes

**Sources of record.**
- **Original implementation:** commit `857d932`, the clean data baseline committed before any Phase 3 change. The Phase 2 versions of the touched files are also frozen in `vibe_coding/phase2_baseline/`.
- **Exact diffs:** [`PHASE3_CODE_DIFFS.md`](PHASE3_CODE_DIFFS.md), generated from git by `phase3/tools/code_changes.py`. It covers every modified file, every created file, and every new file as first generated against its current version.
- **Prompts and post-generation fixes:** `vibe_coding/PROMPTS_PHASE3.md` (prompts P3-0 … P3-5, verbatim) and `vibe_coding/CHANGES_PHASE3.md` (every change made after generated code was first run, with what was observed).

**Rule followed throughout.** Nothing existing was replaced. Existing modules gained small, additive changes, gated so that Phase 1/2 behaviour stays the default. Most existing source files changed by 1–35 lines; the four schema files gained 76–101 lines each, adding tables and constraints.

---

## 1. Files created

| Area | Files |
|---|---|
| Schema migration and integrity | `integration/federation/schema_catalog.py`, `migrate.py`, `scripts/migrate_phase3.py`, `data/seed_phase3.py` |
| DB1 document side | `integration/federation/nosql_store.py`, `data/nosql_store/db1_{vendors,pos_terminals,retail_medicines,stock_receipts,inventory,collections}.json` |
| Per-database joins / inspection | `integration/federation/medicine_views.py`, `inspect.py` |
| Distributed services | `integration/federation/runtime.py`, `local_engine.py`, `remote.py`, `api/node_db.py`, `api/coordinator_service.py` |
| Federated planning | `integration/federation/query_parser.py`, `coordinator.py` |
| SCORE context | `integration/federation/score_context.py`, `context_aggregator.py` |
| Documents | `data/generate_documents.py`, `data/documents/db1..db4/` (303 files, generated), `integration/federation/doc_store.py`, `retrieval.py` |
| User-facing page | `dashboard/phase3.html` (served by the coordinator at `/`) |
| Deployment | `deploy/local.env`, `deploy/machine{1,2}.env.example`, `deploy/docker-compose.{local,machine1,machine2}.yml`, `deploy/README.md`, `Dockerfile.phase3`, `Dockerfile.phase3.dockerignore`, `.dockerignore`, `scripts/prepare_node_data.py`, `scripts/run_federation.py` |
| Demonstrations / tools | `scripts/federated_demo.py`, `score_demo.py`, `integrated_demo.py`, `phase3_scenarios.py`, `eval_retrieval.py`, `run_phase3_tests.py`, `phase3/tools/check_page_render.mjs`, `phase3/tools/code_changes.py` |
| Tests | `tests/test_phase3_schema.py` (23), `test_phase3_federation.py` (16), `test_phase3_operators.py` (3), `test_phase3_score.py` (12), `test_phase3_documents.py` (13), `test_phase3_end_to_end.py` (9) |
| Documentation | `PHASE3_IMPLEMENTATION_PLAN.md`, `PHASE3_FINAL_REPORT.md`, `phase3/documentation/*`, `vibe_coding/{PROMPTS,CHANGES}_PHASE3.md`, `vibe_coding/phase2_baseline/`, `generated_v0_phase3/`, `rounds/17-*`, `18-*`, `19-*` |

## 2. Existing files modified: original → modified, and why

### Schemas (`schema/schema_db1..4.sql`) and the four databases

- **Original:** 3, 4, 4 and 5 tables; a medicine was mostly a single row per source.
- **Modified:**
  - every database has 7 related tables;
  - no existing column was added or removed;
  - FK constraints were added on existing clean columns: `purchase_events.device_id → pos_terminals`, `(distribution_batches.distributor_id, source_warehouse) → warehouses`, `products.generic_name → molecules`, `ministry_officers.department` and `public_alerts.issued_by → regulatory_authorities`;
  - 10 integrity triggers register a new terminal, warehouse, molecule or authority instead of leaving a dangling key.
- **Why:** Requirement 1. Columns could not be added, because Phase 1 seeds, the Phase 2 generator and a Phase 2 test insert by position. The databases were migrated in place (`scripts/migrate_phase3.py`): all 16 Phase 1/2 tables are identical row for row, and all 218 verdicts are unchanged.

### `integration/resolver.py` (+18 / −4)

```python
# original
WRAPPER_DB1 = NoSqlDocumentWrapper()
WRAPPER_DB2 = SqliteRelationalWrapper("db2_distributor", ...)
...
# modified
FEDERATION_MODE = "remote" if _federation_runtime.remote_mode() else "local"
if FEDERATION_MODE == "remote":
    WRAPPER_DB1 = RemoteSourceWrapper("db1")   # same BaseWrapper contract; the query runs on DB1's machine
    ...
else:
    WRAPPER_DB1 = NoSqlDocumentWrapper()       # Phase 1/2, unchanged
```

**Why:** the Phase 1 pipeline (GlobalItemHistory, conflicts, vetoes, trust score) must run against databases on other machines without changing it.

### `integration/entity_resolver.py` (+34 / −1)

- **Original:** reads the product catalogue from the local DB3 and DB2 files.
- **Modified:** in federated mode, reads the same rows from the DB3 and DB2 services (`/api/v3/legacy/catalog`), and caches them on the services' data version.
- **Why:** on Machine 1 there is no DB3 file. Opening the old path would silently create an empty registry, so every medicine would look like a phantom serial.

### `integration/lifecycle_state.py` (+21 / −1)

- **Original:** reads and writes the `item_lifecycle` ledger inside the local DB3 file.
- **Modified:** in federated mode, no local ledger; the state is still inferred on every call.
- **Why:** same reason as above. `infer_and_sync` returns the inferred state either way, so the verdict is unchanged (verified: network verdicts equal local verdicts).

### `api/verify_item.py` (+11 / −3)

- **Original:** files an automatic ministry complaint for NAKALI items, and offers the Phase 2 "did you mean".
- **Modified:** in federated mode, neither happens: `auto_report_due` says a complaint is due, and `federation_mode` is reported.
- **Why:** a federated query is read-only, and DB4 is on another machine. The Phase 2 suggestion reads all four silos locally. Neither one changes the verdict.

### `integration/mediator.py` (+15)

- **Added:** `GavQueryMediator.execute_federated_query(question, …)` → `coordinator.federated_query`.
- **Why:** Phase 3 is reached through the existing mediator.

### `integration/schema_mapping.json` (+473 / −40; the −40 is re-indentation only, no values changed)

- **Added:** a `phase3` section:
  - global concepts (item code, batch, vendor, distributor, manufacturer, free text) as views over each source;
  - shared business identifiers per table;
  - intent routing.
- **Why:** GAV unfolding of natural-language questions.

### Paths follow `ASALI_DB_DIR` / `ASALI_NOSQL_FILE`

Files: `wrappers/sql_wrapper.py`, `wrappers/nosql_wrapper.py`, `audit_chain.py`, `ministry_reporter.py`, `api/ministry_service.py` (1–3 lines each).

- **Original:** fixed `databases/` paths.
- **Modified:** the environment variable if set, else exactly the old path.
- **Why:** a database service keeps its file in its own data directory.

### `integration/wrappers/rest_wrapper.py`, `api/ministry_service.py` (+6/−2, +8/−6)

- **Added:** DB4 address and token from `ASALI_DB4_REST_URL` / `ASALI_DB4_LEGACY_TOKEN`, with the Phase 1 values as defaults; `offline` skips the HTTP attempt; `--host` for the ministry service.
- **Why:** no hard-coded address or credential (audit item J-4). Also, with the service down, every local verification waited out four HTTP timeouts.

### `integration/db_explorer.py` (+24 / −4)

- **Added:** the Phase 3 tables to the Explorer's table lists, with column descriptions.
- **Why:** the existing dashboard shows the new tables.

### `data/seed_nosql_db1.py` (+7 / −1)

- **Added:** `sync_collection()` also writes DB1's Phase 3 collections and their reference manifest.
- **Why:** DB1 stays a document store for the new entities; `db1_retail_pos.json` keeps its exact shape.

### `create_databases.py`, `scripts/rebuild_data.py`, `tests/test_uncertainty.py` (2–8 lines each)

- `create_databases.py` prints table counts.
- `rebuild_data.py` seeds the Phase 3 tables and generates the documents.
- The Phase 2 test fixture seeds Phase 3 too, so Phase 2 is tested on the Phase 3 schema.

### `README.md`, `RUNNING.md`, `.gitignore`

Pointers to Phase 3; deployment state and real env files ignored.

## 3. Changes to generated code after it ran

The new Phase 3 code was frozen as first generated before it ran:
- `vibe_coding/generated_v0_phase3/`
- `rounds/17-score-context/generated/`
- `rounds/18-document-retrieval/generated/`
- `rounds/19-end-to-end/generated/`

`vibe_coding/CHANGES_PHASE3.md` lists the 21 significant changes made after running it. The ones that mattered most:

| # | Observed | Changed |
|---|---|---|
| 3 | A context query for MED-ASALI-009 matched MED-ASALI-001 (one edit away) and expanded unrelated recalls | `code` matches only exact, formatting and scanner look-alikes; one-edit values are reported as near misses, never used |
| 9 | "cold chain" matched "Apollo Supply **Chain**"; table affinity was all-or-nothing | phrase matching; graded affinity |
| 15 | Recall notices about other medicines came back for a batch question (via "Ltd") | different-medicine penalty also for batches and context codes; company suffixes are not search terms |
| 16 | A queried code became the search words "med" and "nakali" | codes removed from text and matched as entities |
| 20 | The first end-to-end run of the verification scenario **withheld its verdict**: DB1's `eq` operator raised a NameError (HTTP 500) on a code path never exercised before | fixed (`mongo[fld] = val`); `tests/test_phase3_operators.py` now runs every operator on both engines |

There was a gap in the record, noted in rounds 17–18: for files a round modified, the state just before that round was not snapshotted separately. The P3-2 state is `generated_v0_phase3/` plus CHANGES items 3–8.
