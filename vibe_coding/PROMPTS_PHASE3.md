# Vibe-coding prompts — Phase 3: federated, context-aware integration

Tool: Claude Code (model: Claude Opus 5.5), run inside this repository.

Same convention as Phase 2 (`PROMPTS.md`):

* **Prompt 0** is the Phase 3 request exactly as it was typed.
* **Prompts P3-n** are the requests that implement it, quoted exactly, in order.
* The files each prompt changes are frozen *before* the change in `vibe_coding/phase2_baseline/`
  (the project as Phase 2 left it) and *as first generated, before anything was run* in
  `vibe_coding/generated_v0_phase3/`. Every later edit is listed in `CHANGES_PHASE3.md`.

---

## Prompt 0 — the request (audit and plan)

> I need to implement Phase 3 of my existing Asali/Nakali medicine verification project.
>
> First, thoroughly inspect the entire repository and understand the existing architecture
> before modifying anything.
>
> PHASE 3 ASSIGNMENT REQUIREMENTS:
>
> 1. Expand each database to contain at least 4-5 related tables/entities. Information about
>    an entity must be distributed across multiple tables, with appropriate foreign-key and
>    primary-key relationships.
> 2. Database instances must run on different machines. A user query must be federated across
>    these databases. Each database must independently discover relevant context using its local
>    FK-PK relationships.
> 3. Accumulate the context discovered by individual databases. The overall context must be
>    highly relevant to the original user query.
> 4. Use the discovered query context to search unstructured data and integrate relevant
>    documents with structured query results.
> 5. Demonstrate the original prompt, generated code and modified code.
>
> For now, DO NOT MODIFY ANY FILES. Perform a complete repository audit and report: [A–J] …
> Create a detailed Phase 3 implementation plan. … Save the analysis as
> PHASE3_IMPLEMENTATION_PLAN.md. Wait for my approval before implementing anything.

Output: `PHASE3_IMPLEMENTATION_PLAN.md` (no code).

## Prompt P3-0 — decisions

> Physical machines: Use 2 physical machines with Docker. Distribute the four independent
> database services across both machines, preferably two databases per machine. Keep the GAV
> mediator and federated query coordinator on Machine 1. …
> Document storage: Store unstructured documents with the database/data source that owns them. …
> Document usage: Unstructured documents should provide supporting information and explanations
> only. They must not directly modify or influence the existing ASALI/NAKALI verification verdict. …
> Older Git clone: Leave Project2_Asali_Nakali/Project2_Asali_Nakali/ untouched. …
> Modified data files: Inspect and validate the five modified data files. If the changes are
> intentional and valid, commit them separately before taking the Phase 3 starting snapshot. …
> Ports and APIs: Approve ports 8021–8024 for the four database services and 8030 for the
> federated coordinator, after checking for port conflicts. Use /api/v3/ …

Output: commit `857d932` (clean data baseline), branch `phase3`.

## Prompt P3-1 — Requirement 1: related tables

