# Asali Network: plan for the rebuilt system

Status: plan only. Nothing in `asali-net/` is implemented yet.
Companion files in this folder:

| File | What it holds |
|---|---|
| `PLAN.md` (this file) | What we build and why: organisations, data, sharing, codes, correction, verification, deployment, testing |
| `TEXT_ML.md` | The unstructured part: text documents, the ML models, how text is linked to and checked against structured data |
| `DESIGN.md` | The portal UI: design rules, components, screens, motion, the banned-pattern list, writing rules |
| `TASKS.md` | The build, milestone by milestone, as small tasks with files, interfaces and checks |
| `AGENT_PROMPT.md` | The prompt to hand to the implementing agent |
| `test-vectors/codes.json` | Check-digit and parsing cases every implementation must pass |

The old Phase 1–3 code stays in the repository root, untouched. It is the previous coursework and the source of a few reused algorithms (section 19).

---

## 1. What we are building

### 1.1 The professor's feedback

- Every pharma company, every distributor and every shop keeps its own database. Each one stores data in its own way.
- Nothing is central. An organisation lets others read its data; nobody can write into another organisation's database.
- Each organisation has a portal:
  - **Pharma** registers the packs it makes and records which distributor it sends them to.
  - **Distributor** scans packs as they arrive, then scans them again to record which shop they go to. This is saved in the distributor's own database.
  - **Shop** scans packs as they arrive and scans them again when it sells them. A shop's portal reflects where it is: city, state, local alerts, receipt language.
  - **User** (a patient or buyer) scans a pack to check it.
- One UI codebase serves every portal. We run 2–3 portals of each kind.
- The system runs on four PCs, one kind of portal per PC. It must behave like a real multi-site system, not a program on one computer.
- Part of the data must be unstructured. The professor's clarification: text only, no images. Use ML on the text, link the text to the structured data, and use the two together to verify a medicine.
- Codes read by scanners or typed by people contain wrong characters. The system must fix what it can and say plainly when it can't.

### 1.2 The system in one paragraph

Twelve organisations run on four PCs. Each one has its own portal, its own database (PostgreSQL, MongoDB or SQLite, each with a different schema) and its own text vault. Every write goes into the writer's own database. Every read of another organisation goes through that organisation's read-only sharing API, which connects to its database with a read-only account. A small directory service plays the part DNS plays on the internet: it holds addresses and public keys, and never medicine data.

To check a pack, the asking portal follows the pack hop by hop, using the "shipped to" references in each organisation's records:
- maker → distributor → shop → sale;
- alongside the hops, regulator alerts, consumer scan counts, and text documents that ML models have linked to this pack, its batch or its shipments.

The answer is one of four plain verdicts, each with its reasons and its evidence.

### 1.3 Words used in this plan

| Word | Meaning |
|---|---|
| Organisation (org) | One pharma company, distributor, shop, consumer portal or regulator. Each runs as one node. |
| Node | One running org: its app container, its database and its vault. |
| Portal | The web UI of a node. Same codebase everywhere; what it shows depends on the org's type and settings. |
| Pack / unit | One saleable pack with a unique serial number. |
| GTIN | The 14-digit product number (GS1 standard). It identifies the product, not the pack. |
| Lot | The batch number. |
| Event | Something an org recorded about a pack: made, shipped, received, sold, returned, destroyed. |
| Share API | Each node's read-only HTTP API (`/share/v1/...`), the only way other orgs see its data. |
| Portal API | Each node's own write API (`/api/...`), used only by its own staff through its own portal. |
| Vault | Each node's store of text documents (Meilisearch index plus the text files). |
| Directory | The address book of the network. No medicine data. |

---

## 2. Decisions

These are decided so the implementing agent never has to guess. All decisions below are confirmed (18 Nov 2026), including D11 naming: product name Asali, plain-English verdicts.

| # | Decision | Why |
|---|---|---|
| D1 | Build in a new folder `asali-net/` on a new branch `v2-network`. Old Phase 1–3 code is not modified. | Phase 1–3 is graded coursework and the comparison point. |
| D2 | 12 orgs: 3 pharma, 3 distributors, 3 shops, 2 consumer portals, 1 regulator. (confirmed by the team, 18 Nov 2026) | The professor said 2–3 of each. The regulator holds recalls, quality notices and licences, which verification needs and which no pharma or shop would own. |
| D3 | Backend: Python 3.11, FastAPI, one codebase that runs as any org type, chosen by environment variables. | The team knows Python. One codebase means one set of tests. |
| D4 | Storage engines differ by org: PostgreSQL 16, MongoDB 7, SQLite. Each org's schema is also different (section 5). | The professor wants "different structures to store". Three engines and nine schema styles give real heterogeneity without too many moving parts. |
| D5 | Unstructured data is text only: plain text and Markdown documents. Each org keeps its own in its own Meilisearch vault. (confirmed by the team, 18 Nov 2026) | The professor said text, no images. Meilisearch has built-in read-only search keys, a natural fit for read-only sharing, and needs about 60 MB of RAM, which suits the 8 GB PCs. |
| D6 | ML is scikit-learn: TF-IDF features, linear classifiers, a logistic-regression link ranker, TF-IDF clustering. No deep learning. | It trains in seconds on a laptop, is explainable in a viva, and runs on 8 GB machines. Section 13 and `TEXT_ML.md`. |
| D7 | Frontend: React 19, Vite, TypeScript, Tailwind CSS v4, shadcn/ui (Radix), Motion, TanStack Query, React Router. | The professor asked for a modern UI. These are standard, well documented, and work together. `DESIGN.md`. |
| D8 | Orchestration: Docker Compose on each PC, one stack per PC, generated from one file `infra/network.yaml`. Not Docker Swarm or Kubernetes. (confirmed by the team, 18 Nov 2026) | Swarm's overlay network is unreliable on Docker Desktop for Windows and Mac, and two of our PCs are 8 GB laptops. Per-PC Compose plus a directory service is how many real multi-site systems work. |
| D9 | All traffic is HTTPS. Caddy runs on every PC, with certificates from one shared mkcert authority. | Browsers allow the camera only on HTTPS pages, and nodes must not talk in plain text on a shared network. |
| D10 | Pack codes follow GS1: GTIN plus serial, lot and expiry, in a QR code as a GS1 Digital Link URL, with a human-readable line under it. The serial is 11 characters of Crockford Base32 and ends in a check character. | Real-world standard. India already requires QR codes on many medicines. Crockford Base32 has no I, L, O or U, so the commonest misreads can be undone exactly. |
| D11 | Verdicts are words, not scores: **Genuine**, **Caution**, **Do not use**, **Cannot check**. Each comes with reasons and evidence. | The old 0–100 trust score claimed a precision the system doesn't have. |
| D12 | Text can change a verdict only under the rules in section 12.4. An unverified customer complaint never proves a pack fake by itself. | Same safety rule as Phase 3, now with a precise way for official text and corroborated complaints to count. |
| D13 | Every new code file is snapshotted before its first run, and every later fix is logged, under `asali-net/docs/vibe/`. | The course asks for the original prompt, the generated code and the modified code. |
| D14 | Camera barcode decoding uses a library (it only reads the code). No OCR, no image storage, no image ML. | The professor ruled out images for the unstructured part. Decoding a QR is input, not data. |

---

## 3. Hardware and what runs where

| PC | Machine | RAM | Role | Orgs it hosts |
|---|---|---|---|---|
| PC-A | Windows, Intel i7 H-series | 16 GB | People: directory, regulator, consumers | `directory`, `regulator` (PostgreSQL), `consumer-delhi` (SQLite), `consumer-mumbai` (MongoDB) |
| PC-B | Mac, Apple M4 | 16 GB | Pharma | `tarang` (PostgreSQL), `medivra` (MongoDB), `kesar` (SQLite) |
| PC-C | Windows, Ryzen 5 U-series | 8 GB | Distributors | `dist-north` Delhi (PostgreSQL), `dist-west` Mumbai (MongoDB), `dist-south` Bengaluru (SQLite) |
| PC-D | Windows (this PC) | 8 GB | Shops | `shop-delhi` (SQLite), `shop-mumbai` (PostgreSQL), `shop-bengaluru` (MongoDB) |

