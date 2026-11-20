# Asali Network: report

Built 20 Nov 2026 from the files in `docs/evidence/`.

## Not done or partly done

- **The four-computer run has not been done.** Everything ran as one-computer simulation (local processes on real PostgreSQL, MongoDB and SQLite). There is no evidence folder from a multi-computer run.
- **Docker was never run.** The development PC has no WSL2. The generated compose files are tested as data (`infra/tests/test_make_stack.py`) and have not been started.
- **The text vault is SQLite full-text search, not Meilisearch.** Meilisearch's binary is blocked by Windows Smart App Control on the development PC.
- **The hand-written ML test set has not been provided** by the team. The ML report says so in its first line.
- **Superpowers and Humanizer plugins were not installed** (they need the user's `/plugin` commands). Impeccable's detector was run and is at zero findings; its critique, audit and polish commands were not run as skills, and no humanizer pass was made on the prose.
- **Not written:** generated API types (task 4.8; the types are written by hand), the dark-mode switch (the portal follows the system setting), a "More" menu on the phone bottom bar, and addressing other computers from the seed scripts.
- **Hindi, Marathi and Kannada receipt text is unreviewed** and marked so in the files and on screen.
- **ML target missed:** m2_micro_f1 is 0.643 against a target of 0.8 on the generated test families. Thresholds were not tuned on test data.

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

## Automated checks

Run 2026-11-20T09:50:56.

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

Run 2026-11-20T09:46:38.

| Scenario | Verdict | Reasons | Expected | Computers named | Result |
|---|---|---|---|---|---|
| S1 | genuine | none | genuine  | SIM-LOCAL | pass |
| S2 | do_not_use | NOT_ISSUED | do_not_use NOT_ISSUED | SIM-LOCAL | pass |
| S3 | do_not_use | COPIED_CODE, CHAIN_BREAK, TEXT_CONTRADICTION | do_not_use COPIED_CODE, CHAIN_BREAK, TEXT_CONTRADICTION | SIM-LOCAL | pass |
| S4 | do_not_use | RECALLED | do_not_use RECALLED | SIM-LOCAL | pass |
| S5 | do_not_use | QUALITY_FAILED | do_not_use QUALITY_FAILED | SIM-LOCAL | pass |
| S6 | caution | COLD_CHAIN | caution COLD_CHAIN | SIM-LOCAL | pass |
| S7 | caution | CHAIN_BREAK | caution CHAIN_BREAK | SIM-LOCAL | pass |
| S9 | needs_confirmation | | needs_confirmation | | pass |

Scenario S8 (a stopped organisation) is run by `tests/network/test_scenarios.py` because it stops and starts a node.

## Text and ML

Measured on template families the models never saw (`docs/evidence/ml/report.md` has the confusion matrices, the reliability chart and the baseline comparison).

| Metric | Result | Target |
|---|---|---|
| m1_macro_f1 | 0.942 | at least 0.9 |
| m2_micro_f1 | 0.643 | at least 0.8 |
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

6 passed, 0 failed. Screenshots in `docs/evidence/ui/e2e/`.

## Deviations from the plan

Every deviation, with its reason, is in `docs/vibe/CHANGES.md`.