> Now implement Phase 3 Requirement 1 based on the approved PHASE3_IMPLEMENTATION_PLAN.md.
>
> OBJECTIVE: Expand all four existing databases so that each contains at least 4-5 related
> tables/entities, with information about the same real-world medicine distributed across
> multiple tables using primary-key and foreign-key relationships.
>
> IMPLEMENTATION REQUIREMENTS:
> 1. Inspect the existing schemas before making changes.
> 2. Expand each database with meaningful medicine-related tables. Do not create unrelated dummy
>    tables just to satisfy the table count.
> 3. Ensure each database has at least 4-5 meaningful, interconnected tables/entities.
> 4. Distribute information about medicines across these tables.
> 5. Establish valid PK-FK relationships wherever appropriate.
> 6. Design realistic relationships, for example: RETAIL POS: Pharmacy, Medicine, Sales, Sale
>    Items, Inventory. DISTRIBUTOR: Distributor, Medicine, Batch, Shipment, Shipment Items.
>    MANUFACTURER: Manufacturer, Medicine, Batch, Production Records, Quality Certificates.
>    MINISTRY: Regulatory Authority, Medicine, Complaints, Recall Notices, Blacklist Records.
>    Adapt these examples to the existing schemas and data. Avoid unnecessary duplication.
> 7. Preserve existing identifiers and ensure that relationships between databases can be
>    established through shared business identifiers such as medicine_id, batch_id and
>    manufacturer_id.
> 8. Maintain realistic sample records with sufficient connected data to demonstrate
>    multi-table joins.
> 9. Update existing database initialization scripts, migrations, seed data and data access
>    functions.
> 10. Ensure existing Phase 1 and Phase 2 verification workflows continue working.
>
> IMPORTANT: Do not merge the four databases. Do not introduce a centralized data warehouse.
> Preserve the existing database technologies wherever possible. If a source is NoSQL or
> REST-based, implement a compliant relational representation or adapter strategy as
> established in the approved implementation plan. Do not silently claim that a NoSQL
> collection or API endpoint is a relational SQL table.
>
> VALIDATION: Show all tables/entities in each database. Show their PK-FK relationships.
> Demonstrate at least one multi-table join per database. Verify referential integrity. Verify
> that existing application functionality still works.
>
> Update PHASE3_IMPLEMENTATION_PLAN.md with completed changes.

Generated for P3-1 (snapshot in `generated_v0_phase3/`): `schema/schema_db1..4.sql`,
`integration/federation/{__init__,schema_catalog,migrate,nosql_store,medicine_views,inspect}.py`,
`data/seed_phase3.py`, `scripts/migrate_phase3.py`, `tests/test_phase3_schema.py`, and edits to
`data/seed_nosql_db1.py`, `scripts/rebuild_data.py`, `create_databases.py`,
`integration/db_explorer.py`, `tests/test_uncertainty.py`.

## Prompt P3-2 — Requirement 2: distributed deployment and federated query execution

> Implement Phase 3 Requirement 2: Distributed database deployment and federated query execution.
>
> OBJECTIVE: The four independent database instances must run on different machines. A user query
> must be distributed to the relevant databases, and each database must independently execute its
> subquery and discover relevant local context.
>
> STEP 1: DISTRIBUTED DEPLOYMENT — 1. Inspect the current database and deployment architecture.
> 2. Configure the four database instances as independent services that can run on separate
> physical machines or virtual machines. 3. Use configurable hostnames, IP addresses, ports and
> credentials through environment variables. 4. Do not hardcode IP addresses or credentials.
> 5. Provide a separate configuration for local development and distributed deployment.
> 6. Implement health-check endpoints or connection checks to verify that each database is reachable.
>
> STEP 2: FEDERATED QUERY EXECUTION — Implement a federated query coordinator using the existing
> GAV mediator architecture. When a user submits a natural-language query: 1. Understand the user's
> information requirement. 2. Identify which databases are relevant. 3. Generate appropriate
> database-specific subqueries. 4. Send each subquery to its respective database instance.
> 5. Execute the subqueries independently. 6. Collect structured query results from all
> participating databases. 7. Preserve source database identity and provenance. 8. Handle
> unavailable databases, timeouts and partial results. 9. Do not merge the original databases into
> one database.
>
> STEP 3: DATABASE-SPECIFIC EXECUTION — Each database must expose an interface that supports:
> receiving a subquery; executing the query locally; returning structured results; exposing its
> local schema and FK-PK relationships; supporting local context discovery. The coordinator must not
> perform all context discovery centrally. Each database must participate independently.
>
> STEP 4: INTEGRATION — Integrate the federated query execution with the existing GAV mediator and
> canonical model. Do not break: GlobalItemHistory. Resolver. Conflict resolver. Medicine
> verification engine. Phase 2 uncertainty module.
>
> STEP 5: TESTING AND DOCUMENTATION — Demonstrate: 1. Four independent database instances. 2. Their
> respective machine addresses. 3. A single user query. 4. The subqueries generated for each
> database. 5. Independent execution on each database. 6. Results returned by each database.
> 7. Combined federated query results. Provide Docker or deployment configuration where appropriate,
> along with instructions for deploying each database on a separate machine.
>
> IMPORTANT: Localhost-based testing alone does not prove distributed deployment. Clearly
> distinguish local simulation from actual multi-machine execution.