Why this placement:
- The consumer and regulator nodes ask every other node during a check and run ML at query time. They get a 16 GB machine, and so does the directory, which everyone depends on.
- The 8 GB PCs each run about 1.2 GB of containers. Each PC runs at most one PostgreSQL, one MongoDB and three small Meilisearch instances. MongoDB's cache is capped at 256 MB.
- The Mac needs arm64 images. PostgreSQL, MongoDB, Meilisearch and Caddy all publish them. The app image is built on each PC, so it is native everywhere.
- Every PC can also run the whole network alone in simulation mode (section 16.6). A 16 GB PC is recommended for that. The UI labels simulation mode clearly.

Ports (HTTPS, served by Caddy on the PC that hosts the org):

| Org type | Ports |
|---|---|
| Distributors | 8101 `dist-north`, 8102 `dist-west`, 8103 `dist-south` |
| Shops | 8201 `shop-delhi`, 8202 `shop-mumbai`, 8203 `shop-bengaluru` |
| Pharma | 8301 `tarang`, 8302 `medivra`, 8303 `kesar` |
| People | 8400 `directory`, 8401 `regulator`, 8402 `consumer-delhi`, 8403 `consumer-mumbai` |

Ports are fixed per org, not per PC, so the simulation can run everything on one machine without clashes. Databases and Meilisearch are never published to the LAN. Only Caddy's ports are.

---

## 4. Architecture

```
            PC-A (people)                          PC-B (pharma)
  ┌───────────────────────────────┐      ┌───────────────────────────────┐
  │ Caddy :8400-8403 (TLS)        │      │ Caddy :8301-8303 (TLS)        │
  │  directory  (SQLite)          │      │  tarang   app + Postgres + vault│
  │  regulator  app+Postgres+vault│      │  medivra  app + Mongo    + vault│
  │  consumer-delhi app+SQLite+vlt│      │  kesar    app + SQLite   + vault│
  │  consumer-mumbai app+Mongo+vlt│      └───────────────┬───────────────┘
  └───────────────┬───────────────┘                      │
                  │        LAN or Tailscale (HTTPS only)  │
  ┌───────────────┴───────────────┐      ┌───────────────┴───────────────┐
  │ Caddy :8101-8103 (TLS)        │      │ Caddy :8201-8203 (TLS)        │
  │  dist-north app+Postgres+vault│      │  shop-delhi app+SQLite+vault  │
  │  dist-west  app+Mongo   +vault│      │  shop-mumbai app+Postgres+vlt │
  │  dist-south app+SQLite  +vault│      │  shop-bengaluru app+Mongo+vlt │
  └───────────────────────────────┘      └───────────────────────────────┘
            PC-C (distributors)                    PC-D (shops)
```

Inside every node, all from the same image:

```
  browser ──HTTPS──> Caddy ──> app container (FastAPI)
                                 ├─ /            the built React portal (static files)
                                 ├─ /api/...     portal API: staff login, writes to OWN db (read-write account)
                                 ├─ /share/v1/.. share API: GET only, signed callers, OWN db via READ-ONLY account
                                 ├─ network client: signs requests, calls other nodes' share APIs, caches the directory
                                 ├─ verify engine: trace + rules + text evidence (runs in whichever node asks)
                                 └─ text pipeline: ingest, ML classify, extract, link, index into OWN vault
                               db container (Postgres / Mongo) or SQLite file in the app's volume
                               vault container (Meilisearch) + text files in the app's volume
```

What is central, and what is not:
- **Central: the directory only.** It holds org id, type, name, city, state, base URL, public key, serial issuer code, GS1 company prefix, host name and last-seen time. Nodes cache it on disk and keep working from the cache if it goes down.
- **Not central: everything else.** There is no shared database, no warehouse and no coordinator that owns data. Any node can run a verification, because the verify engine is part of every node. Consumers and the regulator use it most.

Classic information-integration parts, so the report can name them:

| Concept | Where it lives |
|---|---|
| Sources | 12 org databases plus 11 text vaults. The directory has no medicine data and no vault. |
| Wrappers | One adapter per org that maps its native schema to the canonical model (sections 5–6) |
| Mediator | The verify engine in each node |
| Query plan | A dependent ("bind") join along the custody chain. Each hop's query needs the previous hop's answer, the `to_org` of the last shipment. Independent side queries (alerts, scans, documents) run in parallel. |
| Entity resolution | Code correction (section 10) and text-to-record linking (`TEXT_ML.md`) |
| Provenance | Every fact in a result carries the org that said it and the host that served it |

---

## 5. Organisations and their native storage

Each adapter maps one org's native schema to the canonical model. Field names, date formats, status codes and structure deliberately differ. The tables below are the starting schemas; the implementing agent writes them as DDL or validators in `services/node/asali_node/schemas/<org_id>/`.

### 5.1 Pharma

**`tarang`: Tarang Pharma, PostgreSQL, normalised, snake_case.** Serial issuer `TP`, GS1 prefix `8901001`, lot style `TP24A017` (year, month letter A–L, number).

```sql
products(gtin char(14) PK, brand_name text, generic_name text, strength text, dosage_form text,
         pack_size int, storage_min_c numeric, storage_max_c numeric, schedule text)
batches(lot text PK, gtin char(14) FK->products, mfg_date date, expiry_date date,
        quantity int, status text CHECK (status IN ('released','quarantine','recalled')))
units(serial char(11) PK, gtin FK->products, lot FK->batches, status text CHECK (status IN ('commissioned','shipped','destroyed')),
      commissioned_at timestamptz)
shipments(shipment_id text PK, to_org_id text, shipped_at timestamptz, vehicle_no text, created_by text)
shipment_units(shipment_id FK->shipments, serial FK->units, PRIMARY KEY (shipment_id, serial))
recalls(recall_id text PK, lot FK->batches, reason text, level text, issued_at timestamptz)
staff(username PK, password_hash, role, display_name)
```

**`medivra`: Medivra Labs, MongoDB, embedded documents, camelCase.** Issuer `MV`, prefix `8901002`, lot style `MV-2410-033`.

```js
skus         { _id: "<gtin>", brand, molecule, strengthMg, form, packOf, storage: { minC, maxC } }
lots         { _id: "MV-2410-033", sku: "<gtin>", made: ISODate, expires: ISODate, qty,
               recall: null | { reason, at, level },
               units: [ { sn: "MV....", state: "C"|"S"|"D", out: null | { consignment, to, at } } ] }
consignments { _id: "CN-...", consignee: "<org_id>", dispatchedAt: ISODate, lines: [ { sku, lot, sns: [...] } ] }
staff        { _id: username, hash, role, name }
```
With more than 5,000 units, a lot's `units` array becomes a separate `units` collection. Agent rule: keep the embedded design; seed data stays under 2,000 units per lot.

**`kesar`: Kesar Biologics, SQLite, legacy ERP style.** UPPER_CASE abbreviations, dates as text in Indian format, single-letter status codes, and distributors identified by an internal party code that must be mapped to network org ids. Issuer `KS`, prefix `8901003`, lot style `K/24/0091`.

```sql
ITEM_MST(ITEM_CD TEXT PK, GTIN TEXT UNIQUE, ITEM_DESC TEXT, MOL_DESC TEXT, STR TEXT, UOM TEXT, STOR_TEMP_TXT TEXT /* "2-8 C", "BELOW 25 C" */)
LOT_MST(LOT_NO TEXT PK, ITEM_CD FK, MFG_DT TEXT /* DD/MM/YYYY */, EXP_DT TEXT /* MM/YYYY */, LOT_STAT TEXT /* A,Q,R */)
SRL_MST(SRL_NO TEXT PK, LOT_NO FK, SRL_STAT TEXT /* C,D,X */, CRT_TS TEXT)
PARTY_MST(PARTY_CD TEXT PK, PARTY_NM TEXT, NET_ORG_ID TEXT)
DSP_HDR(DSP_NO TEXT PK, PARTY_CD FK, DSP_DT TEXT, TRUCK_NO TEXT)
DSP_DTL(DSP_NO FK, SRL_NO FK, PRIMARY KEY(DSP_NO, SRL_NO))
RCL_REG(RCL_NO TEXT PK, LOT_NO FK, RCL_RSN TEXT, RCL_DT TEXT)
USR_MST(USR_ID PK, PWD_HASH, USR_ROLE, USR_NM)
```

