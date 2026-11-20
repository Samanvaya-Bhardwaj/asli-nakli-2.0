# Context-aware document retrieval and the integrated answer

**What it does.** The query context that the four databases discovered (with SCORE, [PHASE3_CONTEXT_DISCOVERY.md](PHASE3_CONTEXT_DISCOVERY.md)) is used to search documents written by the organisations behind each source. The documents found are combined with the structured results into one explainable answer.

| | |
|---|---|
| Code | `data/generate_documents.py` (corpus); `integration/federation/doc_store.py` (ingestion, index and search, inside each source's service); `integration/federation/retrieval.py` (request, merge and integrated answer, at the coordinator) |
| Demo | `scripts/integrated_demo.py`; recorded run in `phase3/documentation/evidence/integrated_retrieval_demo.txt` |
| Evaluation | `scripts/eval_retrieval.py` |
| Tests | `tests/test_phase3_documents.py` (13) |

---

## 1. The documents

The repository had no document corpus. The only free text was a few short columns inside the databases (complaint descriptions, lab findings, alert messages) and generated HTML verification reports. So `data/generate_documents.py` writes **303 documents as files**, one folder per owning source.

| Folder (owner) | Documents | Formats |
|---|---|---|
| `data/documents/db1/` retail chain | 37 pharmacy incident reports | .md |
| `data/documents/db2/` distributors | 85 shipment notes, 3 cold-chain incident reports | .md |
| `data/documents/db3/` manufacturers | 17 product quality reviews (half-yearly, multi-section), 45 batch inspection reports, 42 product safety documents | .md |
| `data/documents/db4/` ministry | 3 recall notices, 9 regulatory investigation reports, 60 consumer complaint letters, 2 drug-alert bulletins | .html, .md, .txt |

- **Where they live.** Documents are stored with the source that owns them, as approved (decision N-2), and **not in any database table**. A test checks that the complaint letters' text is not in DB4's `complaints` table. In a deployment, each source's documents sit in its own data directory (`scripts/prepare_node_data.py` → `deploy/nodes/<db>/documents`, `ASALI_DOCS_DIR`), and the Docker image contains none.
- **Derived from real records.** Documents are generated from the structured data, so the codes, batches and companies they mention are real.
- **Written the way people write.** The header holds only doc_id, title, type, source and the date in the writer's own format. Identifiers appear only in the prose, sometimes damaged by the Phase 2 noise functions (`MED-ASAL1-OO9`, `med asali 009`). Brand names are sometimes misspelt.
- **Hard cases on purpose.** Documents about sibling batches one character apart, and reference documents that share only common words, are included because retrieval has to tell them apart.
- **Ground truth for evaluation only.** `data/documents/ground_truth.json` records what each document is truly about. Search never reads it.

## 2. Ingestion (`doc_store.DocStore`, per source, rebuilt when files change)

1. **Extract text.** Markdown and text files: a front-matter header and a body. HTML: tags stripped, with `<title>` and `<meta>` read.
2. **Clean.** Unicode NFKC, HTML entities, Markdown markup removed, whitespace collapsed. The header date in any format (`20/01/2025`, `June 07, 2025`, `10 Apr 2025`) is normalised to ISO by the Phase 2 date parser.
3. **Chunk.** By section and paragraph. A long section is cut into windows of about 120 words that overlap by 30. The quality reviews become 2–3 chunks.
4. **Metadata.** Document id, title, type, source, date, owning database, file and format, plus the extracted ids: medicine, batch, manufacturer, distributor, vendor, dispatch reference and complaint reference.
5. **Entities.**
   - **Medicine codes**, even damaged ones. Each is stored as written, in canonical form, and with a scanner-look-alike key.
   - **Other identifiers** (batch, dispatch, complaint and company ids), by pattern.
   - **Company names**, resolved to ids through the owner's own database. A manufacturer's report names the manufacturer, and DB3 knows its id.

   Measured against the ground truth, 91.6% of true medicine codes are linked (355 exact, 5 as look-alikes) with 95.0% precision. The rest are codes damaged beyond scanner look-alikes (e.g. `MED-4LBHZ-853` for MED-ALBNZ-853). They are kept as written but not linked: only look-alike glyph swaps are trusted, the safety rule from Phase 1.
6. **Index.** BM25 (k1 = 1.5, b = 0.75) over chunks, plus the entity lists.

## 3. Building the search from the context (`retrieval.build_search_request`)

The search is **not** the question alone. From the aggregated SCORE context it takes:

| Part | From | Weight |
|---|---|---|
| question words | the question (codes removed; they are matched as entities, so "MED-NAKALI-001" does not become the words *med* and *nakali*) | 1.0 |
| context terms | the top 15 non-numeric context terms (text words, categorical values) | 0.8 × term score / best score |
| anchor identifiers | the question's own codes, ids and batches, and what they resolved to | 1.0 |
| context identifiers | identifiers found through FK joins (the batch's pack code, its manufacturer, dispatch references) and identifiers shared by several databases | 0.5 |
| names | company, product and generic names from the context | name match |
| intents | the question's intents, which decide the preferred document types | |

The request is shown in readable form in every response (`document_search.request.display`). For example:

```
text: "Find information about batch BATCH-A009 manufactured by Biocon and identify any quality or safety concerns"
  + context terms: Biocon Biologics Ltd^0.43, biocon^0.34, 2025-06^0.29, Pen 3ml^0.25, Basalog 100 IU/ml^0.25, ...
  + identifiers:   batch_number=BATCH-A009^1.0, item_code=MED-ASALI-009^0.5, manufacturer_id=MFG-004^0.5
  + names:         Basalog 100 IU/ml, Biocon Biologics Ltd, Insulin glargine
  + intents:       safety, manufacturing
```

`MED-ASALI-009` and `MFG-004` were not in the question. DB3 found them by joining the batch's product row to its manufacturer.

## 4. Search and relevance (`DocStore.search`, inside each source)

```
lexical   = 1 - exp(-BM25_weighted / 6)           saturated to 0..1, comparable across sources
entity    = Σ matched identifier weight × request weight, capped at 2
              medicine code exact 1.0, scanner look-alike 0.85, batch 0.8, dispatch ref 0.6,
              manufacturer / distributor 0.35, vendor 0.25, company name 0.3
gate      = an entity match, OR ≥ 2 informative query terms (idf ≥ 1.5) with lexical ≥ 0.3
conflict  = × 0.25 when the request is about specific medicines or batches and the
              document names others but none of them
type      = × 1.25 when the document type suits the intent (cold chain → shipment notes,
              cold-chain incidents; recall → recall notices, investigations; ...)
recency   = × (1 + 0.1 × years since 2025-01-01, at most 1.5 years)
score     = (0.4 × lexical + 0.6 × entity / 2) × type × recency × conflict; returned if ≥ 0.15
```

- **Merging.** Every source scores its own documents with this same formula, and the coordinator merges them by score. The lexical part is saturated (not divided by each source's best score), so a weak best match in one collection does not look as strong as a good match in another.
- **Common words are not enough.** A document is not returned merely because it shares a common word. Without an identifier match it needs two informative words, and "Ltd", "www" and similar fragments do not count. A document about a *different* medicine is penalised below the cut-off; a test checks that sibling batches one character away are never returned.
- **What each result carries:** its score parts; the matched identifiers (with how each matched: exact or look-alike, and how it was written); the matched terms; the best chunk with the matches highlighted; reasons in words; and its evidence status.

## 5. The integrated answer (`retrieval.integrated_response`, in the result as `integrated`)

| Key | Content |
|---|---|
| **A_question** | the question |
| **B_structured_results** | `verified_facts`: statements the databases establish, each with its source record (the Phase 1 verdict; registration; blacklist; recall notice; cold-chain breach; lab result). `per_database`: native queries and row counts |
| **C_local_context** | each database's explored tables and its top SCORE terms with paths |
| **D_aggregated_context** | anchors, and the ranked terms with their reasons |
| **E_documents** | each document with title, type, date, **score and score parts (F)**, **provenance (G)** (owning database, file, chunk *n* of *m*, author), **why it was retrieved (H)**, the matching context, evidence status, and **links to structured entities** |
| policy | verified facts versus reported information; documents never change the verdict |

**Links to structured entities.** An exact code or id is a *reliable* link to the structured records that hold it ("matched in db1, db2, db3"). A look-alike code is *probable*. A name is *weak*.

**Verified versus reported.** Documents are labelled by who wrote them:
- official regulatory notice;
- regulatory finding;
- manufacturer's own record;
- distributor's operational record;
- pharmacy's report (not verified);
- consumer allegation (not verified).

An unverified report that alleges counterfeiting carries a **caution**: "An allegation in an unverified report, not proof of counterfeiting." It sits next to what the structured records say, e.g. "MED-NAKALI-001: blacklisted in DB4; verdict NAKALI", or "MED-NAKALI-002: not on the blacklist". The Phase 1 verdict is computed by the unchanged verification engine before any document is searched, and nothing in the document path can change it.

## 6. Evidence that the context matters

From `scripts/eval_retrieval.py`. Relevant = the document is truly about a medicine the question concerns. P@5 is capped when a question has fewer than five relevant documents.

| | P@5 | R@10 | nDCG@10 |
|---|---|---|---|
| search built from the SCORE context | **0.84** | **1.00** | **1.00** |
| the question alone | 0.78 | 0.93 | 0.95 |

The gain is concentrated where it should be: questions that name a **batch** and not a medicine code.
- "…batch BATCH-A009…": P@5 0.80 vs 0.60.
- "…batch BATCH-R002?": 1.00 vs 0.60.

The pack code reached through the FK join is what finds, for example, the shipment note for BATCH-A009. That note names only the pack code, never the batch. When the question already names the code, the identifier alone finds most documents, and the context mainly improves the order.

Changing the question changes the context and the documents. The test suite checks that the top-5 documents for the cold-chain, recall and counterfeit questions do not overlap at all.

## 7. Limitations

- The corpus is synthetic: generated, deterministic, derived from the structured data. Its language is more regular than real documents, and the ground truth comes from the same generator.
- Relevance is lexical plus identifiers (BM25 and entity matching); there is no semantic embedding. A synonym the documents use but the context does not ("chilled" for "refrigerated") is not bridged.
- Codes damaged beyond scanner look-alikes are not linked, on purpose. Linking them would need the Phase 2 probabilistic matcher, with its review step.
- Names are matched as exact phrases. A misspelt brand in a complaint letter is found through its code or other words, not through the name.
