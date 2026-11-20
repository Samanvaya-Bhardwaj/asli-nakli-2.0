# Phase 3 final validation report

**Bottom line.** Phase 3 is implemented, and its end-to-end workflow has been **executed and validated as a local simulation**: four database services and the coordinator ran as separate processes with separate data directories, on one Windows laptop, over loopback HTTP. It has **not** been executed on separate machines. That part of Requirement 2 is configured and documented but not demonstrated (§3).

**Where things are.** Every claim below points to a file of evidence produced by running the system, or to a test. Nothing here comes from an un-run step.

| What | Where |
|---|---|
| Evidence | `phase3/documentation/evidence/` |
| Generated walkthrough | `phase3/documentation/PHASE3_DEMONSTRATION.md` |
| Architecture | `phase3/documentation/PHASE3_ARCHITECTURE.md` |
| Context discovery | `phase3/documentation/PHASE3_CONTEXT_DISCOVERY.md` |
| Unstructured retrieval | `phase3/documentation/PHASE3_UNSTRUCTURED_RETRIEVAL.md` |
| Code changes | `phase3/documentation/PHASE3_CODE_CHANGES.md` (+ generated `PHASE3_CODE_DIFFS.md`) |
| Plan and log | `PHASE3_IMPLEMENTATION_PLAN.md` §O |

**Environment of every run:** Windows 11 Home, Python 3.11.9, 18 Nov 2026, branch `phase3`. Phase 3 work is uncommitted.

---

## 1. The user-facing workflow

1. **Start the system.** `python scripts/run_federation.py --env-file deploy/local.env` starts the four database services (ports 8021–8024) and the coordinator (port 8030).
2. **Ask a question.** Open `http://127.0.0.1:8030/` and type a question, or click one of the scenarios. The page shows, from the live response:
   1. what the question asks and which databases are asked, with reasons;
   2. each database's subquery, and the native query it ran;
   3. verified facts and the Phase 1 verdict;
   4. each database's discovered context with FK paths;
   5. the aggregated context;
   6. the document search built from it;
   7. the ranked documents, with scores, provenance, reasons, evidence status and cautions.

   The same pipeline is available as `POST /api/v3/federated/query`, as `GavQueryMediator().execute_federated_query()`, and from the command-line demos.

**Evidence:**
- `tests/test_phase3_end_to_end.py` (9/9) drives exactly this, over HTTP only.
- `phase3/tools/check_page_render.mjs` runs the page's own script against the three real saved responses: 7/7 sections and all documents rendered for each. This checks the page's logic, not its visual appearance; the page has **not** been looked at in a browser in this environment.

## 2. Requirement by requirement

### Requirement 1 — four to five related tables per database, an entity spread across them with PK–FK relationships

| | |
|---|---|
| **Implemented** | Every database has **7 tables** (6–7 linked by foreign keys); a medicine is spread across item master, receipts, inventory and sales (DB1), shipments, warehouses, loggers and readings (DB2), molecule, product, site, production and QC certificate (DB3), and authority, officer, complaint, lab report, alert, blacklist and recall (DB4). FKs were added on existing clean columns; no column was added or removed; 10 integrity triggers. DB1 keeps its document store: the new entities are JSON collections linked by declared **document references** (reported as such, not as SQL foreign keys). Migrated in place, with every Phase 1/2 row kept. |
| **Files** | `schema/schema_db1..4.sql`, `integration/federation/{schema_catalog,migrate,nosql_store,medicine_views,inspect}.py`, `data/seed_phase3.py`, `scripts/migrate_phase3.py` |
| **Evidence** | `python -m integration.federation.inspect` (tables, PKs, FKs, `integrity_check`, one join per database). FK violations: 0 in DB2–DB4; DB1 has 30, all the Phase 2 deliberate mistyped vendor ids, and none on a Phase 3 key. 16/16 Phase 1/2 tables identical after migration. 218/218 verdicts identical before and after (§O.1 of the plan). `evidence/rebuild_from_scratch.txt`: a from-scratch rebuild gives identical rows. |
| **Tests** | `tests/test_phase3_schema.py` **23/23** |
| **Demo** | `python -m integration.federation.inspect` |