### 5.2 Distributors

**`dist-north`: North Star Distributors, Delhi, PostgreSQL**, separate receipt and dispatch tables:
```sql
receipts(receipt_id PK, from_org_id, source_ref /* sender's shipment id */, received_at timestamptz, received_by)
receipt_items(receipt_id FK, gtin, serial, PRIMARY KEY(receipt_id, serial))
dispatches(dispatch_id PK, to_org_id, dispatched_at timestamptz, vehicle_no)
dispatch_items(dispatch_id FK, gtin, serial, PRIMARY KEY(dispatch_id, serial))
staff(...)
```
Stock is a view: received serials minus dispatched serials.

**`dist-west`: Western Medilink, Mumbai, MongoDB**, a single event-sourced collection:
```js
movements { _id, dir: "IN"|"OUT", party: "<org_id>", at: ISODate, ref: "<sender shipment id or own dispatch id>", items: [ { g: "<gtin>", s: "<serial>" } ] }
staff { ... }
```

**`dist-south`: Dakshin Pharma Agencies, Bengaluru, SQLite**, keeps the raw scanned text next to the parsed values:
```sql
inward(entry_id INTEGER PK, supplier_org TEXT, dc_number TEXT, entry_date TEXT /* YYYY-MM-DD */)
inward_lines(entry_id FK, barcode_raw TEXT, gtin TEXT, sn TEXT, lot TEXT, exp TEXT, corrected INTEGER /* 0/1 */)
outward(entry_id INTEGER PK, customer_org TEXT, invoice_no TEXT, entry_date TEXT)
outward_lines(entry_id FK, barcode_raw TEXT, gtin TEXT, sn TEXT)
users(...)
```

### 5.3 Shops

Every shop has location settings: `city`, `state`, `state_code`, `receipt_language` (en, hi, mr, kn), `drug_licence_no`, `gstin`.

**`shop-delhi`: Sharma Medicos, Lajpat Nagar, Delhi, SQLite**, purchase/sale bills:
```sql
purchases(pur_id PK, distributor_org, bill_no, bill_date)
purchase_items(pur_id FK, gtin, sn, lot, exp)
sales(bill_no PK, sold_at, customer_ref_hash /* sha256 of last 4 phone digits + shop salt, or NULL */, total_paise INTEGER)
sale_items(bill_no FK, gtin, sn, mrp_paise INTEGER)
returns(ret_id PK, bill_no FK, sn, reason, at)
users(...)
```

**`shop-mumbai`: Apna Chemist, Andheri, Mumbai, PostgreSQL**, one ledger table:
```sql
inventory_ledger(entry_id bigserial PK, kind text CHECK (kind IN ('IN','SALE','RETURN','DAMAGE')),
                 gtin char(14), serial char(11), counterparty text, doc_no text, at timestamptz)
bills(doc_no PK, at timestamptz, amount_paise int, customer_ref_hash text)
staff(...)
```

**`shop-bengaluru`: Namma Pharmacy, Jayanagar, Bengaluru, MongoDB**, one document per pack:
```js
stock { _id: "<gtin>/<serial>", in: { from: "<org_id>", at: ISODate, ref }, sale: null | { bill, at }, ret: null | { at, why } }
bills { _id: billNo, at, lines: [ "<gtin>/<serial>", ... ], amountPaise, customerRef }
staff { ... }
```

### 5.4 Consumers and regulator

**`consumer-delhi`, SQLite:**
```sql
checks(check_id PK, raw_input, gtin, serial, verdict, reasons_json, city, at, device_hash)
reports(report_id PK, check_id FK NULL, doc_id /* text lives in the vault */, gtin, serial, city, at)
```

**`consumer-mumbai`, MongoDB:** `scans` and `reports` collections, holding the same information with different field names and nesting.

**`regulator`: State and Central Drug Control (fictional), PostgreSQL:**
```sql
alerts(alert_id PK, kind CHECK (kind IN ('recall','nsq','ban')), gtin, lot, manufacturer_org, issued_at, reason, doc_id)
licences(org_id PK, licence_no, licence_type, valid_from date, valid_to date, status CHECK (status IN ('active','suspended','cancelled')))
inspections(inspection_id PK, org_id, inspected_at, outcome, doc_id)
staff(...)
```

All company names are fictional. Do not use real company names. The old project used one; the new one must not.

---

## 6. The canonical shared model

The share API of every node returns these shapes, whatever its native storage. They follow the idea of GS1 EPCIS events, simplified. Definitions live in `services/node/asali_node/canonical.py` as Pydantic models, and the TypeScript types are generated from the OpenAPI schema.

```python
class Org:        org_id, org_type ('pharma'|'distributor'|'shop'|'consumer'|'regulator'), name, city, state,
                  issuer_code | None, gs1_prefix | None, base_url, host_name
class Product:    gtin, brand, generic, strength, form, pack_size, storage_min_c | None, storage_max_c | None, owner_org
class Batch:      gtin, lot, mfg_date, expiry_date, status ('released'|'quarantine'|'recalled'), owner_org
class Event:      event_id, org_id, event_type ('commission'|'ship'|'receive'|'sell'|'return'|'destroy'),
                  at (aware datetime), gtin, serial | None, lot | None,
                  from_org | None, to_org | None, ref | None, city
class UnitView:   gtin, serial, known (bool), lot | None, expiry | None,
                  status_here ('in_stock'|'shipped'|'sold'|'returned'|'destroyed'|'never_held'),
                  events: list[Event], served_by: ServedBy
class ServedBy:   org_id, host_name, at
class Shipment:   shipment_id, from_org, to_org, at, units: list[(gtin, serial)]
class Alert:      alert_id, kind ('recall'|'nsq'|'ban'), gtin, lot | None, manufacturer_org, issued_at, reason, doc_id | None
class Licence:    org_id, licence_no, status, valid_to
class ScanStat:   gtin, serial, total, by_city: list[{city, count, first_at, last_at}]
class DocHit:     see TEXT_ML.md section 7
```

Each adapter's mapping is written down in `schemas/<org_id>/MAPPING.md`, one row per canonical field: the native field, the conversion, and an example. This is the GAV mapping for the report.

Conversion rules every adapter must apply:
- **Dates:** always returned as ISO 8601 with a timezone (Asia/Kolkata). Kesar's `DD/MM/YYYY` and `MM/YYYY` are converted; `MM/YYYY` means the last day of that month.
- **Status codes:** mapped through an explicit table in the adapter, such as Kesar `C` → `commissioned` and Medivra `S` → `shipped`. An unknown code raises an error. Never guess.
- **Party codes:** mapped through `PARTY_MST.NET_ORG_ID`. A code with no network id is returned as `to_org = None` with `ref` set, and the trace treats it as a chain gap.

---

## 7. Read-only sharing, enforced three ways

"They give access to their database only in a read-only way" is enforced at three layers. Each layer has a test that tries to break it.

| Layer | How it is enforced | Test that must fail to write |
|---|---|---|
| HTTP | The share router registers GET routes only. Any other method returns 405. | `POST /share/v1/units/...` → 405 |
| Database account | The share router uses a separate connection: a PostgreSQL role `share_ro` with `GRANT SELECT` only; a MongoDB user with the built-in `read` role; SQLite opened as `file:...?mode=ro` with `uri=True`; a Meilisearch key with `actions: ["search"]` only. | The share-mode adapter calling its own `insert_*` raises a permission error at the database. |
| Data scope | A caller sees what it needs and nothing more. Unit queries need gtin and serial; there is no "list all sales". `GET /share/v1/shipments` returns only shipments addressed to the caller. Bulk lists are allowed only when the caller's org type is `regulator`. | A shop asking another shop's `/share/v1/shipments` gets an empty list; a list endpoint called by a non-regulator → 403 |

