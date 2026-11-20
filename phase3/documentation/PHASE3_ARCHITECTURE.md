# Phase 3 architecture

**What Phase 3 adds.** Phase 3 extends the Asali/Nakali GAV mediator from "verify one medicine code across four sources" to "answer a natural-language question". The question goes to four independent database services. Each one:
- runs its own subquery;
- discovers its own context through its foreign keys;
- searches its own documents with the combined context.

**What it keeps.** The Phase 1 verifier and the Phase 2 uncertainty module are used unchanged. Phase 3 calls them; it does not replace them.

## 1. Components and where they run

```
                              MACHINE 1                                                      MACHINE 2
 ┌──────────────────────────────────────────────────────────────────────────┐   ┌──────────────────────────────┐
 │ Browser ──> coordinator  :8030    api/coordinator_service.py              │   │                              │
 │             page (dashboard/phase3.html), /api/v3/federated/query          │   │                              │
 │             holds NO database (only its own audit ledger)                  │   │                              │
 │   ┌──────────────────────────────────────────────────────────────────┐     │   │                              │
 │   │ GAV mediator (integration/mediator.py -> federation/coordinator.py)│    │   │                              │
 │   │  query_parser  -> route -> GAV unfold (schema_mapping.json phase3)  │    │   │                              │
 │   │  parallel send (remote.NodeClient, one bearer token per database)   │    │   │                              │
 │   │  context_aggregator  -> retrieval (search request, merge, A-H)      │    │   │                              │
 │   │  Phase 1 verify() over RemoteSourceWrapper x4 (unchanged engines)   │    │   │                              │
 │   └──────────────────────────────────────────────────────────────────┘     │   │                              │
 │          │ HTTP                │ HTTP                                       │   │                              │
 │   DB1 service :8021      DB2 service :8022                                  │   │ DB3 service :8023            │
 │   api/node_db.py         api/node_db.py                                     │HTTP│ api/node_db.py              │
 │   JSON collections       SQLite ERP                                         │<-->│ SQLite registry             │
 │   (+ SQLite master)      + documents                                        │   │ + documents                  │
 │   + documents                                                               │   │ DB4 service :8024            │
 │                                                                             │   │ REST envelope over SQLite    │
 │                                                                             │   │ + documents                  │
 └──────────────────────────────────────────────────────────────────────────┘   └──────────────────────────────┘
```

Each database service (`api/node_db.py --db dbN`) runs `integration/federation/local_engine.py`, `score_context.py` and `doc_store.py` over **its own** data directory, and it refuses to start if it can see another database's file. Its endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /health` | identity and machine (no token) |
| `GET /api/v3/schema` | tables, keys and FK–PK relationships |
| `POST /api/v3/subquery` | execute a subquery locally and discover context |
| `POST /api/v3/context/discover` | context discovery only |
| `POST /api/v3/documents/search` | search this source's documents |
| `GET /api/v3/documents/stats` | document-store statistics |
| `POST /api/v3/legacy/lookup`, `GET /api/v3/legacy/catalog` | the Phase 1 wrapper contract, answered on that machine |

| Database | Paradigm kept from Phase 1/2 | Phase 3 tables (7 each) | Documents it owns |
|---|---|---|---|
| DB1 Retail POS | JSON document collections; SQLite authoritative for writes | vendors, pos_terminals, retail_medicines, purchase_events, stock_receipts, inventory, scan_anomaly_log | pharmacy incident reports |
| DB2 Distributor ERP | relational SQLite | distributors, warehouses, distribution_batches, cold_chain_loggers, temperature_logs, contracts, return_log | shipment notes, cold-chain incident reports |
| DB3 Manufacturer Registry | relational SQLite | manufacturers, molecules, products, manufacturing_sites, production_records, batch_release_certs, authorized_distributors | quality reviews, batch inspections, product safety documents |
| DB4 Ministry Reports | REST microservice over SQLite (answers in `{meta, data}`) | regulatory_authorities, ministry_officers, complaints, ministry_blacklist, lab_reports, public_alerts, recall_notices | recall notices, investigations, complaint letters, drug-alert bulletins |

## 2. One question, end to end

