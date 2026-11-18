# Unstructured text and ML

Part of the plan in `PLAN.md`. This file is the design for the unstructured-data requirement.

## 1. What was asked and what we do

The professor's clarification:
- the unstructured data is **text, not images**;
- use **ML algorithms** on it;
- **link** the text to the structured data, and use both to **verify** a medicine.

What we do:
1. Every organisation keeps its own text documents in its own vault. The text is never copied into the structured tables; only links and extracted facts are stored next to it.
2. When a document arrives, ML models decide what kind of document it is, find the codes, names, dates and temperatures in it, and link those mentions to structured records: a pack, a batch, a shipment, a product or an organisation. Each link has a confidence.
3. The pipeline pulls claims out of the text: "bought in Mumbai on 3 Nov", "the logger read 14 °C for 3 hours", "batch K/24/0091 failed dissolution".
4. When someone checks a pack, the verify engine fetches the documents linked to that pack, its batch and its shipments. It checks each claim against the structured history and applies the rules in `PLAN.md` section 12.4.

So text does two jobs: it explains a verdict, and under precise rules it can change one.

## 2. The text sources

| Owner | Document type (`doc_type`) | Kind | Typical content | Generated count |
|---|---|---|---|---|
| Pharma | `coa`: certificate of analysis | official | Batch, tests (assay %, dissolution %, related substances), pass or fail, release decision | 120 |
| Pharma | `batch_release_note` | official | Batch released to market, quantity, QA name | 60 |
| Pharma | `deviation_report` | official | A manufacturing problem on a batch, its impact, the action taken | 40 |
| Pharma | `recall_notice` | official | Product, lot, reason, level, what shops and patients should do | 15 |
| Distributor | `temperature_report` | operational | Shipment ref, logger id, readings as text lines, narrative, maximum temperature and duration | 120 |
| Distributor | `delivery_note` | operational | Shipment ref, cartons, vehicle, remarks | 80 |
| Distributor | `discrepancy_note` | operational | Shipment ref, expected count against received count, missing serials | 40 |
| Distributor | `damage_report` | operational | Shipment ref, what was damaged and how | 30 |
| Shop | `counter_note` | allegation | A staff note about a customer's report ("customer says strip looks different") | 80 |
| Shop | `return_note` | operational | Bill, pack, reason for return | 40 |
| Consumer | `consumer_complaint` | allegation | Free text, often informal; some in Hinglish (Hindi written in Latin letters) | 400 |
| Regulator | `nsq_alert` | official | A monthly list of "not of standard quality" batches: product, lot, manufacturer, failed test | 24 lists, 5–10 rows each |
| Regulator | `ban_order` | official | Product or lot banned, with the legal reason | 6 |
| Regulator | `inspection_report` | official | An inspection of a distributor or shop: findings, outcome | 40 |

About 1,200 documents in total. `kind` decides how much a document can weigh in a verdict (`PLAN.md` section 12.4).
- Official documents name an authority that stands behind them.
- Allegations are someone's claim.
- Operational documents are an organisation's own working records.

Examples of the tone the generator must produce:

```text
consumer_complaint (Hinglish):
  Maine 3 Nov ko Apna Chemist Andheri se Amoxil 500 liya. Strip ka colour pichli baar se alag hai
  aur expiry 08/2026 likha hai. Code TPM9-S346-Q37. Dawai se koi fayda nahi hua.

temperature_report:
  Shipment DSP-N-0042 (North Star Distributors to Sharma Medicos). Logger TL-22.
  12/11 09:10  6.1 C
  12/11 11:40  13.8 C
  12/11 14:30  14.2 C
  Reefer unit failed near Panipat. Temperature above 8 C for about 3 h 20 min. Cartons delivered.

nsq_alert:
  Drugs declared not of standard quality, October 2026.
  1. Amoxicillin Capsules IP 500 mg | B.No. K/24/0091 | Mfd by Kesar Biologics | Dissolution failed
  2. ...
```

## 3. How documents enter a vault

- **Staff** add documents in their portal's Documents screen, by pasting text or uploading a `.txt` or `.md` file. Choosing a type is optional, because the model predicts it.
- **Consumers** write a complaint in "Report a problem".
- **The system** writes some documents itself:
  - a recall notice when a pharma recalls a batch;
  - a regulator notice when the regulator issues an alert;
  - a discrepancy note when a receipt has missing packs.
- **The generator** (section 10) adds the starting corpus through the same portal endpoints.