The portal API, which writes, accepts only the org's own logged-in staff (session cookie) and only from that node's own portal origin.

---

## 8. Directory and trust between organisations

### 8.1 Directory service (`services/directory`, runs on PC-A, port 8400)

| Endpoint | Purpose |
|---|---|
| `POST /directory/v1/register` | Body: `{org_id, org_type, name, city, state, issuer_code, gs1_prefix, base_url, public_key, host_name}`. Header `X-Join-Token` must equal the network join token from `.env`. Re-registering the same `org_id` with a different public key is refused (409) unless the request also carries the admin token. |
| `POST /directory/v1/heartbeat` | Signed by the org. Updates `last_seen`. |
| `GET /directory/v1/orgs` | Optional filters `type`, `state`. Returns every org with `online` = last seen under 90 s ago. |
| `GET /directory/v1/orgs/{org_id}` | One org. |
| `GET /directory/v1/issuers/{code}` | Two-character serial issuer code → pharma org. |
| `GET /directory/v1/prefixes/{gtin}` | Longest GS1 prefix match → pharma org. |
| `GET /directory/v1/health` | Liveness. |

A node registers at start-up, sends a heartbeat every 30 s, and caches the full org list in `/data/directory_cache.json` every time it reads it. With the directory unreachable, the node uses the cache and the portal shows "Directory unreachable, using the list from 14:02".

### 8.2 Signed requests between nodes

- On first start a node creates an Ed25519 key pair in `/data/keys/` and registers the public key.
- Every share API request carries these headers:
  - `X-Asali-Org: <caller org_id>`
  - `X-Asali-Time: <unix seconds>`
  - `X-Asali-Signature: base64(ed25519_sign(private_key, f"{METHOD}\n{PATH_WITH_QUERY}\n{TIME}\n{ORG}"))`
- The receiving node gets the caller's public key from its directory cache and checks the signature. It also checks that `|now − time| ≤ 120 s`; all four PCs must have automatic time sync on.
- On failure: 401 with a reason (`unknown_org`, `bad_signature`, `clock_skew`).
- Browsers never call another org's share API. The consumer's browser talks only to its own consumer node, and that node signs the calls onward. This avoids CORS problems and keeps keys server-side.

### 8.3 Timeouts and failure handling

- Each share call gets a 2 s connect and read timeout and one retry.
- After two consecutive failures a node is skipped for 30 s (a circuit breaker). The skip is reported in the result as "not asked: unreachable since 14:03".
- A whole verification has a 6 s budget. Side queries that miss it are reported as missing, never silently dropped.

---

## 9. Codes on the pack

### 9.1 Formats

| Field | Format | Check | Example |
|---|---|---|---|
| GTIN | 14 digits: indicator `0`, 7-digit GS1 prefix (`890` is GS1 India; ours are fictional), 5-digit item reference, check digit | GS1 mod-10 | `08901001000124` |
| Serial | 11 characters, Crockford Base32 (`0-9 A-Z` without I, L, O, U): 2-character issuer code, 8 random characters, 1 Luhn mod-32 check character | Detects every single-character error and almost every adjacent swap (`test-vectors/codes.json`) | `TPM9S346Q37` |
| Lot | Pharma-specific (section 5.1) | None, so it is checked against the pharma's records | `TP24A017`, `MV-2410-033`, `K/24/0091` |
| Expiry | GS1 AI 17, `YYMMDD`; `DD=00` means the last day of the month | Valid date | `270331` |

What is printed on a pack label:
1. A QR code holding a GS1 Digital Link: `https://id.asali.example/01/<gtin>/21/<serial>?10=<lot>&17=<yymmdd>`. `.example` is a reserved domain; the portals parse the URL, they don't fetch it.
2. A human-readable line under it, with the serial in groups of 4-4-3 in the label font:

   `GTIN 08901001000124   SN TPM9-S346-Q37   LOT TP24A017   EXP 03/2027`

The serial is unique across the whole network because the first two characters name the issuer. So a consumer who types only the 11 serial characters can still be routed to the right pharma.

### 9.2 Generating serials

`secrets.choice` over the alphabet for the 8 random characters, then the check character. The pharma's adapter enforces uniqueness (primary key). On a collision, generate again.

### 9.3 Luhn mod-32 (reference implementation, copy exactly)

```python
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

def luhn32_check_char(payload: str) -> str:
    factor, total, n = 2, 0, 32
    for ch in reversed(payload):
        addend = factor * ALPHABET.index(ch)
        factor = 1 if factor == 2 else 2
        total += addend // n + addend % n
    return ALPHABET[(n - total % n) % n]

def luhn32_is_valid(full: str) -> bool:
    factor, total, n = 1, 0, 32
    for ch in reversed(full):
        addend = factor * ALPHABET.index(ch)
        factor = 2 if factor == 1 else 1
        total += addend // n + addend % n
    return total % n == 0
```

GS1 mod-10: going from the rightmost digit of the 13-digit body, multiply alternately by 3 and 1, sum, and the check digit is `(10 − sum mod 10) mod 10`.

---

## 10. Scanning and fixing misreads

### 10.1 Where wrong characters come from

| Input | Typical errors |
|---|---|
| USB or Bluetooth "keyboard wedge" scanner (common in Indian pharmacies) | Wrong keyboard layout on the PC, Caps Lock flipping case, the GS separator (0x1D) dropped or turned into a space, characters lost when the scan comes faster than the page can take keystrokes, a trailing Enter or Tab |
| Phone camera reading the QR | Rare, because QR has its own error correction. A half-read 1D barcode or a QR containing someone else's code is possible. |
| Person typing the printed line | 0/O, 1/I/L, 5/S, 8/B, 2/Z, 6/G, swapped neighbours, a missed or doubled character, hyphens and spaces |

### 10.2 The pipeline (`packages/asali_codes`)

```
raw text ─> normalise ─> parse ─> validate ─┬─ all valid ──────────────> ACCEPTED
                                            └─ something invalid ─> generate candidates ─> filter ─> rank ─> decide
```

1. **Normalise**
   - Unicode NFKC, then trim and drop control characters except GS (0x1D).
   - Strip the scanner symbology prefixes `]Q1`, `]Q3`, `]d2`, `]C1`.
   - In the serial only: uppercase, remove spaces and hyphens, map `O→0`, `I→1`, `L→1`. These letters are not in the alphabet, so the mapping loses nothing.
   - Keep `U` and report it as an invalid character. It is not in the alphabet, and guessing what it meant would be a guess.
2. **Parse**, trying these grammars in order. The first one that matches wins.
   - GS1 Digital Link URL (any host; the path carries `/01/<gtin>/21/<serial>`; query `10` and `17`).
   - GS1 element string, with or without brackets. Fixed-length AIs `01` (14 digits) and `17` (6 digits); variable-length `10` and `21` end at GS, at the next bracket, or at the end. For a raw string without GS, try both possible ends of AI `10` and keep the reading where the following AI parses and the serial passes its check.
   - The human-readable line: regex over the labels `GTIN|SN|S/N|SERIAL|LOT|B.NO|BATCH|EXP|EXPIRY`, in any order. Reuse ideas from the old `integration/uncertainty/standardize.parse_label`.
   - A bare 11-character serial (with or without hyphens).
   - A bare 14-digit GTIN (product lookup only, no pack check).