| # | Step | Where | Runs on |
|---|---|---|---|
| 1 | The user types a question on the page | `dashboard/phase3.html` | browser |
| 2 | **Understand**: medicine codes (also damaged), batches, ids, intents, terms | `query_parser.parse` | coordinator |
| 3 | **Route** to the databases that can answer, with reasons; **unfold** each global concept into subqueries in each database's own table and column names | `coordinator.route`, `coordinator.unfold`, `schema_mapping.json` → `phase3` | coordinator |
| 4 | **Send** in parallel over HTTP; status per database (ok / timeout / unreachable / refused / partial) | `coordinator._run_on`, `remote.NodeClient` | coordinator → each database |
| 5 | **Execute locally**: the database checks every name against its own schema and compiles to its native language (parameterised SQL, or `db.<collection>.find(...)` for DB1) | `local_engine.validate`, `SqlEngine/DocEngine.select` | each database |
| 6 | **Discover context**: SCORE over its own FK–PK graph (result relation → tf × idf terms → greedy FK joins, MAX_AUGMENTATION → TOP_N ranked terms with provenance) | `score_context.discover` | each database |
| 7 | **Aggregate** the local contexts: normalise, deduplicate, corroborate, rank, separate the question's own identifiers as anchors | `context_aggregator.aggregate` | coordinator |
| 8 | **Build the document search** from the aggregated context (question + context terms + anchor and context identifiers + names + intents) | `retrieval.build_search_request` | coordinator |
| 9 | **Search documents**: each source ranks its own collection (weighted BM25 + identifier matches, gate, penalties); the coordinator merges | `doc_store.DocStore.search`, `retrieval.search_documents` | each database → coordinator |
| 10 | **Integrate**: A question, B verified facts and per-database results, C local contexts, D aggregated context, E documents with F scores, G provenance and H reasons; the **Phase 1 verdict**, computed by the unchanged verifier over the network (withheld unless all four databases answered) | `retrieval.integrated_response`, `api/verify_item.verify` over `RemoteSourceWrapper` | coordinator |

The same pipeline is reachable from Python as `GavQueryMediator().execute_federated_query(question)`. It runs in a process started with `ASALI_FEDERATION=remote`, which is what the coordinator service is.

## 3. How Phase 3 sits on Phase 1/2

- **GAV mediator.** `schema_mapping.json` keeps its Phase 1 mapping and gains a `phase3` section: global concepts defined as views over each source, the business identifiers each source shares, and intent routing. `GavQueryMediator` gains `execute_federated_query()`.
- **Resolver, GlobalItemHistory, conflict resolver, hard vetoes, trust score, audit** run unchanged. In federated mode the resolver's four wrappers are `RemoteSourceWrapper`s, which satisfy the Phase 1 `BaseWrapper` contract over HTTP: the query runs on the database's machine with the same Phase 1 wrapper code. Verdicts over the network are identical to local verdicts (25 of 25 checked by `tests/test_phase3_federation.py`).
- **Phase 2.**
  - Its standardisation (`canonical_code`) and scanner look-alike folding decide which rows match a damaged code at every database (the `code` operator).
  - Its noise functions damage the codes in the generated documents.
  - Its matcher and cleanser still run on the Phase 1/2 nodes (28/28 tests).
- **Phase 1/2 deployment.** PC1/PC2 (`run_cluster.py`, ports 8011/8012), replication and the dashboard pages are unchanged. Phase 3 is a separate deployment on ports 8021–8024 and 8030. Both run on the same migrated databases: `evidence/legacy_phase1_phase2_check.txt`.

## 4. Distributed deployment

**Configuration** (`integration/federation/runtime.py`). No address or token is in the code. Each machine has an env file:
- `deploy/local.env`: one machine, loopback;
- `deploy/machine1.env.example`: DB1, DB2 and the coordinator;
- `deploy/machine2.env.example`: DB3 and DB4.

Each database has `ASALI_DBn_URL` and `ASALI_DBn_TOKEN`.

**Data per machine.** `scripts/prepare_node_data.py` gives each database a directory holding only its own database, documents and (for DB1) JSON collections. The Docker image (`Dockerfile.phase3`) contains no data, and each container mounts only its own directory, read-only.

**Ways to run it:**
- `scripts/run_federation.py` (local simulation, or `--only db3,db4` on a real machine);
- `deploy/docker-compose.local.yml`;
- `deploy/docker-compose.machine1.yml` and `deploy/docker-compose.machine2.yml`.

**Honesty about where it ran.** `GET /api/v3/federation/nodes` classifies the run as `LOCAL_SIMULATION`, `SINGLE_HOST_NETWORKED` or `MULTI_MACHINE` from the addresses and the hosts the services report. Every service also reports the address it saw the coordinator connect from. Instructions and the checks a real two-machine run must pass are in `deploy/README.md`.

**Status:** only the local simulation has been executed (one Windows laptop). The Docker and two-machine layouts are configured, and the compose files validate, but they have not been run: Docker needs WSL2, which is not installed, and no second machine was available. See `PHASE3_FINAL_REPORT.md`.

## 5. Structured and unstructured integration

**Verified versus reported.** Structured records are *verified facts*: the verdict; registration; blacklist; recall; cold-chain breach; lab result. Each is reported with the table it came from. Documents are *reported information*. Each document carries an evidence status that says who wrote it:
- official notice;
- regulatory finding;
- manufacturer's record;
- distributor's record;
- unverified pharmacy or consumer report.

**Links.** A document is linked to structured entities only through identifiers it actually contains. An exact code is reliable; a scanner look-alike is probable; a name alone is weak.

**Allegations.** An unverified allegation of counterfeiting carries a caution and the structured records' answer, side by side.

**Verdict.** The verdict is computed by the Phase 1 engine before documents are searched, and nothing in the document path can change it.