Each document is stored as:
- the original text, in `/data/vault/text/<doc_id>.txt` in the org's volume;
- one Meilisearch document in the org's own `docs` index (section 5).

## 4. Ingest pipeline (`packages/asali_text`)

```
text ─> 4.1 clean + redact ─> 4.2 language ─> 4.3 type (M1) ─> 4.4 mentions ─> 4.5 link (M3)
     ─> 4.6 claims ─> 4.7 issue labels (M2, complaints only) ─> 4.8 index into own vault
```

Each step is one module with one public function, and each step is tested alone.

### 4.1 Clean and redact (`clean.py`)

1. Unicode NFKC; normalise whitespace; keep line breaks, because temperature readings are one per line.
2. Remove personal data before anything is stored or indexed. Replace with tokens: phone numbers (`[+91]` and 10 digits starting 6–9) → `[phone]`; e-mail addresses → `[email]`; 12-digit Aadhaar-like numbers → `[id]`.
3. Keep the original only when the author is staff of the same org. Consumer text is stored redacted only.

### 4.2 Language (`language.py`)

Tag `en`, or `hi-Latn` for Hinglish, by the share of tokens found in a list of 300 common Hinglish words (`hai, nahi, ka, ki, se, liya, dawai, alag...`). A threshold of 0.15 is enough; it is used only for reporting and for M2's features.

### 4.3 Document type: model M1 (`classify_type.py`)

- **Features:** TF-IDF of word 1–2-grams (min_df 2, sublinear tf) plus TF-IDF of character 3–5-grams (char_wb), joined with `FeatureUnion`. Character n-grams cope with Hinglish and typos.
- **Model:** `LinearSVC(C=1.0, class_weight="balanced")`, wrapped in `CalibratedClassifierCV(cv=3)` to get probabilities.
- **Output:** `doc_type`, `type_confidence`, and the top 2 alternatives.
- **When the staff-declared type disagrees** and the model's confidence is ≥ 0.8, show "This looks like a temperature report. You chose delivery note." Store both, and use the declared type.

### 4.4 Mentions (`mentions.py`)

These are rules and a gazetteer, not a learned model. Codes have a grammar, and rules over a grammar are more reliable than a classifier. ML is used where judgement is needed, in linking.

| Mention | How it is found |
|---|---|
| serial | Tokens of 11 Crockford characters, with or without the 4-4-3 hyphens, after `asali_codes` normalisation. Keep invalid ones, flagged; linking may correct them. |
| gtin | 14 digits; also 13 digits with a leading zero missing |
| lot | The three lot grammars (`PLAN.md` section 5.1), with a relaxed variant that allows spaces and confusables (`TP 24A0l7`), plus a label cue (`B.No`, `Batch`, `Lot`) for unknown formats |
| shipment ref | `DSP-…`, `CN-…`, `SHP-…`, `DC …`, `invoice …` patterns |
| product | Gazetteer of brand and generic names from every pharma's `/share/v1/products`, matched with `rapidfuzz.process.extract` (`token_set_ratio ≥ 85`). Strength found by the regex `\d+(\.\d+)?\s?(mg|mcg|ml|g|iu)`. |
| organisation | Gazetteer of org names from the directory, plus short forms ("Sharma Medical", "sharma medicos lajpat ngr"); `token_set_ratio ≥ 85` |
| city | Gazetteer of the cities in `cities.py`, plus common variants (Bombay → Mumbai, Bangalore → Bengaluru) |
| date | Formats `12/11/2026`, `12-11-26`, `12 Nov`, `3 Nov ko`, `Nov 2026`; a year without a date gets the document's year. Reuse the old flexible date parser's ideas. |
| expiry stated | A date after `exp`, `expiry` or `use before` |
| temperature | `\d+(\.\d+)?\s?°?\s?C`, with the line's time if a time is on the line |
| duration | `\d+\s?(h|hr|hours|ghante)`, `\d+\s?(min|minutes)` |

Each mention records its span (start, end), so the UI can highlight the sentence it came from.

### 4.5 Linking: model M3 (`link.py`)

**Candidate generation.** For each mention, find structured records it could refer to:

| Mention | Candidates |
|---|---|
| serial | `asali_codes.read` of the serial; if invalid, its correction candidates; then `/share/v1/units/exists` at the issuer → **unit** candidates |
| lot (+ product, if found) | Batches from the issuers' `/share/v1/batches`, within confusion cost ≤ 1.5 of the lot text, restricted to the matched product if a product was found → **batch** candidates |
| product | Products matched by the gazetteer, with the strength checked → **product** candidates |
| shipment ref | The writer's own shipments and shipments addressed to the writer, found by exact or near-exact ref → **shipment** candidates |
| organisation | The directory → **org** candidates |

