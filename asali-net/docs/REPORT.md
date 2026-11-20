# Asali Network: report

Built 20 Nov 2026 from the files in `docs/evidence/`.

## Not done or partly done

- **The four-computer run has not been done.** Everything ran as one-computer simulation (local processes on real PostgreSQL, MongoDB and SQLite). There is no evidence folder from a multi-computer run.
- **Docker was never run.** The development PC has no WSL2. The generated compose files are tested as data (`infra/tests/test_make_stack.py`) and have not been started.
- **The text vault is SQLite full-text search, not Meilisearch.** Meilisearch's binary is blocked by Windows Smart App Control on the development PC.
- **The hand-written ML test set has not been provided** by the team. The ML report says so in its first line.
- **Superpowers and Humanizer plugins were not installed** (they need the user's `/plugin` commands), so no humanizer pass was made on the prose. Impeccable's detector is at zero findings; its audit and critique were done as a pass by Claude, not by a second person (`docs/evidence/ui/impeccable-review.md`).
- **The seed and scenario scripts address nodes through the directory** (`--directory-url`, `--ca`), but have only been run against the local directory, never against four computers.
- **The Phase 1 to 3 code at the repository root is not connected to this system.** It still runs on its own (`scripts/run_federation.py`) and was not changed. This network re-implements what the three phases asked for: Phase 3's context discovery was ported into the nodes (`asali_node/context/`); Phase 1's integration is the per-organisation mapping to a canonical model; Phase 2's matching is `packages/asali_codes`. Phase 2's probabilistic entity-matching posterior, Phase 1's hash-chained audit log and Phase 2's replication were not carried over.
- **Phase 3 "databases on different machines" is only simulated:** each database and its node ran as its own process on one computer. The context discovery has never run across machines.
- **Hindi, Marathi and Kannada receipt text is unreviewed** and marked so in the files and on screen.
- **ML target missed:** m2_micro_f1 is 0.653 against a target of 0.8 on the generated test families. Thresholds were not tuned on test data.

## What the professor asked for, and where it is

| Request | Where it is shown |
|---|---|
| Each company, distributor and shop has its own database with a different structure | 12 stores in `services/node/asali_node/stores/`, schemas and mappings in `schemas/<org>/`; three engines; contract tests in `services/node/tests/stores/` |
| Databases are shared read-only | Three layers (HTTP, database account, scope); `test_readonly.py` shows PostgreSQL, MongoDB and SQLite refusing writes |
| Portals for pharma, distributor, shop, consumer and regulator from one UI | `apps/portal-web/`, one codebase, routes built from `/api/config` |
| Distributor scans packs in and records where they go; shops scan in and sell | Scan sessions (`scan_sessions.py`, `portal/scan.py`), browser flow in `apps/portal-web/e2e/custody.spec.ts` |
| Fix wrongly scanned characters | `packages/asali_codes` (Python and TypeScript), staff auto-correct against the expected set, consumers always confirm |
| Unstructured data is text, with ML, linked to structured data to verify | `packages/asali_text`, vaults, `verify/documents.py`; scenarios S3, S5 and S6 use it |
| Real orchestration across computers | `infra/network.yaml`, `make_stack.py`, runbook `docs/runbook/FOUR_PCS.md`; **run only as a one-computer simulation so far** |
| The old UI looked machine-made | Tokens, banned patterns, `check_copy.mjs`, Impeccable detector at zero; see `docs/plan/DESIGN.md` |

## The three phases' rubrics

One project in three phases. Each line is a marking item, what answers it, and where.

### Phase 1

| Rubric item | Marks | Where |
|---|---|---|
| Scope of work | 1 | `docs/plan/PLAN.md` section 1 |
| What is new | 1 | Per-organisation databases in three engines with different schemas; read-only sharing; text linked by ML to structured records; misread-code correction (`docs/vibe/CHANGES.md`) |
| Database schema design | 2 | `schemas/<org>/schema.sql` and `validators.json`, each with a `MAPPING.md` |
| Populating the tables | 2 | `seed/seed_network.py` through the portals' own APIs; `seed/catalogue.yaml` |
| Schema matching / mapping, or APIs for fetching | 2 | Each store maps its native schema to the canonical model (`MAPPING.md`); the share API (`services/node/asali_node/share/`) is the fetching API |
| Query decomposition and federation, or querying through APIs | 2 | `verify/trace.py`: a dependent join along the custody chain, side queries in parallel |
| Communication between the sources | 2 | Signed HTTP between nodes, a directory of addresses and keys (`network/`, `auth/`); `tests/network/` |
| Result integration and a simple GUI | 3 | Result page of the portal: verdict, reasons, history, documents, context (`apps/portal-web/`) |

### Phase 2

| Rubric item | Marks | Where |
|---|---|---|
| Approximate matching of a noisy code, and the reverse; why this algorithm | 5 | `packages/asali_codes` (weighted edit search, check character, issued set); `POST /api/similar` and the Investigate page; `docs/evidence/matching/report.md`: top 1 91.2% (plain edit distance) to 100.0% (weighted, check character, lot); decides alone 52.5% to 86.7%; wrong and decided alone 0.0% |
| Cleansing recorded data with the other information on the label, so no anomalies remain | 5 | Label lot and expiry separate candidates (`asali_codes/read.py`); `/api/quality` audit, proposals and applied fixes with a trail; `docs/evidence/quality/report.md`: 15 planted, 15 found, 15 right proposals, 15 applied |
| Prompt, generated code, and the changes | 5 | `docs/vibe/PROMPTS.md`, `docs/vibe/generated/`, `docs/vibe/CHANGES.md`, `docs/scripts/vibe_diffs.py` |

### Phase 3

| Rubric item | Marks | Where |
|---|---|---|
| Each database has four to five related tables, some joined by foreign keys | 2 | `services/node/tests/stores/test_phase3_shape.py` checks all twelve; `MAPPING.md` lists the related tables of each |
| Context found through the keys, in each database on its own machine, accumulated and related to the query | 3 | `asali_node/context/` (per database), `share/context.py`, `verify/context.py` (merge); `docs/evidence/context/report.md`: 30 packs, 3.13 organisations found context per pack, 9.13 joins followed per pack over mongo, postgres, sqlite; documents naming the pack's product: 0.732 by context, 0.2 by the question's words alone. **Each database ran as its own process on one computer; not on different machines** |
| The context searches the unstructured data, and the two are integrated | 3 | `verify/context.py` `context_documents`; the result page shows linked documents, context, and related documents apart; related documents never change a verdict |
| Prompt, generated code, modified code | 2 | As Phase 2 |

## Automated checks

Run 2026-11-20T12:54:05.

| Check | Result |
|---|---|
| pytest (all, network tests skipped) | passed |
| pytest scenarios against the running simulation | passed |
| ruff check | passed |
| ruff format check | passed |
| mypy (strict, asali_codes) | passed |
| vitest | passed |
| eslint | passed |
| typescript build | passed |
| contrast of every token pair | passed |
| copy check (banned words, dashes, emoji) | passed |
| Impeccable detector on the portal source | passed |
| file sizes (400 lines) | passed |

## Scenarios (simulation on one computer)

Run 2026-11-20T12:44:16.

| Scenario | Verdict | Reasons | Expected | Computers named | Result |
|---|---|---|---|---|---|
| S1 | genuine | none | genuine  | SIM-LOCAL | pass |
| S2 | do_not_use | NOT_ISSUED | do_not_use NOT_ISSUED | SIM-LOCAL | pass |
| S3 | do_not_use | COPIED_CODE, CHAIN_BREAK, TEXT_CONTRADICTION | do_not_use COPIED_CODE, CHAIN_BREAK, TEXT_CONTRADICTION | SIM-LOCAL | pass |
| S4 | do_not_use | RECALLED | do_not_use RECALLED | SIM-LOCAL | pass |
| S5 | do_not_use | QUALITY_FAILED | do_not_use QUALITY_FAILED | SIM-LOCAL | pass |
| S6 | caution | COLD_CHAIN | caution COLD_CHAIN | SIM-LOCAL | pass |
| S7 | caution | CHAIN_BREAK, COLD_CHAIN | caution CHAIN_BREAK | SIM-LOCAL | pass |
| S9 | needs_confirmation | | needs_confirmation | | pass |

Scenario S8 (a stopped organisation) is run by `tests/network/test_scenarios.py` because it stops and starts a node.

## Text and ML

Measured on template families the models never saw (`docs/evidence/ml/report.md` has the confusion matrices, the reliability chart and the baseline comparison).

| Metric | Result | Target |
|---|---|---|
| m1_macro_f1 | 0.942 | at least 0.9 |
| m2_micro_f1 | 0.653 | at least 0.8 |
| codes_precision | 1.000 | at least 0.98 |
| codes_recall | 1.000 | at least 0.95 |
| names_precision | 0.983 | at least 0.9 |
| names_recall | 1.000 | at least 0.85 |
| m3_precision | 1.000 | at least 0.95 |
| m3_recall | 0.906 | at least 0.85 |
| m4_f1 | 0.889 | at least 0.85 |
| retrieval_recall_at_10 | 0.986 | at least 0.9 |
| retrieval_unrelated_max | 0.000 | at most 1.0 |

## Browser tests

15 passed, 0 failed. Screenshots in `docs/evidence/ui/e2e/`.

## Deviations from the plan

Every deviation, with its reason, is in `docs/vibe/CHANGES.md`.
