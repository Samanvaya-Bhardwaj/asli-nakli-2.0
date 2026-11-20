# Changes made to the generated Phase 3 code

`vibe_coding/generated_v0_phase3/` holds every Phase 3 file exactly as first written, before it
was run. Each entry below is a change made afterwards, because running or reviewing the code
showed it was wrong: what was observed, what changed, where.

## P3-1 — Requirement 1 (related tables)

**1. Schedule class was wrong for prescription drugs.** The validation report showed insulin
glargine (MED-ASALI-009) as `schedule_class = X`, the narcotics schedule. The generated
`schedule_class()` treated any non-zero `products.controlled_substance` as controlled, but the
Phase 1 seed codes that column as 0 = not controlled, **1 = prescription only** (antibiotics,
metformin, insulin) and **2 = narcotic / psychotropic** (codeine, diazepam). Seven molecules were
mis-scheduled. → Level 2 → X, antibiotic → H1, level 1 → H, OTC categories → OTC. A test now pins
five known molecules. *data/seed_phase3.py, tests/test_phase3_schema.py*

**2. The DB4 join demo returned no rows.** The inspection report used one medicine for every
source; MED-ASALI-009 has no ministry records, so the DB4 join printed 0 rows and showed
nothing. → Each source gets a demo medicine that has records there (MED-RECALL-001 for DB4);
`--item` still overrides. *integration/federation/inspect.py*

Found before the first run, so part of the generated snapshot and not listed as a change:
`schema_catalog.integrity_report()` first mapped `foreign_key_check` ids through a re-sorted list,
which could have reported a violation against the wrong foreign key.

## P3-2 — Requirement 2 (distributed deployment, federated queries)

**3. A one-character neighbour was treated as the same medicine.** The first federated run for
MED-ASALI-009 showed DB4 matching a lab report and a complaint for **MED-ASALI-001** (edit distance
1), then expanding them into unrelated recalls and blacklist rows. The generated `code_matches()`
fell back to one-edit matches when nothing closer existed. Phase 2 showed consecutive batches are
one edit apart, so those are different medicines. → `code` matches only exact / formatting /
scanner-look-alike values; one-edit values are returned separately as `near_misses` and never seed
context or a verdict. *integration/federation/local_engine.py*

**4. The combined result mixed two kinds of medicine.** It listed the code that was asked about
together with fifteen codes that appeared only in discovered context (other batches of the same
distributor). → Nodes return `match_bridge_keys` (from matched rows) next to `bridge_keys` (all
rows). The coordinator reports `medicines` (matched), `related_in_context` and `near_misses`
separately. *local_engine.py, coordinator.py, scripts/federated_demo.py*

**5. "shipments" left the fragment "ments" as a search term.** The intent keyword "ship" was cut out
of the middle of the word. → A one-word keyword removes the whole word; "send/sent/got" are stopwords.
*integration/federation/query_parser.py*

**6. Two identifiers on one table became two unrelated subqueries.** "Which shipments did DIST-004
send to VND-012?" sent one subquery per identifier, each matching half the question. → When several
identifiers map to the same table, unfolding emits one subquery that requires all of them. The GAV
mapping gained `distribution_batches.distributor_id` and `distributor_vendor_contracts.distributor_id`.
*coordinator.py, integration/schema_mapping.json*

**7. Local-mode verification waited about 6 s per item on the DB4 REST service.** This was found
while building the parity test: with the Phase 1 service not running, every lookup waited out four
HTTP timeouts, and the address and token were fixed in code (audit item J-4). →
`ASALI_DB4_REST_URL` (or `offline`, meaning go straight to the in-process store) and
`ASALI_DB4_LEGACY_TOKEN`, with the Phase 1 values as defaults. `ministry_service.py` gained `--host`, and its
store path follows `ASALI_DB_DIR`. *integration/wrappers/rest_wrapper.py, api/ministry_service.py*

**8. The physical host could not be reported from inside a container.** → `ASALI_PHYSICAL_HOST` in
the machine profiles. *deploy/machine1.env.example, deploy/machine2.env.example*

`tests/test_phase3_federation.py` was written after the snapshot. Its one later edit stops the
service processes writing into pipes nobody reads (ResourceWarnings, and a possible stall), and
simplifies the schema lookup in one test.


## P3-3 — SCORE-inspired query context discovery

**9. Phrases were split into words, and schema affinity was all-or-nothing.** This was found in the first smoke run, before the round snapshot. For "cold chain", the original matcher (`k in text or text in k` over single words) flagged *"Apollo Supply **Chain** Solutions"* as matching the question. `_affinity()` returned True for any table with one matching column, so `distributors` (which has a `cold_chain_capable` column) beat `cold_chain_loggers` for a cold-chain question, and the DB2 run joined distributors first. → Keywords and phrases are now matched as whole words or prefixes, with underscores read as spaces. Affinity is 1.0 for a table-name match and 0.5 for a column-only match. The parser passes intent phrases whole (`keywords`), and the coordinator adds each intent's vocabulary. *score_context.py, query_parser.py, coordinator.py*