**Features**, one vector per (document, candidate):

| # | Feature | Meaning |
|---|---|---|
| f1 | `code_cost` | Confusion-model cost between the mention and the candidate's key; 0 if exact |
| f2 | `code_exact` | 1 if exact |
| f3 | `product_name_sim` | `token_set_ratio / 100` between the product text in the document and the candidate's brand, generic and strength; 0 if no product mentioned |
| f4 | `strength_match` | 1 match, 0 no strength mentioned, −1 different |
| f5 | `maker_match` | The document names the candidate's manufacturer (1), names another one (−1), or names none (0) |
| f6 | `org_on_chain` | A mentioned shop or distributor is on the candidate's custody chain |
| f7 | `city_on_chain` | A mentioned city is a city on the candidate's chain |
| f8 | `date_plausible` | The document's dates fall within [mfg date, expiry + 90 days] for batches and units, or within ±10 days of the shipment date |
| f9 | `ambiguity` | log(1 + number of candidates for the same mention) |
| f10 | `writer_related` | The document's owner org is on the candidate's chain, or is its maker |
| f11 | `kind_official` | The document's kind is official |

- **Model:** `StandardScaler` + `LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000)`, calibrated with `CalibratedClassifierCV(method="sigmoid")` on the validation split. The probability is the link confidence.
- **Thresholds:**

  | Confidence | Result |
  |---|---|
  | ≥ 0.8 | Linked |
  | 0.6–0.8 | Possible link (shown, but weaker) |
  | below 0.6 | Dropped |

  `PLAN.md` section 12.4 uses ≥ 0.9 for official text to raise a do_not_use reason.
- **Explainability:** for each link, store the three features that contributed most (coefficient × scaled value). The UI shows them as "Linked because: exact serial match, the shop named is on this pack's route, the date fits."
- **Hierarchy:** a link to a unit implies its batch and product. A batch link implies its product. Store the most specific link and derive the others when querying.

### 4.6 Claims (`claims.py`)

These are rules per document type, over the mentions found:

| Doc type | Claims extracted |
|---|---|
| consumer_complaint, counter_note | `purchase_city`, `purchase_shop`, `purchase_date`, `stated_expiry`, `stated_lot` |
| temperature_report | `shipment_ref`, `max_temp_c`, `minutes_above_limit` (from the readings and the product's limit; if there are no readings, from the stated duration), `report_date` |
| nsq_alert, ban_order, recall_notice | Per row or notice: `product`, `lot`, `manufacturer`, `reason`, `action` |
| coa | `lot`, `result` (pass or fail), `failed_tests` |
| discrepancy_note | `shipment_ref`, `expected`, `received`, `missing_serials` |
| inspection_report | `org`, `outcome` (satisfactory, observations, licence action) |

### 4.7 Complaint issue labels: model M2 (`classify_issue.py`)

- **Labels** (multi-label): `suspected_fake`, `packaging_different`, `no_effect`, `side_effect`, `expired_or_near_expiry`, `overcharged`, `damaged_pack`, `wrong_medicine`, `other`.
- **Features:** the same TF-IDF union as M1.
- **Model:** `OneVsRestClassifier(LogisticRegression(class_weight="balanced", max_iter=1000))`. Each label's threshold is chosen on the validation split to maximise F1, then frozen.

### 4.8 Index (`index.py`)

Write the document to the org's own Meilisearch `docs` index (section 5) and save the original text file. Link records are also mirrored into the org's database table `document_links(doc_id, entity_type, entity_key, confidence, linked_at)`. These are small structured facts about the text, not the text.

### 4.9 Re-linking

A link can only be made to records that exist when the document arrives. A complaint about a pack sold tomorrow can't link today. So a background task in each node, every 10 minutes, re-runs 4.4–4.8 on documents that have no link at ≥ 0.8 and are less than 90 days old. It runs immediately for a document whose claims mention an entity the org just received.

## 5. The vault: Meilisearch index `docs`

One Meilisearch instance per org, with one index `docs`.

| Field | Type | Searchable | Filterable |
|---|---|---|---|
| `id` | string | | |
| `org_id` | string | | yes |
| `doc_type`, `doc_type_declared`, `kind` | string | | yes |
| `title` | string | yes | |
| `body` | string (cleaned, redacted) | yes | |
| `language` | string | | yes |
| `created_at` | int (unix) | | yes, sortable |
| `link_ids` | string[], e.g. `unit:08901001000124/TPM9S346Q37`, `batch:08901003000078/K/24/0091`, `shipment:dist-north/DSP-N-0042`, `product:08901001000124`, `org:shop-mumbai` | | yes |
| `links` | object[] `{entity_type, entity_key, confidence, top_features}` | | |
| `mentions` | object, lists per mention type | | `mentions.lots`, `mentions.serials` |
| `claims` | object[] | | |
| `issue_labels` | string[] | | yes |

Keys, created by the app at start-up using the master key:
- an **admin key** scoped to `docs`, used by the ingest pipeline;
- a **search key** with `actions: ["search"]` and `indexes: ["docs"]`, used only by the share API router.

The share router never holds the admin key.

## 6. Checking text against structured data

### 6.1 The structured facts available

For a pack, the verify engine already has:
- its history (events with org, city and time);
- its product (including storage limits);
- its batch (status, dates);
- the shipments that carried it (refs per hop);
- regulator alerts and licences.

### 6.2 Claim checks (`verify/text_checks.py`)

| Claim | Compared with | Result |
|---|---|---|
| `purchase_city` | The city of the sell event | consistent / contradicts / unknown (no sell event) |
| `purchase_shop` | The selling org's name (`token_set_ratio ≥ 85`) | consistent / contradicts / unknown |
| `purchase_date` | The sell event date, ±3 days | consistent / contradicts / unknown |
| `stated_expiry` | The batch expiry at the issuer | consistent / contradicts |
| `stated_lot` | The pack's lot | consistent / contradicts |
| `max_temp_c` and duration, for a shipment that carried the pack | The product's `storage_max_c` | excursion yes / no |
| nsq / recall row (`lot`, `manufacturer`) | The pack's lot and manufacturer | match / partial (lot only) / no |
| coa `result` | The batch status | shown as evidence; a fail on a released batch is shown as "Certificate reports a failed test" (caution only through `QUALITY_NOTICE_POSSIBLE`) |

### 6.3 How the checks feed the reasons

These are the `PLAN.md` section 12.2 reasons, restated for text:
- **Excursion yes** on a cold-chain product, from a temperature report linked at ≥ 0.8 to a shipment on the pack's route → `COLD_CHAIN`.
- **An nsq row matching** lot and manufacturer, in a regulator document linked at ≥ 0.9 → `QUALITY_FAILED`. A partial match, or confidence 0.6–0.9 → `QUALITY_NOTICE_POSSIBLE`.
- **A recall notice** from the issuer, linked at ≥ 0.9 → `RECALLED`. Normally the structured batch status says so too; the text is then the attached evidence.
- **A complaint whose claims contradict** the structured sale (city, shop or date), or the stated expiry or lot → `TEXT_CONTRADICTION` (caution). If `COPIED_CODE` is also raised from structured data, the complaint is shown as supporting evidence: "A customer in Mumbai reports buying this code on 3 Nov. Records show it was sold in Delhi on 1 Nov."
- **Several complaints** → `COMPLAINT_CLUSTER`, after de-duplication (6.5).

### 6.4 Why contradictions matter

A copied code is the most common real counterfeit: a genuine code printed on many fake packs. The structured data sees one pack's legitimate path. Only the text from the people holding the copies shows the other places that code turned up. Linking that text to the structured record and finding the contradiction is how unstructured data catches what structured data alone misses. This is the core of the professor's "link and verify".

### 6.5 De-duplication and clusters: models M4 and M5 (`clusters.py`)

- **M4, near-duplicate complaints:**
  - TF-IDF vectors (M1's vectoriser) and cosine similarity;
  - two complaints with similarity ≥ 0.9, from the same consumer node, linked to the same batch, within 7 days count as one;
  - the threshold is chosen on the validation split by the generator's duplicate labels.
- **`COMPLAINT_CLUSTER`:** after M4, 3 or more independent complaints linked to the same batch at ≥ 0.8, from 2 or more cities, with a label in {suspected_fake, packaging_different, no_effect}.
- **M5, unusual batch, for the regulator screen:**
  - expected complaints for a batch = network complaint rate per sold pack × packs of that batch sold;
  - flag the batch when `scipy.stats.poisson.sf(k − 1, expected) < 0.01` and k ≥ 3;
  - shown on the regulator's Complaints screen, not used in a consumer verdict.

## 7. Retrieval during a verification (`verify/documents.py`)

1. **Context.** From the trace, collect:
   - keys `unit:<gtin>/<serial>`, `batch:<gtin>/<lot>`, `product:<gtin>`;
   - `shipment:<org>/<ref>` for every ship event on the route;
   - `org:<id>` for every org on the route;
   - the brand and generic names, the cities on the route, and the window [mfg date, today].
2. **Which vaults.** Every org on the route, the issuer, the regulator, and every consumer node: at most 8 calls, in parallel, inside the 6 s budget.
3. **Two queries per vault**, through `/share/v1/documents/search`:
   - **Linked:** `filter: link_ids IN [<all keys>]`, sorted by `created_at` desc, limit 20.
   - **Possible:** `q: "<brand> <generic> <lot>"` with `filter: doc_type IN [nsq_alert, recall_notice, ban_order, temperature_report, consumer_complaint] AND created_at >= <mfg date>`, limit 10. The asking node re-runs M3 on these against this pack's context and keeps those at ≥ 0.6. This catches documents that couldn't link when they arrived and haven't been re-linked yet.
4. **Rank:**
   - `score = link_confidence × kind_weight × recency`;
   - `kind_weight`: official 1.0, operational 0.8, allegation 0.6;
   - `recency = exp(−age_days / 365)`;
   - keep at most 10, and at most 4 of any one doc type;
   - de-duplicate by `doc_id`.
5. **Check claims** (6.2) and attach the results.

`DocHit`, as returned in the verification result:

```json
{
  "doc_id": "consumer-mumbai:doc_01J...",
  "org_id": "consumer-mumbai", "org_name": "Consumer portal, Mumbai",
  "doc_type": "consumer_complaint", "kind": "allegation",
  "title": "Complaint from Andheri, 3 Nov 2026",
  "created_at": "2026-11-04T10:12:00+05:30",
  "snippet": {"text": "Code TPM9-S346-Q37. Dawai se koi fayda nahi hua.", "highlights": [[5, 18]]},
  "linked_to": [{"entity": "unit:08901001000124/TPM9S346Q37", "confidence": 0.94,
                 "because": ["exact serial match", "city on the route: no", "date fits"]}],
  "claims": [{"name": "purchase_city", "value": "Mumbai", "check": "contradicts",
              "against": "Sold by Sharma Medicos, Delhi on 1 Nov 2026"}],
  "issue_labels": ["packaging_different", "no_effect"],
  "label": "Reported by a customer, not verified",
  "served_by": {"org_id": "consumer-mumbai", "host_name": "PC-A"}
}
```

## 8. Verdict integration

These are the rules in `PLAN.md` sections 12.2–12.4; this file defines the inputs they use. A summary for the report:

| Text evidence | Can raise | Never raises |
|---|---|---|
| Official notice (regulator NSQ, ban, recall; pharma recall), link ≥ 0.9, match on lot and maker | `QUALITY_FAILED` or `RECALLED` (do_not_use) | |
| Official, link 0.6–0.9, or a partial match | `QUALITY_NOTICE_POSSIBLE` (caution) | do_not_use |
| Temperature report on the pack's route, excursion on a cold-chain product | `COLD_CHAIN` (caution) | do_not_use |
| A single complaint | Nothing; shown as an allegation | anything |
| Complaints contradicting the record, or a cluster | `TEXT_CONTRADICTION`, `COMPLAINT_CLUSTER` (caution) | do_not_use |

## 9. Evaluation

### 9.1 Data splits

- **Generated corpus.** Every template family (section 10) has an id. Families are split 70 / 15 / 15 into train, validation and test. The test set contains no phrasing seen in training, which keeps "100% because the test text is the training text" from happening.
- **Hand-written set** (`ml/data/handwritten/`):
  - The team writes 60 documents themselves, in their own words: at least 25 complaints (some in Hinglish), 10 temperature reports, 10 official notices and 15 others.
  - Labels go in `labels.jsonl` (type, issue labels, the correct links, the expected claim values). `ml/data/handwritten/README.md` explains the format.
  - **The implementing agent must not write these documents.** If the folder is empty, the evaluation report says "Hand-written set: not yet provided" in its first line.

### 9.2 Metrics and targets

The targets are fixed now and aren't tuned on the test sets. If one is missed, report the miss; don't adjust thresholds on test data.

| Component | Metric | Target (generated test) | Hand-written set |
|---|---|---|---|
| M1 type | macro-F1 | ≥ 0.90 | reported |
| M2 issues | micro-F1 | ≥ 0.80 | reported |
| Mentions: serial, lot, shipment ref | precision / recall | ≥ 0.98 / ≥ 0.95 | reported |
| Mentions: product, org, city | precision / recall | ≥ 0.90 / ≥ 0.85 | reported |
| M3 linking at ≥ 0.8 | precision / recall | ≥ 0.95 / ≥ 0.85 | reported |
| M3 calibration | Brier score; reliability plot saved as a PNG chart in the evidence | reported | reported |
| M4 duplicates | F1 | ≥ 0.85 | n/a |
| Retrieval in verification | recall@10 of truly linked documents | ≥ 0.90 | n/a |
| Retrieval in verification | unrelated documents in the top 10, on average | ≤ 1 | n/a |
| Ablation | M3 against the baseline "exact code match only" | Report both; M3 should find the noisy and name-only mentions the baseline misses | |

- `python -m asali_text.evaluate` writes `docs/evidence/ml/report.md` and `metrics.json`, with confusion matrices for M1 and M2.
- The report starts with the date, the commit hash and the dataset sizes.

## 10. Corpus generator (`ml/generate_corpus.py`)

- **Built from the seeded network.** It runs after the network is seeded (milestone M5), reads the real packs, batches, shipments and sales through the share APIs, and writes documents that refer to them. Its answer key holds the true links and claims.
- **Families.** Each `doc_type` has 6–10 template families. A family is a sentence plan with slot banks: products, places, problems, times. Paraphrase banks give 3–6 wordings per sentence slot.
- **Noise**, applied after filling the slots, with probabilities set per family:
  - keyboard-neighbour typos;
  - code misreads, the inverse of the confusion model: 0→O, 1→I, 5→S;
  - missing hyphens; lowercase codes;
  - name variants ("sharma medical", "apna chemists andheri");
  - Hinglish: 25% of complaints, 10% of counter notes;
  - irrelevant extra sentences;
  - date-format variety.
- **Hard negatives,** so linking has to work:
  - complaints naming a real product with a lot that belongs to a different product;
  - lots one edit away from a real lot;
  - shop names close to a real shop in another city;
  - NSQ lists that include batches from outside our network.
- **Planted scenario documents.** S3's Mumbai complaints about the Delhi-sold serial, S5's NSQ row for kesar's batch, S6's temperature report.
- **Duplicates:** 5% of complaints get a near-copy, for M4.
- **Output:**
  - `ml/data/generated/<split>/<doc_type>/<doc_id>.txt`;
  - `ml/data/generated/truth.jsonl`: doc_id, owner org, doc_type, kind, family_id, split, issue labels, true links, true claims, duplicate_of.
  - When used for seeding, the generator posts each document to its owner org's portal API, so the real ingest pipeline processes it.
- **Determinism:** `--seed 42`, which gives the same corpus every time.

## 11. Code layout

```
packages/asali_text/
  asali_text/
    clean.py  language.py  classify_type.py  mentions.py  gazetteer.py
    link.py  features.py  claims.py  classify_issue.py  clusters.py  index.py
    pipeline.py            # ingest(text, owner_org, declared_type, context) -> IngestResult
    train.py               # python -m asali_text.train --corpus ml/data/generated --out ml/models
    evaluate.py            # python -m asali_text.evaluate ...
    models.py              # load/save joblib with a version and a training-data hash
  tests/
ml/
  generate_corpus.py  templates/<doc_type>/*.yaml  data/generated/  data/handwritten/  models/
services/node/asali_node/verify/
  documents.py  text_checks.py
```

Library versions: `scikit-learn` 1.5+, `rapidfuzz` 3.x, `scipy`, `numpy`, `joblib`. Pin exact versions in `pyproject.toml` when M0 installs them. Models are saved to `ml/models/` with a short `MODEL_CARD.md`: data, features, metrics and known weaknesses. They are under 10 MB in total, so they are committed and copied into the node image.

## 12. What to say in the viva

- **Why classical ML?** The documents are short and the labels are known. A linear model over TF-IDF is accurate on this kind of text, trains in seconds, and can be explained feature by feature.
- **Why rules for codes and ML for links?** A code has a grammar, so it is extracted by rules. Whether a code, a name and a date in a complaint refer to this pack is a judgement made from several weak signals. Weighing those signals is what the ranker learns.
- **How do we know it works?** Held-out template families, a hand-written set, calibration, and an ablation against exact matching.
- **Why text can't condemn a pack alone:** an unverified complaint is an allegation. Official notices and corroborated patterns can count, and the rules in `PLAN.md` section 12.4 say exactly how much.
