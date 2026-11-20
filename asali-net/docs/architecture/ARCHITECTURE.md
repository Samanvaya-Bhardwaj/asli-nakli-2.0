# Architecture

Asali Network checks whether a medicine pack is genuine by asking the organisations that handled it. No organisation hands its data to a
central store. Each one keeps its own database, in its own structure, and lets the others read a small, controlled part of it.

## The four computers

```mermaid
flowchart LR
  subgraph A["PC-A: people"]
    DIR[directory]
    REG[regulator<br/>PostgreSQL]
    CD[consumer-delhi<br/>SQLite]
    CM[consumer-mumbai<br/>MongoDB]
  end
  subgraph B["PC-B: pharma"]
    TA[tarang<br/>PostgreSQL]
    ME[medivra<br/>MongoDB]
    KE[kesar<br/>SQLite]
  end
  subgraph C["PC-C: distributors"]
    DN[dist-north<br/>PostgreSQL]
    DW[dist-west<br/>MongoDB]
    DS[dist-south<br/>SQLite]
  end
  subgraph D["PC-D: shops"]
    SD[shop-delhi<br/>SQLite]
    SM[shop-mumbai<br/>PostgreSQL]
    SB[shop-bengaluru<br/>MongoDB]
  end
  A <-->|HTTPS, signed requests| B
  A <-->|HTTPS, signed requests| C
  A <-->|HTTPS, signed requests| D
  B <--> C
  C <--> D
```

Twelve organisations, three storage engines, one directory. The directory holds only addresses, public keys and issuer codes. It holds no
medicine data. Nodes cache it on disk and keep working if it goes down.

## Inside one node

```mermaid
flowchart TB
  browser -->|HTTPS| caddy
  caddy --> app
  subgraph app["FastAPI app (same image for every organisation)"]
    portal["/api: staff sign-in, writes<br/>(read-write database account)"]
    share["/share/v1: GET only, signed callers<br/>(read-only database account)"]
    verify["verify engine: trace, rules, text evidence"]
    text["text pipeline: ingest, classify, link, index"]
  end
  portal --> db[(own database)]
  share --> db
  text --> vault[(own text vault)]
  share --> vault
  verify -->|signed GET| others[other nodes' share APIs]
```

Read-only sharing is enforced three ways, and each has a test that tries to break it (`services/node/tests/stores/test_readonly.py`,
`tests/api/test_share_api.py`):

1. **HTTP:** the share router registers GET routes only; `POST`, `PUT`, `PATCH` and `DELETE` return 405.
2. **Database account:** the share API uses a separate connection: a PostgreSQL role with `SELECT` only, a MongoDB user with the `read` role,
   SQLite opened with `mode=ro`, the text vault opened with `mode=ro`. A write fails inside the database.
3. **Scope:** a caller sees what it needs. There is no "list all sales". A shipment list shows only shipments addressed to the caller.
   Bulk complaint lists are for the regulator only.

## How a verification works

```mermaid
sequenceDiagram
  participant C as Consumer node
  participant K as Maker (kesar)
  participant D as Distributor
  participant S as Shop
  participant R as Regulator
  C->>K: unit(gtin, serial)
  K-->>C: made, shipped to D
  par side queries
    C->>R: alerts, licences
    C->>S: unit (every shop)
    C->>C: scan counts (every consumer node)
  end
  C->>D: unit(gtin, serial)  (asked because K says it went there)
  D-->>C: received, shipped to S
  C->>S: unit(gtin, serial)
  S-->>C: received, sold
  C->>C: rules, then documents about the pack
  C-->>C: verdict + reasons + history (each hop names the computer that answered)
```

The chain is a dependent ("bind") join: each hop's question needs the previous hop's answer. The side queries do not, so they run beside
the chain. Every call has a 2 s timeout, one retry, a breaker that skips an organisation after two failures, and a 6 s budget for the
whole check. An organisation that did not answer is named in the result.

Rules (`services/node/asali_node/verify/rules.py`) are table-driven and have no network or clock inside them. The verdict is the strongest
reason: any do-not-use reason wins; otherwise a missing source gives "cannot check"; otherwise any caution gives "caution"; otherwise genuine.
No score exists anywhere.

## The text pipeline

```mermaid
flowchart LR
  text --> clean[clean + redact]
  clean --> type[M1 document type]
  type --> mentions[mentions: codes, names, dates, temperatures]
  mentions --> link[M3 link ranker]
  link --> claims[claims]
  claims --> issue[M2 issue labels]
  issue --> vault[(vault + links in the org's database)]
```

Text can change a verdict only under fixed rules (`PLAN.md` 12.4): an official notice linked with confidence 0.9 or more can raise
a do-not-use reason; a lower link only a caution; a temperature report only a caution; a single complaint nothing at all.

## Where each course idea lives

| Idea | Where |
|---|---|
| Sources | 12 organisation databases and their text vaults (`services/node/asali_node/stores/`, `vault/`) |
| Wrappers | One store per organisation: `stores/<org>.py` over its own schema in `schemas/<org-id>/` |
| Global-as-view mapping | `schemas/<org-id>/MAPPING.md`: one row per canonical field |
| Canonical model | `services/node/asali_node/canonical.py` |
| Mediator and query plan | `verify/trace.py` (bind join along the custody chain), `verify/engine.py` |
| Entity resolution | Code correction (`packages/asali_codes`) and text-to-record linking (`packages/asali_text/link.py`) |
| Provenance | Every fact in a result carries the organisation and the computer that said it (`served_by`) |
| Heterogeneity | Different structures, date formats, status codes and party codes, mapped in each store |
| Unstructured data and ML | `packages/asali_text`: models M1 to M5, evaluated in `docs/evidence/ml/report.md` |

## Honest limits

- The text vault is SQLite full-text search, not Meilisearch. Meilisearch could not run on the development PC.
- Nothing has run on four computers yet. The simulation runs all organisations as processes on one computer.
- Docker and the generated compose files have not been run on this PC (no WSL2).
- The issue-label model misses its target on unseen phrasings; the hand-written test set has not been provided.