**10. Relationship paths read backwards.** Paths were stored as the FK's label, which is always written child → parent. So walking products → production_records printed "production_records(product_uid) -> products(product_uid)". → `step_label()` writes each join in the direction it was walked. *score_context.py*

**11. Integer codes were treated as quantities.** `controlled_substance` (levels 0/1/2) was summarised as "mean 0.05", which is meaningless for a code. → Integer columns with at most five distinct values are categorical. *score_context.py*

**12. The question's own code was the top context term.** MED-ASALI-009 ranked first in the aggregated context for a question about MED-ASALI-009. → The aggregator now lists the question's identifiers (and what they resolved to) as `anchors`, apart from the context. *context_aggregator.py, coordinator.py*

**13. Two Requirement 2 tests asserted the plain walk.** They expected every neighbour to be visited (`manufacturing_sites`, `pos_terminals`), which is exactly what SCORE avoids. → They now pin `method="bfs"` for that assertion and add the SCORE expectation: selective, local, with paths. *tests/test_phase3_federation.py*


## P3-4 — context-aware unstructured retrieval and integration

**14. Fixes made while building the corpus** (before the round snapshot; listed for completeness):
- Only one cold-chain incident report was generated, because the generator required a temperature-sensitive product. Distributors also report excursions for ordinary products. → Reports for every excursion, with a product-dependent impact paragraph.
- The ground truth kept raw stored codes (`med_lvcre_851`), and omitted the medicine for complaints about unregistered codes (MED-NAKALI-001). → Canonical codes, always included.
- The authenticity keyword "safe" also fired on "safety". → Only "is it safe" / "safe to"; a separate `safety` intent.

*data/generate_documents.py, integration/federation/query_parser.py*

**15. Recall notices about other medicines came back for a batch question.** "Find information about batch BATCH-A009 … Biocon …" returned three recall notices for unrelated products, on the words "ltd" and "manufactured". There were two causes:
- The different-medicine penalty only applied when the question itself named a medicine code. Here the code was found through the FK context, and the question named a batch.
- Company suffixes looked informative in DB4's collection.

→ The penalty applies whenever the request carries medicine codes or batches (the question's own, or found through FK joins with weight ≥ 0.5) and the document names others but none of them. "ltd/limited/pvt/www/com…" are not search terms. SCORE also skips `website` columns. *doc_store.py, score_context.py*

**16. The question's code was tokenised as words.** "MED-NAKALI-001" added the words *med* and *nakali*, which match every other NAKALI document. That is how a complaint about MED-NAKALI-002 ranked for MED-NAKALI-001, and how "Janata **Med**icos" got highlighted. → Codes are removed from the question text before tokenising; they are matched as entities. *doc_store.py*

**17. Penalised documents still filled the bottom of every list (scores 0.03–0.11).** → A minimum score of 0.15. *doc_store.py*

**18. Nested highlight markers** (`****MED**-**NAKALI**-001**`) came from substituting overlapping strings one after another. → One regex pass, longest first, whole words only. *doc_store.py*

**19. A test assumed the wrong document.** It assumed the cold-chain incident report for BATCH-A009 is only reachable through the context, but that report names the batch itself. → The test now checks the shipment note DOC-DB2-SHP-003, which names only the pack code: it is retrieved with the context and not with the question alone. *tests/test_phase3_documents.py*


## P3-5 — integration and end-to-end validation

**20. The verification scenario withheld its verdict.** In the first end-to-end run of "Is MED-ASALI-009 from batch BATCH-A009 genuine?", DB1 answered one subquery with HTTP 500, `NameError: name 'v' is not defined`. DB1's document engine wrote the native-query text for the `eq` operator with an undefined variable. No earlier question had sent `eq` to DB1's documents; this one did, through the combined subquery on `retail_medicines` (code AND batch). The coordinator behaved as designed: DB1 was reported `partial`, so the verdict was **withheld** rather than computed on missing evidence. → `mongo[fld] = val`. `tests/test_phase3_operators.py` now runs every operator (eq, in, contains, contains_any, gte, lte, code) and combined conditions on both engines. *integration/federation/local_engine.py*

**21. The full rebuild did not regenerate the documents.** → `scripts/rebuild_data.py` step 5b runs `data/generate_documents.py`. A from-scratch rebuild on a copy then reproduced the project's 28 tables and 303 documents exactly. *scripts/rebuild_data.py*