Generated for P3-2: `integration/federation/{runtime,local_engine,remote,query_parser,coordinator}.py`,
`api/node_db.py`, `api/coordinator_service.py`, `scripts/{prepare_node_data,run_federation,federated_demo}.py`,
`deploy/` (env profiles, compose files), `Dockerfile.phase3`, and edits to `integration/resolver.py`,
`entity_resolver.py`, `lifecycle_state.py`, `mediator.py`, `audit_chain.py`, `ministry_reporter.py`,
`wrappers/sql_wrapper.py`, `wrappers/nosql_wrapper.py`, `schema_mapping.json`, `api/verify_item.py`.


## Prompt P3-3 — SCORE-inspired query context discovery

Quoted in full in `vibe_coding/rounds/17-score-context/ROUND.md`. The user titled it "Requirement 2"; it covers the context half of Requirement 2 and the plan's Requirement 3.

Generated:
- **New:** `integration/federation/score_context.py`, `integration/federation/context_aggregator.py`, `scripts/score_demo.py`, `tests/test_phase3_score.py`, `phase3/documentation/PHASE3_CONTEXT_DISCOVERY.md`.
- **Edited:**
  - `local_engine.py`: rows, keys and FK joins for SCORE; `method` score|bfs.
  - `coordinator.py`: keywords, MAX_AUGMENTATION / TOP_N, aggregation.
  - `query_parser.py`: keywords.
  - `coordinator_service.py`, `mediator.py`.


## Prompt P3-4 — context-aware unstructured retrieval and integration

Quoted in full in `vibe_coding/rounds/18-document-retrieval/ROUND.md`. The user titled it "Requirement 3"; it is the plan's Requirement 4.

Generated:
- **New:** `data/generate_documents.py` (the corpus in `data/documents/`), `integration/federation/doc_store.py`, `integration/federation/retrieval.py`, `scripts/integrated_demo.py`, `scripts/eval_retrieval.py`, `tests/test_phase3_documents.py`, `phase3/documentation/PHASE3_UNSTRUCTURED_RETRIEVAL.md`.
- **Edited:**
  - `coordinator.py`: document search and the integrated answer.
  - `query_parser.py`: a safety intent, plus quality/inspection words.
  - `schema_mapping.json`: safety routing.
  - `api/node_db.py`: `/api/v3/documents/*`.
  - `coordinator_service.py`, `mediator.py`.
  - Deployment: `prepare_node_data.py` and `run_federation.py` (per-source document folders), `Dockerfile.phase3` (+ its ignore file).


## Prompt P3-5 — integration and end-to-end validation

Quoted in full in `vibe_coding/rounds/19-end-to-end/ROUND.md`.

Generated:
- `dashboard/phase3.html` (the user-facing page, served by the coordinator at `/`);
- `tests/test_phase3_end_to_end.py`, `tests/test_phase3_operators.py`;
- `scripts/phase3_scenarios.py` (writes `PHASE3_DEMONSTRATION.md` from real responses), `scripts/run_phase3_tests.py`;
- `phase3/tools/check_page_render.mjs`, `phase3/tools/code_changes.py`;
- `phase3/documentation/*` and `PHASE3_FINAL_REPORT.md`.

Edited: `api/coordinator_service.py` (serves the page), `scripts/rebuild_data.py` (documents), `local_engine.py` (CHANGES item 20).