### Requirement 2 — databases on different machines; each discovers context with its own FK–PK relationships

| | |
|---|---|
| **Implemented** | One service per database (`api/node_db.py`), each with: only its own data; a refusal to start beside another database's file; its own bearer token; a schema endpoint; injection-proof declarative subqueries compiled to SQL or document queries; local SCORE context discovery. A coordinator built on the GAV mediator parses the question, routes it, unfolds it over the GAV mapping into each database's own vocabulary, and sends the subqueries in parallel with timeouts. Unavailable databases give partial results, and a verdict is withheld when a source is missing. No address or credential is in the code; there are env profiles for one machine and for two machines, Docker files, and step-by-step two-machine instructions. |
| **Files** | `integration/federation/{runtime,local_engine,remote,query_parser,coordinator}.py`, `api/node_db.py`, `api/coordinator_service.py`, `deploy/*`, `Dockerfile.phase3`, `scripts/{prepare_node_data,run_federation}.py` |
| **Evidence** | `evidence/requirement2_local_simulation.txt`, `evidence/nodes.json` (the coordinator's own classification: `LOCAL_SIMULATION`). Verdicts over the network equal local verdicts for 25/25 codes. |
| **Tests** | `tests/test_phase3_federation.py` **16/16**, `tests/test_phase3_operators.py` **3/3**, `tests/test_phase3_end_to_end.py` **9/9** |
| **Demo** | `deploy/README.md` §1 (local) and §3–§5 (two machines) |
| **NOT DONE** | **Execution on different machines.** Only the local simulation has run. Docker (Layouts B and C) has not run: Docker Desktop is installed but its engine needs WSL2, which needs an administrator install and a restart. A second machine was not available. The compose files pass `docker compose config`; nothing more is claimed. To close this item: run `deploy/README.md` §3 or §4 on two machines and keep the output of `GET /api/v3/federation/nodes` showing `MULTI_MACHINE` and the `seen_client` addresses (§5 of that file). |

### Requirement 3 — accumulate the context discovered by the databases; highly relevant to the question

| | |
|---|---|
| **Implemented** | SCORE-inspired, inside each database. The result relation is kept whole. Terms are weighted by tf × idf over text, categorical, identifier, date and numeric attributes. Exploration is greedy over real FK joins: each candidate FK is joined and scored by the new terms it adds, the table's schema affinity to the question and its fan-out. The single best FK is followed at each step, up to `MAX_AUGMENTATION`, and the `TOP_N` terms are returned with database, table, column, FK path and entity ids. The mediator aggregates the local contexts: normalised, deduplicated across databases, corroboration and query-match boosts, the question's own identifiers kept apart as anchors, and a reason for every term. |
| **Files** | `integration/federation/score_context.py`, `context_aggregator.py`, `coordinator.py` |
| **Evidence** | `evidence/score_context_demo.txt` (four questions: candidates per step, joins, stop reasons, local and aggregated context); `PHASE3_DEMONSTRATION.md` §4–6 for three more |
| **Tests** | `tests/test_phase3_score.py` **12/12** (real FKs only; limits; the question changes the first join; tf × idf ranking; zero-gain FKs never followed; provenance; document store; entity matching separate from context; deterministic; aggregation) |
| **Caveat** | The Week-11 L1 slides were not available. The formulas (tf × idf, top-5 gain, affinity, fan-out, decay, thresholds) are this implementation's interpretation, are all parameters, and should be checked against the lecture (`PHASE3_CONTEXT_DISCOVERY.md` §6). |

### Requirement 4 — use the context to search unstructured data; integrate documents with structured results

| | |
|---|---|
| **Implemented** | **Corpus:** 303 generated documents (8 types; .md/.txt/.html), derived from the structured records, stored as files with their owning source, not in any table. **Ingestion in each source:** text extraction, cleaning, date normalisation, chunking, metadata, entity extraction (codes, including damaged ones; batches; ids; company names) and a BM25 index. **Search request built from the aggregated context:** question + context terms + anchor and context identifiers + names + intents. **Ranking:** saturated weighted BM25 + identifier matches; a gate against common-word matches; a different-medicine penalty; document type; recency. **Integrated answer A–H:** verified facts kept apart from reported information; evidence status per document; links to structured entities with reliability; a caution on unverified allegations. Documents never change the verdict. |
| **Files** | `data/generate_documents.py`, `integration/federation/{doc_store,retrieval}.py`, `api/node_db.py` (`/api/v3/documents/*`) |
| **Evidence** | `evidence/integrated_retrieval_demo.txt` (four questions and the evaluation). Entity linkage 91.6% recall / 95.0% precision against the corpus ground truth. Context versus question-only retrieval over 10 questions: **P@5 0.84 vs 0.78, R@10 1.00 vs 0.93, nDCG 1.00 vs 0.95**, with the gain on batch-only questions. |
| **Tests** | `tests/test_phase3_documents.py` **13/13** |
| **Demo** | `python scripts/integrated_demo.py "..."`; `python scripts/eval_retrieval.py` |
| **Caveat** | The corpus is synthetic, and its ground truth comes from the same generator, so the retrieval figures are optimistic for real text. Retrieval is lexical plus identifiers, with no semantic embeddings. |

### Requirement 5 — show the original prompt, the generated code and the modified code

| | |
|---|---|
| **Implemented** | Every Phase 3 prompt is quoted verbatim (P3-0 to P3-5) in `vibe_coding/PROMPTS_PHASE3.md` and in `vibe_coding/rounds/17-*`, `18-*`, `19-*`. The original state is frozen in `vibe_coding/phase2_baseline/` and commit `857d932`. The code as first generated, before it ran, is in `vibe_coding/generated_v0_phase3/` and `rounds/*/generated/`. All 21 later changes are in `vibe_coding/CHANGES_PHASE3.md`, each with what was observed. Exact diffs are in `phase3/documentation/PHASE3_CODE_DIFFS.md` (generated from git). |
| **Incomplete** | The Phase 2 diff page (`vibe_coding/make_diff_report.py` → `dashboard/vibe/index.html`) has **not** been extended to Phase 3; the Phase 3 diffs exist as Markdown, not as a dashboard page. For files a round modified, the state just before that round was not snapshotted separately (noted in rounds 17–18). |

## 3. The requested test cases

From `evidence/test_results.txt`: **104 unit tests in 7 suites, all passed**, plus the page-render check. Each suite runs in its own process (`python scripts/run_phase3_tests.py`).

| # | Requested test | Where it is tested |
|---|---|---|
| 1 | Every database has 4–5 related tables | `test_phase3_schema.Structure.test_each_source_has_at_least_five_connected_tables`, `test_new_tables_are_populated` |
| 2 | FK–PK relationships correct | `test_phase3_schema.Structure.test_referential_integrity`, `Migration.*`, `Triggers.*`, `Documents.test_document_references_resolve` |
| 3 | Each database executes queries independently | `test_phase3_federation.LocalExecution.*`, `test_phase3_operators.*` |
| 4 | Federated queries reach the right databases | `test_phase3_federation.Coordination.test_routing`, `test_end_to_end_with_provenance`; `test_phase3_end_to_end.test_1_2_…`, `test_3_4_…` |
| 5 | Context follows real FK–PK relationships | `test_phase3_score.Algorithm.test_only_real_foreign_keys_are_joined`, `test_document_store_joins_follow_declared_references` |
| 6 | Context goes beyond the original query result | `test_phase3_end_to_end.test_5_6_…` (terms reached through joins), `test_phase3_score…test_every_term_keeps_its_provenance` |
| 7 | Ranking prioritises relevant terms | `test_phase3_score…test_query_relevance_decides_which_fk_is_joined_first`, `test_rare_values_outrank_common_ones`, `test_unrelated_tables_are_not_explored` |
| 8 | Mediator aggregates local contexts | `test_phase3_score.Aggregation.*`, `test_phase3_end_to_end.test_7_…` |
| 9 | Retrieval uses the aggregated context | `test_phase3_documents.Retrieval.test_context_finds_what_the_question_alone_misses`, `test_phase3_end_to_end.test_8_9_…` |
| 10 | Relevant documents retrieved and ranked | `test_phase3_documents.Retrieval.*` (incl. sibling batches excluded, common words alone return nothing) |
| 11 | Document provenance preserved | `test_phase3_documents…test_every_result_explains_itself`, `test_phase3_end_to_end.test_10_…` |
| 12 | Partial database failures | `test_phase3_federation…test_unreachable_database_gives_partial_result_and_no_verdict`, `test_slow_database_times_out`, `test_phase3_end_to_end.test_z_a_database_dies_mid_session` (kills DB3 mid-session, then recovers) |
| 13 | Phase 1 and Phase 2 still work | `tests.test_uncertainty` + `tests.test_replication` **28/28** (fixture built on the Phase 3 schema); network-versus-local verdict parity (25/25); 218/218 verdicts unchanged by the migration; `evidence/legacy_phase1_phase2_check.txt` |

**Phase 1/2 components named in the brief**, from `evidence/legacy_phase1_phase2_check.txt`: the legacy two-node cluster ran on a copy of the migrated databases.

| Component | Evidence |
|---|---|
| Dashboard pages | `index`, `verify`, `explorer`, `uncertainty`, `vibe` all served (HTTP 200) by both nodes |
| Explorer | shows DB3's 7 tables |
| Phase 1 pipeline (`FEDERATED_VIEW`: normaliser, GAV resolver, GlobalItemHistory, conflict resolution, hard vetoes, weighted score, audit) | MED-ASALI-001 → ASALI 100; MED-ASALI-009 → SUSPICIOUS 65; MED-NAKALI-001 → NAKALI 0 with V1 + V2; MED-RECALL-001 → NAKALI 0 with V2; damaged `MED-ASAL1-OO1` → resolved to MED-ASALI-001, ASALI 100 |
| Phase 2 matcher | `MED-ASAL1-OO7` → AUTO_LINK MED-ASALI-007 (posterior 0.993) |
| Audit chain | intact (499 blocks) |

## 4. Demonstration scenarios

`phase3/documentation/PHASE3_DEMONSTRATION.md` is **generated** by `scripts/phase3_scenarios.py` from real responses; the full JSON is in `evidence/scenario_{1,2,3}.json`. For each scenario it shows the question, the subqueries, per-database results, the FK joins explored, local and aggregated context, the document search query, the ranked documents and the integrated answer.

| Scenario | Question | Observed |
|---|---|---|
| 1 | "Is MED-ASALI-009 from batch BATCH-A009 genuine?" | all four databases; verdict **SUSPICIOUS 65** (matches the Phase 1 baseline); top documents: the batch inspection, the cold-chain excursion report and the shipment note for that batch |
| 2 | "Any quality or safety concerns about products manufactured by MFG-002 (Sun Pharmaceutical)?" | routed to DB3 and DB4. DB4's subquery on `recall_notices.manufacturer_ref = MFG-002` found the manufacturer's recall, and the batch is held by both DB3 and DB4, so `MED-RECALL-001` and `BATCH-R001` entered the document search as **context identifiers** (weight 0.5). The recall notice, investigation, quality review and batch inspection were then retrieved; the question never named the recalled product |
| 3 | "Are there consumer complaints or regulatory action against MED-NAKALI-001?" | DB4 only; verdict **NAKALI** (blacklist, lab failure); the complaint letter and the pharmacy incident are marked as unverified allegations, next to the structured facts |

To reproduce: start the system (§1), then `python scripts/phase3_scenarios.py`, or click the scenario buttons on the page.

## 5. Not done, or not verified

1. **Multi-machine execution** (Requirement 2), as above. Docker not run.
2. **Visual check of the page** in a browser (only its logic was checked, against real responses).
3. **Phase 3 diff page** in the dashboard (Requirement 5's Markdown record exists).
4. **SCORE formulas versus the lecture** not checked (slides unavailable).
5. **Nothing from Phase 3 is committed.** All work is on branch `phase3`, uncommitted.
6. Not re-run in this phase, because Phase 3 does not touch them: the Phase 2 model fit (`train.py`) and label-image rendering.