3. **Validate** the GTIN check digit, the serial check character and expiry date validity. Each field gets one status: `valid`, `invalid_check`, `invalid_char`, `missing` or `wrong_length`.
4. **Generate candidates** only for fields that failed:
   - **Serial:** every string within cost 2.0 of the observed one under the confusion model (the old project's `integration/uncertainty/confusion.py` prior: O/0 0.25, I/1 0.25, S/5 0.3, B/8 0.3, Z/2 0.35, G/6 0.4…; adjacent swap 0.6; any other substitution 1.0; one insertion or deletion 1.0). Keep only candidates that pass Luhn mod-32 and start with a known issuer code. Generate the cheap edits first; stop at 200 candidates.
   - **GTIN:** single-digit substitutions and adjacent swaps that pass mod-10 and match a known GS1 prefix (from the directory) and a known product (from the pharma's product list, cached for 10 minutes).
5. **Filter by existence and context.** This is where most misreads get resolved:
   - **Staff scan sessions** pass an *expected set*:
     - receiving: the units the sender's share API lists for this shipment;
     - dispatching or selling: the units in the org's own stock.
     Candidates outside the expected set are dropped. The universe is small, so one candidate usually survives.
   - **Consumer checks** ask the issuer pharma, in one call, which candidates exist (`GET /share/v1/units/exists?gtin=...&serials=A,B,C`). If the lot or expiry was also read, candidates must match them.
6. **Rank** by edit cost, lowest first. The margin is the cost gap between the best candidate and the second best.
7. **Decide:**

| Situation | Decision | What the person sees |
|---|---|---|
| Everything valid | `accepted` | Nothing extra |
| One candidate, cost ≤ 1.0, margin ≥ 0.5 or no second candidate, and context is a staff session with an expected set | `corrected` | The row shows "Read as TPM0-S346-Q37, corrected to TPM9-S346-Q37" with an Undo button |
| One candidate as above, but context is a consumer check | `needs_confirmation` | "Does your pack show TPM9-S346-Q37?" with Yes / No, re-scan. No verdict until Yes. |
| 2–5 candidates | `needs_choice` | The candidates, best first, with the differing characters marked |
| No candidate, or more than 5 | `unreadable` | "We could not read this code. Scan again or type the code printed after SN." |

8. **Safety rules:**
   - A correction can only lead to a Genuine verdict after the person confirms the corrected code against the printed pack. A counterfeiter could print a near-copy of a real serial with a broken check character, hoping a "helpful" system fixes it. Confirmation, together with the copied-code checks in section 12, closes that hole.
   - Corrections are logged per org, with raw input, chosen value, cost and who confirmed, in the org's own database (`scan_corrections`). A confirmed pair can later tune the confusion costs (stretch goal S3).
9. **Same rules in the browser.** `apps/portal-web/src/lib/codes.ts` ports normalise, parse and the check characters to TypeScript. The scan box can show "check character wrong" instantly, before any network call. Both implementations run `test-vectors/codes.json` in their tests.

### 10.3 Keyboard-wedge handling in the scan box

- The scan box keeps focus during a scan session. A global key listener sends fast keystroke bursts there even when another element has focus. A burst is at least 8 characters, at most 35 ms apart, ending in Enter or Tab, or 80 ms of silence.
- Caps Lock: if the burst contains lowercase Crockford letters and no uppercase ones, uppercase it and count it as normal.
- Wrong keyboard layout: if a burst contains characters outside `[0-9A-Za-z()\-\x1d/:?=&.]`, show "The scanner may be set to a different keyboard layout" with a link to a help note. Do not silently remap.

---

## 11. What each portal does (the write paths)

Every write goes to the node's own database through its own adapter. Every check against another org is a read through that org's share API.

### 11.1 Pharma portal

| Screen | Flow |
|---|---|
| Products | List and add products: GTIN generated from the org's prefix plus the next item reference, storage range. |
| Batches | Create a batch: product, lot (generated in the org's style, editable), manufacturing and expiry dates, quantity. "Create packs" generates that many serials (status commissioned) and records commission events. |
| Labels | For a batch, a printable label sheet. A4 with 3×8 labels: QR (`qrcode` npm package, SVG) plus the human-readable line. Browser print, with a print stylesheet. |
| Dispatch | Pick a distributor from the directory (type distributor, online first). Start a scan session with the expected set = own commissioned, not-shipped units. Scan packs. Finish → one shipment record plus ship events. The distributor can now see it in `/share/v1/shipments`. |
| Recalls | Recall a batch: reason, level. Writes to own database; the share API exposes it as batch status `recalled`. Also creates an official recall notice text document in the vault (`TEXT_ML.md` section 3). |
| Documents | Add text documents (certificate of analysis, deviation report, batch release note) by pasting text or uploading `.txt`/`.md`. The pipeline classifies and links them; the screen shows what was linked and how confident the link is. |
| Activity | Own events, newest first, filterable. |

### 11.2 Distributor portal

| Screen | Flow |
|---|---|
| Receive | "Incoming": shipments addressed to this distributor, gathered from every pharma's `/share/v1/shipments` and not yet received. Pick one, scan with expected set = that shipment's units. Each scan is ok, corrected, duplicate, "not in this shipment" or unreadable. Finish → receipt with the scanned units. Missing units are listed as a discrepancy note (a text document in the vault, type `discrepancy_note`). |
| Dispatch | Pick a shop. Shops in the distributor's served states come first; served states are set per distributor. Scan, expected set = own stock. Finish → dispatch record. |
| Stock | Packs in stock, grouped by product and batch, with expiry. Near-expiry (under 90 days) highlighted. |
| Documents | Delivery notes, temperature reports (pasted logger text plus narrative), damage reports. |
| Activity | As pharma. |

### 11.3 Shop portal (location-aware)

| Screen | Flow |
|---|---|
| Receive | As distributor receive, from distributors. |
| Sell | Scan one or more packs (expected set = own stock), optional last 4 phone digits (hashed with the shop's salt before saving), "Record sale". Print a receipt in the shop's receipt language, with a small QR linking to the consumer portal for that city. |
| Returns | Scan a sold pack, choose a reason, record it. Optionally write a return note as text. |
| Stock | As distributor. |
| Alerts | Regulator alerts for the shop's state plus national ones, newest first, and any stock they affect. |
| Documents | Counter notes and customer feedback written by staff. |
| Header | Shop name, area, city and state, e.g. "Apna Chemist · Andheri, Mumbai". |

What changes with location, all from settings:
- the header;
- which alerts are shown;
- which distributors are offered for receiving;
- receipt language and the state drug-control contact on the receipt;
- the consumer portal linked from the receipt QR.

### 11.4 Consumer portal

| Screen | Flow |
|---|---|
| Check | One large input: camera scan, or type the code. Correction rules apply (section 10). Shows the verdict, then the pack's history, then documents (section 12). |
| Report a problem | Free-text box ("What is wrong with the pack or the medicine?"), city, optional purchase date and shop name. Saved as a text document in this consumer node's vault, type `consumer_complaint`, after removing phone numbers and emails (`TEXT_ML.md` section 4.1). |
| My checks | This browser's recent checks (local storage), with a link to re-open each one. |

Every check is recorded in the consumer node's own database with city and time. That is what makes `ScanStat` possible.

### 11.5 Regulator portal

| Screen | Flow |
|---|---|
| Alerts | Issue a recall, NSQ ("not of standard quality") or ban alert for a GTIN and lot. Also writes the official notice text into the regulator vault. |
| Licences | Licence status of every distributor and shop. |
| Complaints | Consumer complaints from all consumer nodes (bulk read allowed for the regulator), grouped by the batch they were linked to, with complaint clusters highlighted (`TEXT_ML.md` section 6.5). |
| Investigate | Full trace of any pack, plus a document search across the network with filters. |
| Network | Every org, its host, online state and latency. This screen is also the live proof that the system is spread over four machines. |

### 11.6 Common to all portals

- Staff log in with username and password; consumers don't log in.
- Passwords are hashed with `bcrypt`. Sessions use an HttpOnly, SameSite=Lax cookie with an 8-hour expiry.
- The header's network status shows "11 of 12 organisations reachable". A popover names the unreachable ones and their last-seen time.

---

## 12. Verification

### 12.1 Trace (the bind join)

```text
verify(raw_input, context='consumer'):
  r = codes.read(raw_input)                        # section 10
  if r.decision not in ('accepted', 'confirmed'): return NeedsInput(r)
  issuer = directory.issuer_for(r.serial[:2])      # or prefix_for(r.gtin)
  if issuer is None: return verdict(DO_NOT_USE, NOT_ISSUED_UNKNOWN_ISSUER)
  start in parallel (each with the 6 s budget):
     A  chain        = follow_chain(issuer, r.gtin, r.serial)
     B  alerts       = regulator /share/v1/alerts?gtin=&lot=      (lot known after the first hop; re-ask if needed)
     C  sells        = every shop: /share/v1/units/{gtin}/{serial}   (sell events by shops not on the chain)
     D  scans        = every consumer node: /share/v1/scans/{gtin}/{serial}
     E  licences     = regulator /share/v1/licences?org_ids=<orgs on the chain>   (after A)
     F  documents    = TEXT_ML.md section 7, using the context gathered by A–E
  apply rules (12.3) → verdict + reasons + evidence + missing_sources

follow_chain(issuer, gtin, serial):
  hop0 = issuer.units(gtin, serial)               # UnitView
  if unreachable: return Gap(issuer)              # → CANNOT_CHECK
  if not hop0.known: return NotIssued
  chain = [hop0]; holder = issuer
  while last ship event in holder's events and len(chain) < 6:
      nxt = ship.to_org
      v = nxt.units(gtin, serial)
      if unreachable: chain.append(Gap(nxt)); break
      if no receive event in v from holder: mark CHAIN_BREAK(holder → nxt)
      chain.append(v); holder = nxt
  return chain
```

Fanning out to every shop (C) and every consumer node (D) is affordable with 3 shops and 2 consumer nodes. The report should say how a national system would do it instead: shops report sales to the issuer, which then answers for them.

### 12.2 Reasons

| Code | Raised when | Strength |
|---|---|---|
| `NOT_ISSUED` | The issuer is reachable and says the serial doesn't exist, or the issuer code or GS1 prefix is unknown | do_not_use |
| `DESTROYED` | The issuer marked the unit destroyed or decommissioned | do_not_use |
| `RECALLED` | Batch status recalled at the issuer, or a regulator `recall` or `ban` alert for the GTIN and lot | do_not_use |
| `QUALITY_FAILED` | A regulator `nsq` alert for the GTIN and lot, or an official regulator text notice linked to the batch with confidence ≥ 0.9 (`TEXT_ML.md` section 8) | do_not_use |
| `EXPIRED` | Expiry before today | do_not_use |
| `COPIED_CODE` | A sell event from two different orgs, or a sell event by a shop the chain never reached | do_not_use |
| `CHAIN_BREAK` | A receive event with no matching ship from the previous holder, or the holder sold or shipped a unit it never received | caution |
| `UNLICENSED_HOLDER` | An org on the chain has a licence that is suspended, cancelled or expired on the event date | caution |
| `SCAN_SPREAD` | After the sale, consumer checks in 2 or more cities that are 300 km or more apart, within 7 days, or more than 20 checks in total | caution |
| `COLD_CHAIN` | The product's storage maximum is 8 °C or less, and a temperature report linked (confidence ≥ 0.8) to a shipment that carried this unit says it went above the maximum | caution |
| `COMPLAINT_CLUSTER` | 3 or more independent consumer complaints linked to the same batch (confidence ≥ 0.8) from 2 or more cities, with issue labels in {suspected_fake, packaging_different, no_effect} | caution |
| `TEXT_CONTRADICTION` | A linked complaint states a purchase city or shop that contradicts the structured sale record (`TEXT_ML.md` section 6.4) | caution; if `COPIED_CODE` is also raised, it is listed as supporting evidence |
| `QUALITY_NOTICE_POSSIBLE` | An official text notice linked with confidence 0.6–0.9 | caution |
| `CORRECTED_UNCONFIRMED` | Never reaches a verdict, because the flow stops for confirmation first | n/a |
| `SOURCE_MISSING` | A node needed for the chain, or for a do_not_use check, didn't answer | cannot_check |

City distances come from a small table of city coordinates in `asali_node/verify/cities.py`, covering every city we use, with the haversine formula.

### 12.3 Verdict

```
if any reason is do_not_use                       → DO NOT USE  (missing sources are listed, but don't block this)
elif the issuer, or any chain hop, is missing      → CANNOT CHECK
elif any reason is caution                         → CAUTION
else                                               → GENUINE
```

Wording, one headline per verdict, taken from the strongest reason. Examples:

| Verdict and reason | Headline and second line |
|---|---|
| GENUINE, sold | "Genuine. Made by Tarang Pharma, sold by Sharma Medicos, Delhi on 12 Nov 2026." |
| GENUINE, still in stock | "Genuine. Made by Tarang Pharma. Sharma Medicos received it on 2 Nov and has not recorded a sale yet." |
| DO NOT USE, `COPIED_CODE` | "Do not use this pack. This code was sold twice: by Sharma Medicos, Delhi and by Apna Chemist, Mumbai. At least one pack carrying it is a copy." |
| CANNOT CHECK | "We could not check this pack. Western Medilink did not answer, so we cannot see where the pack went after it left Tarang Pharma. Try again in a few minutes." |

### 12.4 How text affects the verdict (the precise rule)

- **Official text** (regulator notices, pharma recall notices) counts as evidence from the issuing organisation:
  - linked at confidence ≥ 0.9 → it can raise `QUALITY_FAILED` or `RECALLED`;
  - linked at 0.6–0.9 → only `QUALITY_NOTICE_POSSIBLE` (caution).
- **Operational text** (temperature reports, delivery and discrepancy notes) can raise `COLD_CHAIN` or `CHAIN_BREAK`, which are caution only.
- **Allegations** (consumer complaints, staff notes about customers' claims):
  - one complaint on its own changes nothing; it is shown as "Reported by a customer, not verified";
  - several can raise `COMPLAINT_CLUSTER` or `TEXT_CONTRADICTION` (caution);
  - they never raise a do_not_use reason by themselves.
- Every text-derived reason names the documents it came from, quotes the sentence, and gives the link confidence.

### 12.5 The result object (one shape for the UI and for tests)

```json
{
  "verdict": "do_not_use",
  "headline": "Do not use this pack. ...",
  "reasons": [{"code": "COPIED_CODE", "strength": "do_not_use", "text": "...", "evidence": [{"kind": "event", "org_id": "shop-mumbai", "event_id": "..."}]}],
  "pack": {"gtin": "...", "serial": "...", "lot": "...", "expiry": "...", "product": {"brand": "...", "generic": "...", "strength": "..."}},
  "read": {"raw": "...", "decision": "confirmed", "corrections": [{"field": "serial", "from": "...", "to": "...", "cost": 0.25}]},
  "history": [{"org_id": "tarang", "org_name": "Tarang Pharma", "city": "...", "events": [...], "served_by": {"host_name": "PC-B", "at": "..."}}],
  "documents": [/* DocHit, TEXT_ML.md section 7 */],
  "sources": [{"org_id": "dist-west", "status": "answered" | "unreachable" | "skipped", "ms": 84, "host_name": "PC-C"}],
  "mode": "network" | "simulation",
  "checked_at": "..."
}
```

---

## 13. Unstructured text and ML (summary)

Full design in `TEXT_ML.md`. In short:
- **Who owns which text.** Every org keeps its own text documents in its own vault:
  - pharma: certificates of analysis, recall notices, deviation reports;
  - distributors: temperature reports, delivery and discrepancy notes;
  - shops: counter notes, return notes;
  - consumers: complaints;
  - regulator: NSQ lists, recall and ban orders, inspection reports.
- **Ingest pipeline**, run when a document is added: clean, remove personal data, detect language, classify the document type (ML), extract mentions (codes, dates, temperatures, names), link the mentions to structured records (ML ranker), extract claims, index into the vault.
- **ML models**, all scikit-learn and trained on a generated corpus whose answers are known; see the table below.
- **Honest evaluation.** The models are tested on a held-out generated set and on a small set the team writes by hand. The agent must not write the hand-written set.
- **Verification.** The verify engine builds a context from the pack's history (gtin, lot, serial, shipment refs, orgs, cities, dates). It retrieves linked documents from the vaults of the orgs involved, checks their claims against the structured history, and applies section 12.4.

| Model | Method | Job |
|---|---|---|
| M1 | TF-IDF + LinearSVC | Document type |
| M2 | TF-IDF + one-vs-rest logistic regression | Complaint issue labels |
| M3 | Logistic regression | Ranks candidate links between a mention and a structured record |
| M4 | TF-IDF cosine | Finds near-duplicate complaints |
| M5 | Poisson rate test | Flags batches with unusually many complaints |

---

## 14. Frontend (summary)

Full design in `DESIGN.md`:
- one React app;
- at start-up it reads `/api/config` (org type, name, city, settings) and builds the navigation for that role;
- a work-tool layout: no landing page, no hero, no stat tiles;
- the scan box is the centre of every staff screen;
- the verdict panel is the centre of the consumer screen;
- quality gates: the Impeccable detector must report zero findings, and Impeccable's critique, audit, polish and harden passes are run at fixed milestones.

---

## 15. Backend code rules (de-slop for the server)

The old code had files over 1,000 lines, essay-length comments, silent fallbacks and invented precision. The new code follows these rules, and the review step checks every one:

1. No file over 400 lines. One responsibility per module.
2. Type hints everywhere. `mypy --strict` passes on `packages/` and `asali_node/verify/`. `ruff check` and `ruff format` pass on everything.
3. Docstrings are 1–3 lines, say what and why, and don't narrate the code. No banner comments, no ASCII art, no "This module is a robust, comprehensive…".
4. No bare `except`. Network errors become a typed `SourceUnavailable(org_id, reason)` and end up in `sources`. Nothing is swallowed.
5. No silent fallbacks: if a value is missing, the result says it is missing. No default verdicts, no made-up numbers, no 0–100 scores.
6. Errors over HTTP use problem JSON (RFC 9457): `type`, `title`, `status`, `detail`, plus a `code`. The `detail` is a sentence a person can act on.
7. Config only through `pydantic-settings`, read from the environment. No IP address, password or token appears in code or in committed files. `infra/network.yaml` holds names and roles; `.env` files hold secrets and are git-ignored; `.env.example` files are committed.
8. Logs: one JSON line per request, with `request_id`, `org_id`, route, status and ms. Share calls log the callee and the outcome.
9. No speculative abstractions: no plugin registries, factories or base classes with one implementation. Adapters share a `Protocol` and a contract test suite; that is enough.
10. Every rule in section 12 has a table-driven test. Every adapter passes the same contract tests.
11. Before closing a milestone, run Claude Code's `/simplify` and `/code-review` on the milestone's diff and fix what they find (`TASKS.md`).

---

## 16. Deployment and orchestration

### 16.1 One description of the network

`infra/network.yaml` (committed, no secrets) holds:
- every PC: name and role;
- every org: id, type, name, city, state, engine, port, which PC hosts it;
- issuer codes and GS1 prefixes;
- distributor served states;
- shop settings.

It never holds IP addresses.

### 16.2 Generating each PC's stack

`python infra/scripts/make_stack.py --pc PC-C --ip 192.168.1.23 --directory-url https://192.168.1.11:8400` writes:
- `infra/out/PC-C/compose.yml`: the services for that PC's orgs only, with memory limits;
- `infra/out/PC-C/Caddyfile`: one TLS site per org port, reverse-proxying to that org's app container;
- `infra/out/PC-C/.env`: join token, database passwords (random, generated once and kept), directory URL, public host IP.

`infra/out/` is git-ignored.

### 16.3 Per-org services in a stack

| Service | Image | Notes |
|---|---|---|
| `<org>-app` | `asali-node`, built locally from `services/node/Dockerfile` | The portal's static files are built into the image; `ORG_ID`, `ORG_TYPE` and the rest come from the env file |
| `<org>-db` | `postgres:16-alpine` or `mongo:7` | Not for SQLite orgs. Never published to the LAN. Postgres `shared_buffers=64MB`; Mongo `--wiredTigerCacheSizeGB 0.25`. An init script creates the read-write and read-only accounts. |
| `<org>-vault` | `getmeili/meilisearch:v1.x` (pin the newest v1 tag on Docker Hub at build time; write the exact tag into the compose template) | `MEILI_MASTER_KEY` from env. At start-up the app creates an admin key scoped to its own index and a search-only key for the share API. `--max-indexing-memory=256Mb`. |
| `caddy` | `caddy:2-alpine` | One per PC. Mounts the Caddyfile and the PC's mkcert certificate. |
| `directory` | `asali-directory` | PC-A only |

### 16.4 Network set-up for the four PCs (runbook `docs/runbook/FOUR_PCS.md`)

1. **Network.**
   - All four PCs join one Wi-Fi network that allows device-to-device traffic: a phone hotspot or a home router. Campus Wi-Fi often blocks it ("client isolation").
   - Test with `python infra/scripts/check_lan.py --peers <ip1> <ip2> <ip3>` before anything else.
   - If campus Wi-Fi is the only option, install Tailscale on all four, use their `100.x` addresses, and rerun the check.
2. **Time.** Automatic time sync on (Windows: Settings → Time → Sync now; macOS: on by default). Signatures fail beyond 120 s of skew.
3. **Docker.**
   - Windows PCs: Docker Desktop with WSL2 (`wsl --install --no-distribution` as administrator, then restart), and `%UserProfile%\.wslconfig` with `memory=4GB` on the 8 GB PCs, `memory=8GB` on PC-A.
   - Mac: Docker Desktop for Apple silicon.
4. **Firewall.**
   - Windows: an inbound rule for TCP 8101–8403 on the Private profile:
     ```powershell
     New-NetFirewallRule -DisplayName "Asali" -Direction Inbound -Protocol TCP -LocalPort 8101-8403 -Action Allow -Profile Private
     ```
     Set the Wi-Fi network to Private.
   - Mac: allow Docker in System Settings → Network → Firewall.
5. **Certificates.**
   - One person runs `mkcert -install` and copies the CA (`rootCA.pem`, `rootCA-key.pem`) to the other three PCs. The key is shared only on the team's own machines and never committed.
   - On each PC, run `make_cert.py --ip <this PC's IP>` (which calls mkcert), then `mkcert -install`.
   - Phones used for camera scanning install `rootCA.pem` as a trusted certificate. Android: Settings → Security → Install certificate → CA certificate. iPhone: install the profile, then enable full trust in Settings → General → About → Certificate Trust Settings.
   - App containers mount `rootCA.pem` and set `SSL_CERT_FILE`, so node-to-node HTTPS verifies too.
6. **Start order:** PC-A (directory) first, then the others in any order: `docker compose -f infra/out/<PC>/compose.yml --env-file infra/out/<PC>/.env up -d --build`.
7. **Seed:** from any PC, run `python seed/seed_network.py --directory-url ...`. It writes through each org's own portal API, using staff accounts from the env files.
8. **Prove distribution:** `python infra/scripts/collect_evidence.py` saves the following into `docs/evidence/four_pcs/<timestamp>/`:
   - the directory listing with host names;
   - each PC's `docker ps` output;
   - latency between every pair of PCs;
   - three scenario verifications, where `history[].served_by.host_name` shows at least three different PCs.

   Only evidence produced this way may be called a multi-machine run.

### 16.5 Resource limits (set in the generated compose)

| Service | Memory limit |
|---|---|
| app | 384 MB |
| postgres | 256 MB |
| mongo | 512 MB |
| meilisearch | 256 MB |
| caddy | 64 MB |
| directory | 128 MB |

### 16.6 Simulation mode

- `python infra/scripts/make_stack.py --simulation` writes `infra/out/SIM/compose.yml`, with all 12 orgs plus the directory on one PC.
- Every app gets `ASALI_MODE=simulation`. The portal header shows a grey band, "Simulation: all organisations are running on this computer", and results carry `"mode": "simulation"`.
- Use it for development and CI. It is never used as evidence of distribution.

---

## 17. Testing and evidence

| Level | Tool | What |
|---|---|---|
| Codes | pytest + hypothesis; vitest | `codes.json` vectors in both languages. Properties: every single substitution is detected; every single confusable substitution is recovered when the expected set holds the true code and no other candidate within cost 1.0. |
| Adapters | pytest, against real engines from `infra/compose/test-engines.yml` (Postgres, Mongo) plus SQLite | One contract suite run against all 12 adapters: write, then read back canonical; dates and status mapping; read-only account refuses writes. |
| APIs | pytest + FastAPI TestClient | Per role: auth, validation errors as problem JSON, share API GET-only and scope rules, signature checks (unknown org, bad signature, skew). |
| Rules | pytest, table-driven | Each reason in section 12.2 raised and not raised; verdict precedence; missing-source behaviour. |
| Text ML | pytest + `ml/evaluate.py` | Extractor unit tests; metrics on the held-out generated set and the hand-written set, with thresholds in `TEXT_ML.md` section 9. Results are written to `docs/evidence/ml/`. |
| Network | pytest against the simulation stack | Seeded scenarios S1–S8 (below) give the expected verdict and reasons. Stopping a node gives CANNOT CHECK or a listed missing source. |
| UI | Playwright against the simulation stack | Dispatch → receive → sell → consumer check, typed and wedge-burst input, correction confirmation, offline node notice. Screenshots go to `docs/evidence/ui/`. Impeccable `detect` reports zero findings on the built app. |
| Four PCs | `collect_evidence.py` | Section 16.4 step 8 |

Seeded scenarios (`seed/scenarios.py`), each with its expected result written in `seed/expected.json`:

| # | Scenario | Expected |
|---|---|---|
| S1 | Normal pack, made → north → shop-delhi → sold | GENUINE |
| S2 | Pack whose serial was never issued (valid check character, unknown at issuer) | DO NOT USE, `NOT_ISSUED` |
| S3 | The same serial sold by shop-delhi and shop-mumbai | DO NOT USE, `COPIED_CODE`; the Mumbai consumer complaint adds `TEXT_CONTRADICTION` as support |
| S4 | Batch recalled by medivra | DO NOT USE, `RECALLED`, with the recall notice document attached |
| S5 | NSQ notice from the regulator, as text only (no structured alert), naming kesar's batch | DO NOT USE, `QUALITY_FAILED`, from text with link confidence ≥ 0.9 |
| S6 | Cold-chain product whose shipment had a temperature excursion report | CAUTION, `COLD_CHAIN` |
| S7 | Shop-bengaluru sells a pack it never received (diversion) | CAUTION, `CHAIN_BREAK` |
| S8 | S1's pack with dist-west stopped mid-check | CANNOT CHECK, if dist-west is on the chain; otherwise GENUINE with dist-west listed as not asked |
| S9 | Typed code with O for 0 and a swapped pair | `needs_confirmation`, then the S1 result after Yes |

---

## 18. Milestones

| M | Name | Outcome you can see |
|---|---|---|
| M0 | Set-up | Branch, folders, tools, skills installed, `/impeccable init` done, empty apps start |
| M1 | Codes | `asali_codes` plus the TS port pass the vectors and properties |
| M2 | Directory and node skeleton | Two simulated nodes register, sign and verify each other's requests |
| M3 | Storage | 12 native schemas and adapters pass the contract suite, and the read-only accounts refuse writes |
| M4 | APIs | Portal and share APIs for all roles, with tests |
| M5 | Seed | The simulation network is seeded through the portal APIs; scenarios S1–S9 are in place |
| M6 | Verification (structured) | S1–S4 and S7–S9 give the expected results |
| M7 | Text and ML | Corpus, vaults, pipeline, models, evaluation report, S5 and S6 |
| M8 | UI foundation | Tokens, fonts, shell, scan box, verdict panel, network status |
| M9 | UI screens | All five portal types end to end in Playwright |
| M10 | De-slop and polish | Detector at zero; critique, audit, polish and harden done; copy pass done |
| M11 | Four PCs | Generated stacks running on the four PCs; evidence collected |
| M12 | Report | Architecture and ML report, demo script, vibe-coding record |

`TASKS.md` breaks each milestone into tasks.

---

## 19. What we take from the old project

| Old file | What we keep | How |
|---|---|---|
| `integration/uncertainty/confusion.py` | The weighted string-distance idea and the shape-confusion prior table | Rewritten into `asali_codes/confusion.py` for the Crockford alphabet (fewer confusions, because I, L, O and U are gone); under 150 lines |
| `integration/uncertainty/standardize.py` (`parse_label`, `parse_datetime`, `_MONTHS`) | Label-line parsing and the flexible date parser | Ideas only; new code with tests |
| `integration/federation/doc_store.py`, `retrieval.py` | Entity-first scoring and the verified-versus-reported labels | Reapplied in `TEXT_ML.md`; Meilisearch replaces the hand-made BM25 index |
| `integration/federation/score_context.py`, `context_aggregator.py` | Building a weighted context from linked records to steer text search | Simplified: in this system, the context comes from the custody chain |
| `integration/hard_veto_engine.py`, `trust_engine.py` | The list of checks (not issued, recalled, cloned, cold chain) | Re-expressed as section 12.2 reasons; no numeric score |
| `data/generate_documents.py` | Document templates and ground-truth style | Rewritten for the new document types and orgs |
| Phase 3 lessons | One-edit near misses never auto-verified; verdict withheld when a source is missing | Sections 10.2 step 8 and 12.3 |

Nothing else is copied. The old dashboard, coordinator and databases aren't reused.

---

## 20. Risks and what we do about them

| Risk | What we do |
|---|---|
| Campus Wi-Fi blocks traffic between PCs | Check on day one with `check_lan.py`; hotspot or Tailscale |
| WSL2 or Docker can't be installed on a Windows PC (no admin rights) | Find out in M0. Fallback: that PC's orgs run in the 16 GB PC's simulation stack, and the evidence says so. |
| Camera blocked over HTTP on phones | HTTPS everywhere (D9). The typed and USB-scanner paths always work. |
| 8 GB PCs run out of memory | Memory limits (16.5); Mongo cache cap; one Postgres and one Mongo per PC at most |
| ML looks perfect because test text comes from the same templates | Split by template family; the hand-written set written by the team; both reported (`TEXT_ML.md` section 9) |
| Correction turns a fake code into a real one | Confirmation step; copied-code and scan-spread checks; `needs_confirmation` never shows Genuine |
| The agent fakes results | `AGENT_PROMPT.md` rules: every claim needs a command output; evidence only from scripts; missing work listed as missing |
| Clock skew breaks signatures | Time sync in the runbook; the error message names the skew |

---

## 21. Definition of done

The whole system is done when all of these are true and each has evidence in `docs/evidence/`:

1. 12 orgs run across the 4 PCs. The directory and the evidence script show at least 3 different host names in one verification's `served_by` list.
2. Every write in sections 11.1–11.5 works from its portal and lands only in that org's own database. Tests prove the share accounts can't write.
3. S1–S9 give their expected results on the four-PC network, not only in simulation.
4. The text pipeline is live: adding a temperature report or a regulator notice in a portal changes the next verification of an affected pack, as section 12.4 says.
5. ML evaluation is reported on both test sets. The numbers are what the script printed.
6. The Impeccable detector reports zero findings on the built portal. Critique, audit, polish and harden have been run, and their reports are saved.
7. All tests pass: pytest, vitest, Playwright.
8. The vibe-coding record holds the prompts, the code as first generated, and every later change.
9. Whatever is still incomplete is listed at the top of the final report.
