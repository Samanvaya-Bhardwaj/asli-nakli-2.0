# Changes after first run

A code file is saved to `generated/<milestone>/` before it first runs (`snapshot.py`). Every change made afterwards, because of something seen when running it, is listed here. Changes that only follow the plan's next task aren't listed; `DIFFS.md` (Task 12.4) shows those.

Format: `| # | Milestone | File | What was observed | What changed |`

| # | M | File | Observed | Changed |
|---|---|---|---|---|
| 1 | M0 | `pyproject.toml` (pytest config) | The first run of `pytest docs/vibe` collected 8 tests instead of 4: the snapshot copy of `test_snapshot.py` under `generated/` was collected too | Added `--ignore=docs/vibe/generated` to pytest options and excluded the folder from ruff |
| 3 | M1 | `apps/portal-web/src/lib/codes.ts` (`labelLine`) | 2 of 35 Vitest cases failed: label lines lost their first field (the lot). `LABEL.test()` in `parse` left `lastIndex` after the first match, and `matchAll` copies `lastIndex` from the regex it is given | Reset `LABEL.lastIndex = 0` before `matchAll` |
| 4 | M2 | `services/directory/tests/test_directory.py` | 1 of 16 failed with a TypeError in the test: the bad-`org_id` case passed `org_id` twice to the helper | The test now updates the body dict instead. The service code was unchanged. |
| 2 | M1 | `asali_codes/parse.py` (`_bare`) | `parse("hello world")` returned `bare_serial`: any 10–12 letters counted as a serial, because L and O are read as digits | A bare serial must be exactly 11 characters, or 10–12 characters including at least one digit |

## Deviations from the plan

| # | Plan said | Done instead | Why |
|---|---|---|---|
| D1 | Task 0.4: add ignore rules to the repository's root `.gitignore` | Put them in `asali-net/.gitignore` | Same effect, and keeps everything inside `asali-net/` (Global Constraint 1) |
| D2 | Task 0.1: work on a new branch `v2-network`, commit per task | Nothing switched or committed yet | The Phase 3 work on branch `phase3` is still uncommitted, and the user has not asked for commits. Waiting for the user. |
| D7 | Task 2.6: verify with `docker compose -f infra/compose/dev-two-nodes.yml up` | Dockerfiles and the compose file are written but not built or run (Docker needs WSL2 on this PC). The same check ran with `infra/scripts/run_local_two_nodes.py`: the directory and two nodes as local processes, plain HTTP, simulation mode. Both nodes registered, and each fetched the other's `/share/v1/org` over a signed request: `SMOKE OK`. | Proves the node code. It is not evidence of a container or multi-machine run. Re-run the compose version once WSL2 is installed. |
| D8 | Task 2.6 smoke needs `/share/v1/org` (planned for Task 4.2) | Added now, in `share/common.py`, together with the start-up wiring (`runtime.py`) and refresh-on-unknown-org in the guard and the client | Without them two nodes cannot find or call each other. A node that registered after the last refresh is found within 5 s instead of 30 s. |
| D3 | M1 interface: `FieldStatus` has 5 values | Added a sixth, `invalid_value` | Needed for an expiry that is present but isn't a real date. None of the five fit. |
| D4 | `PLAN.md` 10.2 step 5: for consumer checks, candidates must match a lot or expiry that was also read | Not done inside `read()`. `ExistsFn` only says which serials exist, not their lots. | Belongs in the consumer check endpoint (Task 6.5), which can ask the issuer for each candidate's lot. Noted there. |
| D5 | Plan gap: a consumer may type only the 11-character serial, with no GTIN | Not yet handled. The share API in Task 4.2 looks units up by GTIN and serial. | Task 4.2 needs a pharma-only `GET /share/v1/units/by-serial/{serial}`. Serials are unique across the network, so this is safe. To add in M4. |
| D6 | Task 10.4: `npm run lint` passes | **Blocked on PC-D.** Windows Smart App Control blocks oxlint's unsigned native binary: "An Application Control policy has blocked this file". | **Resolved (19 Nov 2026, the user chose ESLint):**<br>- oxlint removed; ESLint 10 added with typescript-eslint, react-hooks and react-refresh (`eslint.config.js`).<br>- typescript-eslint supports TypeScript < 6.1, so TypeScript is pinned at 6.0.3, the last JavaScript-based release, instead of the template's 7.0.2.<br>- ESLint's first run found 3 problems: two `any` types in the test fixtures (now typed), and the GS character in a regex. The regex is intended and carries a disable comment with the reason.<br>- `npm run lint` is clean, Vitest passes 35 of 35, and the build works. |
