# SCORE-inspired query context discovery

**What it does.** Each database finds the context around a query's answer by itself, using its own foreign keys. The mediator then merges the four local contexts into one overall query context, ranked by relevance to the question and with the origin of every term kept.

| | |
|---|---|
| Code | `integration/federation/score_context.py` (runs inside each database service); `integration/federation/context_aggregator.py` (the mediator's merge) |
| Demo | `scripts/score_demo.py`; recorded run in `phase3/documentation/evidence/score_context_demo.txt` |
| Tests | `tests/test_phase3_score.py` (12), plus the updated `tests/test_phase3_federation.py` (16) |

> **Reference.** This follows the SCORE ideas from Week-11 L1. Those are: the result of a structured query defines its *query context*; terms are extracted from that result and weighted; the result is *augmented* by joining neighbouring tables through foreign keys, choosing the most relevant FK each time, up to `MAX_AUGMENTATION`; the `TOP_N` context terms are returned.
>
> The lecture slides were not available when this was written. The exact formulas below are this implementation's choices, and every one of them is a parameter:
> - the tf × idf term weight;
> - the top-5 gain;
> - the schema-affinity and fan-out factors;
> - the decay;
> - the thresholds.
>
> Please compare them with the lecture's definitions.

---

## 1. Where it runs

```
question ──> coordinator: parse ─> route ─> GAV unfold (one subquery per database view)
                                               │  (HTTP, one bearer token per database)
          ┌──────────────────┬─────────────────┼─────────────────┬──────────────────┐
          ▼                  ▼                 ▼                 ▼
   DB1 service         DB2 service        DB3 service        DB4 service      ← each on its own machine
   execute subquery    execute subquery   execute subquery   execute subquery
   SCORE over its      SCORE over its     SCORE over its     SCORE over its
   document refs       FK-PK graph        FK-PK graph        FK-PK graph
   ranked local ctx    ranked local ctx   ranked local ctx   ranked local ctx
          └──────────────────┴─────────────────┬─────────────────┴──────────────────┘
                                               ▼
                         coordinator: aggregate (dedupe, normalise, corroborate, rank)
                                               ▼
                                     overall query context
```

The coordinator **never** reads a database row and never walks a schema. It only sends the subquery and the query's keywords, then merges what comes back.

## 2. The algorithm, per database

**Input**
- A declarative subquery: target table, conditions, and the GAV view the coordinator chose.
- The question's keywords: the user's words, intent phrases kept whole ("cold chain"), and each detected intent's vocabulary ("temperature", "excursion" for cold chain). Adding the intent vocabulary is a disclosed query expansion.
- `MAX_AUGMENTATION` and `TOP_N`.

### Step 1 — query result analysis

The subquery is compiled to the source's own language and executed:
- parameterised SQL for the SQLite sources;
- `db.<collection>.find(...)` for DB1's documents.

The **whole result relation R0 is kept, every column**, including ones a user-facing projection would drop, because any of them may carry context. Each column is classified by looking at all the values it holds across the table:

| Kind | How it is recognised | Example |
|---|---|---|
| identifier | primary/foreign key column, or a code-like column name | `batch_id`, `MFG-004`, `registration_no` |
| categorical | few distinct values, or 0/1/2-style integer codes | `status`, `cold_chain_maintained`, `schedule_class` |
| text | four or more words on average | `discrepancy_details`, `findings_summary` |
| numeric | other numbers | `temperature_c`, `msrp_kes` |
| date | date-named column, or ISO values | `dispatch_date` (kept at month granularity) |
| skip | hashes, image paths, URLs, phone numbers, unique short strings | `certificate_hash` |

### Step 2 — schema relationship discovery

- **Tables are nodes and FK–PK relationships are edges.** For SQLite they are read from `PRAGMA foreign_key_list`, composite keys included. For DB1 they come from its declared document references (`db1_collections.json`). Nothing is hard-coded.
- The response returns the graph as `schema_graph`.
- Edges are walked in both directions:
  - "to the referenced (PK) table": from a shipment to its distributor;
  - "to the referencing (FK) table": from a shipment to the loggers that record it.

### Step 3 — context terms from the result

Terms are extracted per column kind:

| Kind | Term produced |
|---|---|
| identifier | one term per value; keyed by value, so the same id from another database merges with it later |
| categorical | `column=value` |
| text | each content word (stopwords removed) |
| date | `column=YYYY-MM` |
| numeric | one summary term per column: range, the result's mean, and the table's mean |

Each term gets a weight:

```
w(term) = tf_R × (0.05 + idf_T) × kind_weight × decay^step × (1 + query_boost · query_match)

tf_R   = share of the relation's rows that hold the term
idf_T  = log((1+N)/(1+df)) / log(1+N), df = rows of the WHOLE table holding the term in that column (0..1)
kind_weight: text 1.0, identifier 0.9, categorical 0.8, numeric 0.6, date 0.5
numeric terms use, in place of idf: min(1, |mean_R − mean_T| / (2·std_T))
query_match: a keyword or phrase starts a word of the term or its column name
             ('cold chain' matches cold_chain_maintained, not "Supply Chain")
```

Terms common in the result but rare in the database rank highest. The test suite checks this with no query words at all: `cold_chain_maintained=0` (45 of 427 shipments) weighs more than five times `status=delivered` (every shipment).

### Step 4 — neighbouring-table exploration (greedy augmentation)

```
explored = {R0's table};  relations = [R0];  context = terms(R0)
repeat up to MAX_AUGMENTATION times:
    for every FK edge from an explored table to an unexplored one:
        perform the join from that relation's rows          (real SQL JOIN / $lookup)
        extract the joined records' terms
        relevance = gain × (1 + affinity_boost · affinity) × fanout_penalty
            gain           = sum of the 5 highest weights of terms NOT already in the context
            affinity       = 1.0 if the neighbour's table name matches the question,
                             0.5 if only one of its columns does, else 0
            fanout_penalty = 1 / (1 + log2(joined rows per source row))
    if the best relevance < MIN_FK_RELEVANCE: stop
    join that FK: add its relation and its terms (decayed by DECAY per step)
```

**Avoiding unrelated tables.** An FK is followed only if it earns the highest relevance at that step. An FK whose join adds nothing new scores 0, so the mere existence of a key is never a reason to explore a table. A hub that would pull in many rows (one distributor → nine vendor contracts) is penalised by fan-out. A schema that is "about" the question (`cold_chain_loggers` for a cold-chain question) is preferred. Each step's candidate list (every FK considered, its relevance and its formula) is in the response, so every choice can be checked.

### Step 5 — ranking and provenance

Terms are merged by key. A term's score is its best weight, plus a quarter of each further occurrence's weight. The `TOP_N` terms are returned, each with:
- the term or value;
- its kind;
- its score;
- its source database, table and column;
- the relationship path, i.e. the chain of FK joins in the direction walked, such as `distribution_batches(batch_id) -> cold_chain_loggers(batch_id)`;
- the associated entity identifiers: the primary keys of the rows that held it, plus the shared business identifiers in those rows (item code, vendor, distributor, manufacturer);
- every other place it occurred.

### Step 6 — the database's response (`result.score_context`)

`query_result` (R0's table, rows, column kinds), `schema_graph`, `result_terms`, `augmentation` (every candidate FK per step, its relevance and whether it was joined), `stop_reason`, `explored_tables`, `joins_performed` (the join statement and row count), `additional_records` (primary keys of every joined row, with step and path), and `ranked_context`. The subquery result itself (`matches`, `native_query`) sits beside it.

## 3. Aggregation at the mediator (Step 7)

`context_aggregator.aggregate()`, called by `coordinator.federated_query()`; also reachable as `GavQueryMediator.execute_federated_query()`:

```
s_d   = term score / best score in that subquery's context  ×  that subquery's match quality
        (1.0 exact, 0.97 formatting, 0.9 scanner look-alike); best value per database kept
S     = (Σ_d s_d) × (1 + 0.25 · (databases that found it − 1)) × (1.5 if it matches the question)
```

- **Normalising per subquery** keeps a database with long text columns from drowning out one with short codes.
- **Deduplication** is on the normalised key, so an identifier is one term whichever database holds it. `MFG-004` appears once, with its DB2 shipment and DB3 registry provenance.
- **Anchors.** The question's own identifiers (the code asked about, and what it resolved to) are reported as `anchors`, not as context. They are what the context is *about*.
- **Why relevant.** Each term carries reasons: in the result itself; reached through *n* FK joins (with the path); found independently by *k* databases; matches the question; rare in its column (high tf × idf).

## 4. Worked example: "Was the cold chain of MED-ASALI-009 maintained?"

From `phase3/documentation/evidence/score_context_demo.txt`:

1. **Understanding.** Intent cold chain, identifier MED-ASALI-009. Routed to DB2 (shipments, temperature logs) and DB3 (storage band). DB1 and DB4 were not queried, each with a stated reason.
2. **DB2 result relation.** One shipment row, `DBATCH-010`, all 18 columns. Its strongest terms are the words of its discrepancy note (*excursion*, *thermal*, *threshold*, *exceeded*), which appear in few shipments, and the shipment's identifiers.
3. **DB2 augmentation:**

   | Step | Candidates (relevance) | Joined |
   |---|---|---|
   | 1 | `cold_chain_loggers` **3.66** (affinity 1.0, name matches "cold chain"); `distributors` 3.04 (0.5, one column matches); `warehouses` 2.77 | `cold_chain_loggers` |
   | 2 | `distributors` **3.04**; `warehouses` 2.77; `temperature_logs` 0.24 (11 rows per logger, so the fan-out penalty applies) | `distributors` |
   | 3 | `warehouses` **2.77**; `distributors → warehouses` 0.51; `temperature_logs` 0.24; `distributor_vendor_contracts` 0.051 (9 rows, no affinity) | `warehouses` |
   | 4 | `temperature_logs` **0.24**; `distributor_vendor_contracts` 0.051 | `temperature_logs` (its 11 readings, including the excursion readings) |

   The run stopped at MAX_AUGMENTATION = 4. `distributor_vendor_contracts` and `return_log` (which has no FK) were never explored.
4. **DB3**, independently: `products` → `molecules` → `production_records` → `manufacturers` → `batch_release_certs`. Its result terms are the storage band (`storage_temp_max=8`, `storage_temp_min=2`) and `requires_cold_chain=1`.
5. **Aggregated context (top):**
   - *excursion* (DB2);
   - `requires_cold_chain=1`, `storage_temp_max=8.0`, `storage_temp_min=2.0` (DB3);
   - `MFG-004` (DB2 and DB3, corroborated);
   - `BATCH-A009`.

   MED-ASALI-009 itself is listed as an anchor. The context answers the question as asked: the medicine needs a 2–8 °C band, and its shipment logged a thermal excursion.

The transcript has three more questions:
- a recall question: DB4 joins `ministry_blacklist` and `recall_notices` first, by affinity;
- a pharmacy stock question: DB1's document store reaches `stock_receipts` and `inventory` through `$lookup` on declared references;
- an identifier-only shipment question.

## 5. What this is not

- **Not entity matching.** The `code` operator (Phase 2's scanner look-alike folding) only decides which rows form R0; SCORE starts from R0. A test checks this: a damaged code that resolves to the same row produces exactly the same ranked context as the clean code.
- **Not a central walk.** The coordinator never sees a schema or a row; it sees each database's ranked terms.
- **Not the plain walk.** The Requirement 2 breadth-first walk is still available (`"method": "bfs"`) as a baseline. It visits every neighbour within *k* hops, while SCORE visits only the FKs that earn it.

## 6. Parameters

| Parameter | Default | Where |
|---|---|---|
| `MAX_AUGMENTATION` | 4 | request `max_augmentation`, or `ASALI_SCORE_MAX_AUGMENTATION`; the service caps it at 8 |
| `TOP_N` | 20 | request `top_n`, or `ASALI_SCORE_TOP_N`; capped at 100 |
| `MIN_FK_RELEVANCE` | 0.05 | subquery `expand.min_fk_relevance` |
| `DECAY` | 0.7 per step | `score_context.DEFAULTS` |
| `join_cap` | 200 rows per join | `score_context.DEFAULTS` |
| query and affinity boosts | 1.0 each | `score_context.DEFAULTS` |
| aggregation corroboration, query match | 0.25, 1.5 | `context_aggregator.py` |

## 7. Limitations

- Keyword relevance is lexical: words, phrases and stems in the question, the intent vocabulary, and table and column names. A synonym the vocabulary does not list ("chilled") is not recognised.
- Greedy augmentation makes one best choice per step. An FK that is weak now but would lead to a very relevant table two joins later can be missed; raising `MAX_AUGMENTATION` reaches it, as with `temperature_logs` at step 4.
- Text and identifier terms in the query result itself (step 0) are not decayed, so with a single-row result they tend to rank above joined context. That is intended (the result is the most direct context), but joined context needs a query match to rise above them.
