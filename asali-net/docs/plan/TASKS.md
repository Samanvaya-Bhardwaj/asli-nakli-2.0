# Asali Network Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a decentralised medicine-verification network with 12 organisations on 4 PCs. Each organisation runs its own portal, its own differently structured database and its own text vault, and they share data read-only. Pack codes are scanned with misread correction, and verification combines the structured custody chain with ML-linked text evidence.

**Architecture:**
- One FastAPI codebase runs as any organisation. It contains the portal API (writes to its own database), the share API (GET-only, through a read-only database account), a signed network client and the verify engine.
- A directory service holds only addresses and public keys.
- One React portal adapts to the organisation type.
- Docker Compose runs one stack per PC, generated from `infra/network.yaml`, with Caddy for HTTPS.

**Tech Stack:**
- Python 3.11, FastAPI, Pydantic v2, pydantic-settings, psycopg 3, pymongo, sqlite3, httpx, cryptography (Ed25519), bcrypt, Meilisearch, scikit-learn, rapidfuzz, scipy, pytest, hypothesis, uv.
- React 19, Vite, TypeScript, Tailwind CSS v4, shadcn/ui, Motion, TanStack Query, React Router, lucide-react, Sonner, qrcode, barcode-detector, Vitest, Playwright, axe-core.
- Docker Compose, Caddy, mkcert.

**Spec:** `asali-net/docs/plan/PLAN.md`, `TEXT_ML.md`, `DESIGN.md` (read all three before Task 0.1).

## Global Constraints

1. **Work only inside `asali-net/`.** Never modify, move or delete anything outside it: the Phase 1–3 code, `databases/`, `dashboard/`, `Project2_Asali_Nakali/`. The one exception is the root `.gitignore`, and only in Task 0.4.
2. **No secrets in git.** No IP address, password, token or key in code or committed files. `.env` files and `infra/out/` are git-ignored; commit only `.env.example`.
3. **Tests first.** For every task: write the failing test, run it and see it fail, implement, run it and see it pass, commit. No task is done until its "Verify" commands print the expected output.
4. **Record before running** (vibe-coding record, `PLAN.md` D13). Before you run any new code file for the first time, run `python docs/vibe/snapshot.py <milestone> <files...>`. Every later change to that file that fixes something observed when it ran gets an entry in `docs/vibe/CHANGES.md`: what you saw, what you changed, which file.
5. **Never fake a result.**
   - Never write test output, metrics, screenshots or evidence by hand.
   - Evidence files are written only by scripts.
   - If a target is missed, report the miss.
   - If something cannot be done (no admin rights, no second PC), say so and stop that task.
6. **Code rules: `PLAN.md` section 15.** Files ≤ 400 lines; `ruff check` and `ruff format --check` clean; `mypy --strict` on `packages/` and `services/node/asali_node/verify/`; no bare `except`; no silent fallbacks.
7. **UI rules: `DESIGN.md` sections 3, 4 and 10.** The banned-pattern list is a hard rule.
8. **Commit after every task:** `git add <the task's files>` (never `git add -A` at repo root), with message `M<m>.<t>: <what>`. Work on branch `v2-network`.
9. **Stop and ask the user when:**
   - a decision marked "(confirm)" in `PLAN.md` section 2 has not been confirmed;
   - a tool needs administrator rights;
   - a metric target is still missed after two honest attempts;
   - a step would need data you would have to invent;
   - anything in this plan contradicts the spec.
10. **Pin versions.** When you first install a library, pin the exact version you got (`uv add pkg==x.y.z`, `npm i pkg@x.y.z`), and record it in `docs/vibe/VERSIONS.md`.

## Review Focus

- **Read-only sharing really is read-only:** the share router never holds a read-write connection or the vault admin key.
- **No central data store:** the directory has no medicine data; no node copies another node's tables.
- **Verdict rules match `PLAN.md` section 12** exactly, especially that allegations never raise a do_not_use reason.
- **Correction safety:** a corrected consumer reading never shows Genuine without confirmation.
- **Simulation and four-PC results are never mixed up** in evidence or wording.

---

## Repository layout (created in Task 0.4)

```
asali-net/
  pyproject.toml                  # uv workspace: packages/*, services/*
  README.md
  packages/
    asali_codes/asali_codes/{__init__,alphabet,checks,normalise,parse,confusion,candidates,read}.py
    asali_codes/tests/
    asali_text/asali_text/...     # TEXT_ML.md section 11
    asali_text/tests/
  services/
    directory/asali_directory/{main,store,settings}.py   directory/tests/   directory/Dockerfile
    node/asali_node/
      main.py settings.py logging_setup.py problems.py config_api.py
      canonical.py
      auth/{staff,signing,share_guard}.py
      directory_client.py
      network/{client,breaker}.py
      stores/{protocols,engines}.py  stores/<org_id>.py (12 files)
      schemas/<org_id>/{schema.sql|validators.json, MAPPING.md}
      portal/{common,pharma,distributor,shop,consumer,regulator,scan,documents}.py
      share/{common,regulator,consumer,documents}.py
      scan_sessions.py
      verify/{trace,rules,verdict,wording,cities,documents,text_checks,stream}.py
      vault/{client,bootstrap}.py
      text/{service,relink}.py
    node/tests/   node/Dockerfile
  apps/portal-web/                # Vite app (DESIGN.md)
  ml/{generate_corpus.py, templates/, data/, models/}
  seed/{seed_network.py, scenarios.py, expected.json}
  infra/{network.yaml, compose/, caddy/, scripts/}
  docs/{plan/, vibe/, runbook/, evidence/, architecture/}
```

---

## M0: Set-up

### Task 0.1: Safe starting point

**Files:** none.

- [ ] **Step 1:** Run `git status --short | wc -l` and `git branch --show-current`.
- [ ] **Step 2:** If the current branch has uncommitted Phase 3 work, **stop and ask the user** to commit it first. Don't commit it yourself unless asked.
- [ ] **Step 3:** `git switch -c v2-network`.
- [ ] **Verify:** `git branch --show-current` → `v2-network`.

### Task 0.2: Tools

**Files:** `asali-net/docs/vibe/VERSIONS.md`

- [ ] **Step 1:** Check what is installed:
  - Python 3.11 (`py -3.11 --version` on Windows, `python3.11 --version` on Mac);
  - Node 22 or newer (`node --version`);
  - Docker (`docker version`);
  - mkcert (`mkcert -version`);
  - uv (`uv --version`).
- [ ] **Step 2:** Install the missing ones:

  | Tool | Install command |
  |---|---|
  | uv | `py -3.11 -m pip install uv`, or `winget install astral-sh.uv` |
  | mkcert | `winget install FiloSottile.mkcert`, or `brew install mkcert` |
  | Docker Desktop | Windows needs WSL2: `wsl --install --no-distribution` in an administrator terminal, then a restart. **Ask the user to do this.** |

- [ ] **Step 3:** Write every version into `VERSIONS.md`.
- [ ] **Verify:** `docker run --rm hello-world` prints "Hello from Docker!". If Docker cannot run yet, write "Docker: not running (reason)" in `VERSIONS.md`, continue with M1–M4, which don't need Docker except the adapter tests on Postgres and Mongo, and tell the user.

### Task 0.3: Skills

**Files:** `.claude/` (written by the installer), `asali-net/docs/vibe/SKILLS.md`

- [ ] **Step 1:** If `.claude/skills/impeccable` doesn't exist yet, run from the repo root: `npx impeccable install --providers=claude --scope=project`, then `npx impeccable telemetry off`.
  - It was already installed on 18 Nov 2026 (engine v0.1.24) with `--no-hooks`, telemetry off.
  - To add Impeccable's design hook, which checks UI files after edits, ask the user first, then run `npx impeccable install --providers=claude --scope=project --force` and accept the hook.
- [ ] **Step 2:** Ask the user to type these in Claude Code, because you cannot run slash commands that install plugins:
  ```
  /plugin marketplace add obra/superpowers-marketplace
  /plugin install superpowers@superpowers-marketplace
  /plugin marketplace add blader/humanizer
  /plugin install humanizer@humanizer
  ```
  The humanizer plugin needs Claude Code 2.1.142 or newer; otherwise use `npx skills add blader/humanizer --agent claude-code`. The user then restarts Claude Code.
- [ ] **Step 3:** After the restart, list the available skills and record in `SKILLS.md` which ones are present: impeccable, superpowers (brainstorming, writing-plans, executing-plans, subagent-driven-development, test-driven-development, systematic-debugging, verification-before-completion, requesting-code-review), humanizer.
- [ ] **Verify:** `SKILLS.md` lists each skill as present or missing. If one is missing, say so in your report; don't pretend you used it.

### Task 0.4: Scaffold

**Files:**
- Create: everything in "Repository layout" as empty packages with `__init__.py`;
- Create: `asali-net/pyproject.toml`, `packages/*/pyproject.toml`, `services/*/pyproject.toml`, `asali-net/.gitignore`;
- Modify: root `.gitignore`, adding `asali-net/infra/out/`, `asali-net/**/.env`, `asali-net/**/node_modules/`, `asali-net/**/dist/`.

- [ ] **Step 1:** Write `asali-net/pyproject.toml` by hand (don't use `uv init`): a virtual root project with `[tool.uv.workspace] members = ["packages/*", "services/*"]` and a dev dependency group with `pytest`, `hypothesis`, `ruff`, `mypy`, `httpx`.
- [ ] **Step 2:** Each member gets its own `pyproject.toml` with its runtime dependencies:

  | Member | Runtime dependencies |
  |---|---|
  | `asali_codes` | none |
  | `asali_text` | `scikit-learn`, `rapidfuzz`, `scipy`, `numpy`, `joblib`, `asali_codes` |
  | `node` | `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `psycopg[binary,pool]`, `pymongo`, `httpx`, `cryptography`, `bcrypt`, `meilisearch`, `asali_codes`, `asali_text` |
  | `directory` | `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `cryptography` |

- [ ] **Step 3:** Add `ruff` config (line length 110, rules E, F, I, B, UP, SIM, RUF) and `mypy` config (`strict = true` for `asali_codes`, `asali_text` and `asali_node.verify`).
- [ ] **Step 4:** In `apps/`, run `npm create vite@latest portal-web -- --template react-ts`. Don't add libraries yet; M8 does that.
- [ ] **Verify:** `uv sync` succeeds; `uv run pytest` reports "no tests ran" (exit code 5); `uv run ruff check .` is clean; `npm --prefix apps/portal-web run build` succeeds.

### Task 0.5: Vibe-coding record

**Files:**
- Create: `docs/vibe/PROMPTS.md`, `docs/vibe/CHANGES.md`, `docs/vibe/snapshot.py`, `docs/vibe/README.md`.

- [ ] **Step 1:** In `PROMPTS.md`, paste the full text of `docs/plan/AGENT_PROMPT.md` as prompt V2-0, plus the user's original request, which the user gives you.
- [ ] **Step 2:** Write `snapshot.py <milestone> <file>...`. It copies each file to `docs/vibe/generated/<milestone>/<same relative path>` and refuses to overwrite an existing snapshot. Write its test first, in `docs/vibe/test_snapshot.py`.
- [ ] **Verify:** `uv run pytest docs/vibe` passes.

### Task 0.6: Product brief for Impeccable

- [ ] **Step 1:** Run `/impeccable init`. When it asks about the product, users, tone and constraints, answer from `DESIGN.md` sections 2, 3 and 4, and `PLAN.md` section 1.
- [ ] **Verify:** `PRODUCT.md` exists. It names the five portal types and the light work-tool direction. Read it, and make sure it doesn't contradict `DESIGN.md`; if it does, edit `PRODUCT.md`.

---

## M1: Codes (`packages/asali_codes`)

Interfaces this milestone produces (exact):

```python
# alphabet.py
ALPHABET: str = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
DECODE_ALIASES: dict[str, str] = {"O": "0", "I": "1", "L": "1"}

# checks.py
def gs1_check_digit(body13: str) -> str
def gtin_is_valid(gtin14: str) -> bool
def luhn32_check_char(payload: str) -> str
def luhn32_is_valid(full: str) -> bool

# normalise.py
def normalise_raw(raw: str) -> str                    # NFKC, strip, drop controls except \x1d, strip ]Q1 ]Q3 ]d2 ]C1
def normalise_serial(text: str) -> tuple[str, list[str]]   # (serial, notes) uppercase, drop space/-, alias map

# parse.py
FieldStatus = Literal["valid", "invalid_check", "invalid_char", "wrong_length", "missing"]
@dataclass(frozen=True)
class Reading:
    raw: str; grammar: Literal["digital_link","element_string","label_line","bare_serial","bare_gtin","unknown"]
    gtin: str | None; serial: str | None; lot: str | None; expiry: date | None
    status: dict[str, FieldStatus]                    # keys: gtin, serial, lot, expiry
def parse(raw: str) -> Reading

# confusion.py
def substitution_cost(true_ch: str, seen_ch: str) -> float
TRANSPOSE_COST = 0.6; INDEL_COST = 1.0

# candidates.py
@dataclass(frozen=True)
class Candidate: value: str; cost: float; edits: tuple[str, ...]   # edits like "pos3 0->9"
def serial_candidates(seen: str, issuers: Collection[str], max_cost: float = 2.0, limit: int = 200) -> list[Candidate]
def gtin_candidates(seen: str, known_gtins: Collection[str]) -> list[Candidate]

# read.py
Decision = Literal["accepted", "corrected", "needs_confirmation", "needs_choice", "unreadable"]
@dataclass(frozen=True)
class ReadResult:
    reading: Reading; decision: Decision
    gtin: str | None; serial: str | None; lot: str | None; expiry: date | None
    chosen: Candidate | None; choices: tuple[Candidate, ...]; message: str
ExistsFn = Callable[[str | None, list[str]], set[str]]   # (gtin or None, serial candidates) -> those that exist
def read(raw: str, *, context: Literal["staff", "consumer"], issuers: Collection[str],
         expected: Collection[tuple[str, str]] | None = None,        # (gtin, serial) pairs
         exists: ExistsFn | None = None, known_gtins: Collection[str] = ()) -> ReadResult
```

### Task 1.1: Alphabet and check characters

**Files:** Create `alphabet.py`, `checks.py`, `tests/test_checks.py`.

- [ ] **Step 1:** Write tests that load `docs/plan/test-vectors/codes.json` and assert:
  - every `gtin_valid` passes and every `gtin_invalid` fails;
  - every `luhn32_check_examples` payload gives its check character;
  - every `serial_valid` passes and every `serial_invalid` fails.
- [ ] **Step 2:** `uv run pytest packages/asali_codes -k checks` → FAIL (import error).
- [ ] **Step 3:** Implement. Use the reference code in `PLAN.md` section 9.3 exactly.
- [ ] **Step 4:** Run again → PASS. Snapshot first: `python docs/vibe/snapshot.py M1 packages/asali_codes/asali_codes/checks.py`.
- [ ] **Step 5:** Commit `M1.1: check digits`.

### Task 1.2: Normalisation

**Files:** Create `normalise.py`, `tests/test_normalise.py`.

- [ ] **Step 1:** Tests:
  - `normalise_examples` from the vectors;
  - `"]Q3https://..."` loses its prefix;
  - `"\x1d"` is kept;
  - `"ŤPM9"` (with an accent) is cleaned by NFKC or rejected with a note, never silently changed into a different valid letter;
  - `U` is reported in the notes as an invalid character.
- [ ] **Steps 2–5:** fail, implement, pass, commit `M1.2`.

### Task 1.3: Parsing

**Files:** Create `parse.py`, `tests/test_parse.py`.

- [ ] **Step 1:** Tests:
  - every `digital_link_examples` and `element_string_examples` case;
  - label lines in any order: `"LOT TP24A017 EXP 03/2027 SN TPM9-S346-Q37 GTIN 08901001000124"`;
  - the labels `B.No.` and `S/N`;
  - a bare serial with hyphens;
  - a bare GTIN;
  - garbage → `grammar="unknown"`;
  - expiry `DD=00` → last day of the month;
  - an element string without GS where the lot is followed directly by `21` (both splits tried, the one whose serial passes its check wins).
- [ ] **Steps 2–5:** fail, implement, pass, commit `M1.3`.

### Task 1.4: Confusion costs and candidates

**Files:** Create `confusion.py`, `candidates.py`, `tests/test_candidates.py`.

- [ ] **Step 1:** Port the prior pairs from the old `integration/uncertainty/confusion.py` (`_PRIOR_GROUPS`). Read it; don't import it. Keep only pairs where both characters are in the alphabet or are alias letters. Cost of any other substitution: 1.0.
- [ ] **Step 2:** Tests:
  - `serial_candidates("TPM0S346Q37", issuers={"TP","MV","KS"})` contains `TPM9S346Q37`;
  - every returned candidate passes Luhn and starts with a known issuer;
  - results are sorted by cost;
  - the limit is respected;
  - an adjacent swap of a valid serial yields the original at cost 0.6;
  - a GTIN with one wrong digit yields the right one when it is in `known_gtins`.
- [ ] **Step 3:** Implement candidates as a bounded best-first search: generate single edits, then edits of those, cheapest first, with a priority queue, de-duplicated, stopping at `max_cost` or `limit`.
- [ ] **Steps 4–5:** pass, commit `M1.4`.

### Task 1.5: `read()` decisions

**Files:** Create `read.py`, `tests/test_read.py`.

- [ ] **Step 1:** A table-driven test, one case per row of the decision table in `PLAN.md` section 10.2 step 7, for both `staff` (with `expected`) and `consumer` (with a fake `exists`). Must include:
  - a valid code → `accepted`;
  - staff, one expected candidate at cost 0.25 → `corrected`;
  - consumer, the same → `needs_confirmation`;
  - three candidates → `needs_choice`;
  - nothing → `unreadable`, with a message from `DESIGN.md` section 10.
- [ ] **Steps 2–5:** fail, implement, pass, commit `M1.5`.

### Task 1.6: Properties

**Files:** Create `tests/test_properties.py`.

- [ ] **Step 1:** Hypothesis tests:
  - for random valid serials, every single substitution fails Luhn;
  - for random valid serials and one confusable substitution, `read(..., context="staff", expected={(g, true)})` gives `corrected` with the true serial;
  - `parse(format(x)) == x` for generated Digital Links.
- [ ] **Verify:** `uv run pytest packages/asali_codes -q` → all pass; `uv run mypy packages/asali_codes` → no errors. Commit `M1.6`.

### Task 1.7: TypeScript port

**Files:** Create `apps/portal-web/src/lib/codes.ts`, `apps/portal-web/src/lib/codes.test.ts`.

- [ ] **Step 1:** Add Vitest (`npm i -D vitest@<pin>`). The test imports `../../../../docs/plan/test-vectors/codes.json` and checks the same cases as Tasks 1.1–1.3. Only normalise, parse and the checks are ported; candidates and `read` stay server-side.
- [ ] **Verify:** `npm --prefix apps/portal-web run test -- --run` → all pass. Commit `M1.7`.

---

## M2: Directory and node skeleton

### Task 2.1: Directory service

**Files:** Create `services/directory/asali_directory/{main,store,settings}.py`, `services/directory/tests/test_directory.py`, `services/directory/Dockerfile`.

Interfaces: the endpoints in `PLAN.md` section 8.1. SQLite table `orgs(org_id PK, org_type, name, city, state, issuer_code, gs1_prefix, base_url, public_key, host_name, registered_at, last_seen)`.

- [ ] **Step 1:** Tests:
  - register with the right join token → 201;
  - wrong token → 401;
  - the same org with a different key → 409;
  - a heartbeat with a valid signature updates `last_seen`;
  - `online` is false after 90 s (inject the clock);
  - the issuer and prefix lookups work, with longest-prefix match;
  - the store has no table other than `orgs` (assert on `sqlite_master`).
- [ ] **Steps 2–5:** fail, implement, pass, commit `M2.1`.

### Task 2.2: Node skeleton

**Files:** Create `settings.py`, `logging_setup.py`, `problems.py`, `config_api.py`, `main.py`, and `tests/test_skeleton.py`.

Settings (env names):

| Group | Variables |
|---|---|
| Identity | `ORG_ID`, `ORG_TYPE`, `ORG_NAME`, `ORG_CITY`, `ORG_STATE`, `ISSUER_CODE`, `GS1_PREFIX` |
| Engine | `ENGINE` (`postgres\|mongo\|sqlite`), `DB_RW_URL`, `DB_RO_URL`, `SQLITE_PATH` |
| Vault | `MEILI_URL`, `MEILI_MASTER_KEY` |
| Network | `DIRECTORY_URL`, `JOIN_TOKEN`, `PUBLIC_BASE_URL`, `HOST_NAME` |
| Mode and data | `ASALI_MODE` (`network\|simulation`), `DATA_DIR`, `SHOP_SETTINGS_JSON` |
| Staff | `STAFF_SEED_JSON` |

- [ ] **Step 1:** Tests:
  - `GET /share/v1/health` → 200;
  - an unknown route → problem JSON with `type`, `title`, `status`;
  - `GET /api/config` returns org identity and portal type, and no secrets (assert that no value contains `KEY`, `TOKEN` or `URL` of a database);
  - each request logs one JSON line with `request_id`.
- [ ] **Steps 2–5:** fail, implement, pass, commit `M2.2`.

### Task 2.3: Signing

**Files:** Create `auth/signing.py`, `auth/share_guard.py`, `tests/test_signing.py`.

```python
def load_or_create_keys(data_dir: Path) -> Ed25519PrivateKey
def public_key_b64(key) -> str
def sign_request(key, org_id: str, method: str, path_with_query: str, now: int) -> dict[str, str]  # the 3 headers
def verify_request(headers, method, path_with_query, now: int, lookup: Callable[[str], str | None]) -> str  # returns caller org_id or raises ShareAuthError(reason)
```

- [ ] **Step 1:** Tests: a valid signature passes; a changed path fails `bad_signature`; 121 s of skew fails `clock_skew`; an unknown org fails `unknown_org`; the guard on `/share/v1/*`, other than `/health`, returns 401 problem JSON with the reason.
- [ ] **Steps 2–5:** fail, implement, pass, commit `M2.3`.

### Task 2.4: Directory client

**Files:** Create `directory_client.py`, `tests/test_directory_client.py`.

- [ ] **Step 1:** Tests, using `httpx.MockTransport`:
  - `register()` sends the right body;
  - `orgs()` caches to `DATA_DIR/directory_cache.json`;
  - with the directory down, `orgs()` returns the cache with `stale_since` set;
  - the heartbeat loop calls heartbeat every 30 s (inject the interval).
- [ ] **Steps 2–5:** fail, implement, pass, commit `M2.4`.

### Task 2.5: Network client

**Files:** Create `network/client.py`, `network/breaker.py`, `tests/test_network_client.py`.

```python
class SourceUnavailable(Exception): org_id: str; reason: str
class ShareClient:
    async def get(self, org_id: str, path: str, params: dict | None = None) -> dict   # signs, 2 s timeouts, 1 retry, breaker
    async def gather(self, calls: list[tuple[str, str, dict | None]], budget_s: float) -> list[dict | SourceUnavailable]
```

- [ ] **Step 1:** Tests:
  - a timeout gives `SourceUnavailable(reason="timeout")`;
  - after two failures the breaker skips the node for 30 s (`reason="skipped"`);
  - `gather` returns within the budget and marks late calls `reason="budget"`;
  - the signature headers are present.
- [ ] **Steps 2–5:** fail, implement, pass, commit `M2.5`.

### Task 2.6: Two nodes talking

**Files:** Create `services/node/Dockerfile` (multi-stage: build `apps/portal-web`, then a Python 3.11 slim runtime copying `dist/` to `/app/static`), and `infra/compose/dev-two-nodes.yml` (directory plus two SQLite nodes, plain HTTP, dev only).

- [ ] **Verify:**
  - `docker compose -f infra/compose/dev-two-nodes.yml up -d --build`;
  - then `uv run python infra/scripts/smoke_two_nodes.py`. Write this script: it calls node A's `/api/debug/ask?org=B&path=/share/v1/org`, a dev-only endpoint that exists only when `ASALI_MODE=simulation`. It must print B's org JSON with `served_by.host_name`.
  - `docker compose ... down`. Commit `M2.6`.

---

## M3: Storage

### Task 3.1: Canonical models

**Files:** Create `canonical.py`, `tests/test_canonical.py`.

- [ ] **Step 1:** Pydantic v2 models exactly as in `PLAN.md` section 6.
- [ ] **Step 2:** Tests: datetimes must be timezone-aware (naive ones are rejected); `event_type` and status literals are enforced.
- [ ] **Step 3:** Commit `M3.1`.

### Task 3.2: Store protocols

**Files:** Create `stores/protocols.py`.

```python
class CommonStore(Protocol):
    def get_staff(self, username: str) -> StaffRecord | None
    def add_staff(self, rec: StaffRecord) -> None
    def add_scan_correction(self, c: ScanCorrection) -> None
    def upsert_document_links(self, doc_id: str, links: list[DocLink]) -> None
    def documents_linked_to(self, entity_keys: list[str]) -> list[str]

class PharmaStore(CommonStore, Protocol):
    def add_product(self, p: NewProduct) -> Product
    def products(self) -> list[Product]
    def create_batch(self, b: NewBatch) -> Batch
    def batches(self, gtin: str | None = None) -> list[Batch]
    def commission_units(self, gtin: str, lot: str, serials: list[str], at: datetime) -> int
    def record_shipment(self, s: NewShipment) -> Shipment
    def recall_batch(self, gtin: str, lot: str, reason: str, level: str, at: datetime) -> None
    def unit_view(self, gtin: str, serial: str) -> UnitView
    def existing_serials(self, gtin: str | None, serials: list[str]) -> set[str]
    def shipments_to(self, org_id: str, since: datetime | None = None) -> list[Shipment]
    def stock(self) -> list[StockLine]          # commissioned, not shipped

class HolderStore(CommonStore, Protocol):        # distributor and shop
    def record_receipt(self, r: NewReceipt) -> None        # from_org, source_ref, at, units, by
    def received_refs(self) -> set[tuple[str, str]]        # (from_org, source_ref)
    def record_dispatch(self, d: NewDispatch) -> Shipment  # distributor only; shop raises NotSupported
    def record_sale(self, s: NewSale) -> None              # shop only
    def record_return(self, r: NewReturn) -> None          # shop only
    def unit_view(self, gtin: str, serial: str) -> UnitView
    def stock(self) -> list[StockLine]
    def shipments_to(self, org_id: str, since: datetime | None = None) -> list[Shipment]

class ConsumerStore(CommonStore, Protocol):
    def record_check(self, c: NewCheck) -> str
    def record_report(self, r: NewReport) -> str
    def scan_stat(self, gtin: str, serial: str) -> ScanStat
    def reports(self, since: datetime | None = None) -> list[ReportRecord]

class RegulatorStore(CommonStore, Protocol):
    def add_alert(self, a: NewAlert) -> Alert
    def alerts(self, gtin: str | None = None, lot: str | None = None, state: str | None = None) -> list[Alert]
    def set_licence(self, l: Licence) -> None
    def licences(self, org_ids: list[str] | None = None) -> list[Licence]
    def add_inspection(self, i: NewInspection) -> None
```

Every store is built with a `mode: Literal["rw", "ro"]`. In `ro` mode it opens the read-only connection, and its write methods must fail at the database, not in Python (Task 3.16 checks this).

- [ ] **Commit** `M3.2`.

### Task 3.3: Engines and read-only accounts

**Files:** Create `stores/engines.py`, `infra/compose/init/postgres-init.sql.tmpl`, `infra/compose/init/mongo-init.js.tmpl`, `infra/compose/test-engines.yml`.

- [ ] **Step 1:** In `engines.py`:
  - `pg_pool(url)`: a `psycopg_pool.ConnectionPool` with min 1, max 4;
  - `mongo_db(url)`;
  - `sqlite_conn(path, ro)`: `sqlite3.connect(f"file:{path}?mode=ro", uri=True)` for ro; WAL mode for rw.
- [ ] **Step 2:** Init templates:
  - **Postgres:** create role `app_rw` (owner of the schema) and role `share_ro`:
    `GRANT CONNECT; GRANT USAGE ON SCHEMA public; GRANT SELECT ON ALL TABLES IN SCHEMA public; ALTER DEFAULT PRIVILEGES ... GRANT SELECT`.
  - **Mongo:** user `app_rw` with `readWrite` on the org database; user `share_ro` with `read`.
- [ ] **Step 3:** `test-engines.yml` runs one postgres and one mongo on ports 55432 and 57017 for tests.
- [ ] **Commit** `M3.3`.

### Tasks 3.4 – 3.15: One adapter per organisation

There is one task per org, in this order:

| Task | Org |
|---|---|
| 3.4 | `tarang` |
| 3.5 | `medivra` |
| 3.6 | `kesar` |
| 3.7 | `dist_north` |
| 3.8 | `dist_west` |
| 3.9 | `dist_south` |
| 3.10 | `shop_delhi` |
| 3.11 | `shop_mumbai` |
| 3.12 | `shop_bengaluru` |
| 3.13 | `consumer_delhi` |
| 3.14 | `consumer_mumbai` |
| 3.15 | `regulator` |

Python file names use underscores; org ids keep their hyphens.

**Files per task:**
- `stores/<org>.py`;
- `schemas/<org-id>/schema.sql` (SQL engines), or `schemas/<org-id>/validators.json` (Mongo `$jsonSchema` per collection, plus index list);
- `schemas/<org-id>/MAPPING.md`.

**Steps per task:**
- [ ] **Step 1:** Write the native schema exactly as in `PLAN.md` section 5, plus the common tables:
  - `staff`;
  - `scan_corrections(id, at, raw, field, chosen, cost, confirmed_by)`;
  - `document_links(doc_id, entity_type, entity_key, confidence, linked_at)`.

  Use this org's own naming style for the common tables too: Kesar `SCN_CORR`, Medivra camelCase collections, and so on.
- [ ] **Step 2:** Write `MAPPING.md`. One table row per canonical field the store returns: canonical field | native field(s) | conversion | example.
- [ ] **Step 3:** Run the contract tests (Task 3.16) for this org. They fail.
- [ ] **Step 4:** Implement the store until its contract tests pass. Conversions follow `PLAN.md` section 6; unknown status codes raise `ValueError`.
- [ ] **Step 5:** Snapshot before the first run, then commit `M3.<n>: <org> store`.

**Verify per task:** `uv run pytest services/node/tests/stores -k <org>` → all pass.

### Task 3.16: Contract suite and read-only enforcement

**Files:** Create `tests/stores/conftest.py`, `tests/stores/test_contract_pharma.py`, `test_contract_holder.py`, `test_contract_consumer.py`, `test_contract_regulator.py`, `test_readonly.py`.

(Write this before Task 3.4; it is listed here because it applies to all of them.)

- [ ] **Step 1:** Fixtures:
  - build each org's store in `rw` and `ro` mode against a fresh database;
  - Postgres and Mongo come from `test-engines.yml`, and those tests are skipped with a clear reason if those ports are closed;
  - SQLite uses a temp file.
- [ ] **Step 2:** Contract tests per protocol. Examples for pharma:
  - add product → create batch → commission 5 → ship 3 to `dist-north`;
  - `unit_view` of a shipped unit has events `commission` and `ship` with `to_org="dist-north"`;
  - `shipments_to("dist-north")` returns 1 shipment with 3 units;
  - `existing_serials` returns only the real ones;
  - dates are aware and in IST;
  - `stock()` is 2.
- [ ] **Step 3:** `test_readonly.py`: for every org, the `ro` store's write methods raise a database permission or read-only error. Assert on the exception type from the driver:
  - Postgres `InsufficientPrivilege`;
  - Mongo `OperationFailure`, code 13;
  - SQLite `OperationalError` "attempt to write a readonly database".
- [ ] **Verify:** with `test-engines.yml` up, `uv run pytest services/node/tests/stores -q` → all pass, none skipped. Commit `M3.16`.

---

## M4: APIs

### Task 4.1: Staff auth

**Files:** Create `auth/staff.py`, `portal/common.py` (`/api/login`, `/api/logout`, `/api/me`), `tests/test_staff_auth.py`.

- [ ] Tests:
  - seed staff from `STAFF_SEED_JSON` on first start, with bcrypt hashes;
  - login sets an HttpOnly, SameSite=Lax cookie;
  - a wrong password → 401 problem JSON "Wrong username or password.";
  - portal write routes without a session → 401;
  - consumer routes `/api/check` and `/api/report` need no session.
- [ ] Implement, pass, commit `M4.1`.

### Task 4.2: Share API, common routes

**Files:** Create `share/common.py`, `tests/test_share_common.py`.

| Route | Returns |
|---|---|
| `GET /share/v1/org` | `Org`, plus `engine` and `vault` (for the Network page) |
| `GET /share/v1/units/{gtin}/{serial}` | `UnitView` with `served_by` |
| `GET /share/v1/units/exists?gtin=&serials=A,B` | `{"existing": [...]}` (pharma only) |
| `GET /share/v1/products`, `GET /share/v1/batches?gtin=` | catalogue (pharma only) |
| `GET /share/v1/shipments?since=` | shipments where `to_org` = the caller (pharma and distributor) |

- [ ] Tests:
  - every route uses the `ro` store; assert by injecting a store spy;
  - `POST`, `PUT` and `DELETE` on any share path → 405;
  - `shipments` called by an org that isn't the addressee → empty list;
  - a non-pharma org asked `/units/exists` → 404 problem JSON.
- [ ] Implement, pass, commit `M4.2`.

### Task 4.3: Share API, role routes

**Files:** Create `share/regulator.py` (`/alerts`, `/licences`), `share/consumer.py` (`/scans/{gtin}/{serial}`, `/reports`, the bulk one regulator-only), `share/documents.py` (`/documents/search`, `/documents/{doc_id}`, returning empty until M7), and tests.

- [ ] Tests: role restrictions (403 for a non-regulator on bulk); `ScanStat` contains no device hashes and no times finer than the minute.
- [ ] Implement, pass, commit `M4.3`.

### Task 4.4: Scan sessions

**Files:** Create `scan_sessions.py`, `portal/scan.py`, `tests/test_scan_sessions.py`.

```text
POST /api/scan/sessions   {kind: "dispatch"|"receive"|"sell"|"return", to_org?, from_org?, source_ref?}  -> {session_id, expected_count}
POST /api/scan/sessions/{id}/read  {raw, source: "wedge"|"camera"|"typed"}  -> ScanRow
POST /api/scan/sessions/{id}/rows/{row_id}/undo | /choose {serial}
POST /api/scan/sessions/{id}/finish  -> the written record (shipment, receipt, sale)
DELETE /api/scan/sessions/{id}
```

The expected set comes from:

| Kind | Expected set |
|---|---|
| dispatch, sell | own stock |
| receive | the sender's `/share/v1/shipments` entry with that `source_ref` |
| return | own sold units |

- Sessions live in memory, with a 2 h time-to-live. The UI says "This scan session expired" if one is gone.
- `finish` refuses while any row is `needs_choice` or `rejected`, because those must be removed first.
- Corrections are saved with `add_scan_correction`.
- [ ] Tests: each row state in `DESIGN.md` section 6.1, duplicates, finish refusal, the receive discrepancy count.
- [ ] Implement, pass, commit `M4.4`.

### Task 4.5: Portal API, pharma

**Files:** Create `portal/pharma.py`, `tests/test_portal_pharma.py`.

Routes:
- `GET/POST /api/products`;
- `GET/POST /api/batches`;
- `POST /api/batches/{lot}/packs {count}` (generates serials per `PLAN.md` section 9.2 and commissions them);
- `GET /api/batches/{lot}/labels` (label data: Digital Link URI and human-readable line per pack);
- `POST /api/recalls`;
- `GET /api/activity`.

- [ ] Tests:
  - serials are unique, pass Luhn and start with the issuer code;
  - the GTIN is generated from the prefix with a valid check digit;
  - a recall changes batch status in `share/v1/batches`.
- [ ] Implement, pass, commit `M4.5`.

### Task 4.6: Portal API, distributor and shop

**Files:** Create `portal/distributor.py`, `portal/shop.py`, tests.

| Route | Behaviour |
|---|---|
| `GET /api/incoming` | Asks every upstream org for its `/share/v1/shipments` (distributor: all pharma; shop: distributors serving its state), minus `received_refs()` |
| `GET /api/stock` | Own stock |
| `GET /api/alerts` (shop) | Regulator alerts filtered by the shop's state |
| `GET /api/parties?type=` | Directory orgs, with region filtering (distributor `served_states` comes from `network.yaml`, passed in env) |

- [ ] Tests: `incoming` with one upstream unreachable returns the others plus a `sources` entry saying who didn't answer.
- [ ] Implement, pass, commit `M4.6`.

### Task 4.7: Portal API, consumer and regulator (without verify)

**Files:** Create `portal/consumer.py` (`/api/report`; `/api/check` is added in M6) and `portal/regulator.py` (`/api/alerts` POST and GET, `/api/licences`).

- [ ] Tests: the report text is redacted before storage. A stub redactor is fine here; M7 replaces it.
- [ ] Commit `M4.7`.

### Task 4.8: TypeScript API types

- [ ] Add `openapi-typescript@<pin>` and the script `npm run gen:api`: it fetches `/openapi.json` from a running dev node and writes `src/api/schema.d.ts`.
- [ ] Commit the generated file.

---

## M5: Network description, simulation and seed data

### Task 5.1: `infra/network.yaml`

**Files:** Create `infra/network.yaml`, `infra/scripts/network_model.py` (Pydantic loader), and tests.

- [ ] The content is exactly the orgs, PCs, ports, engines, cities, issuer codes, prefixes, served states and shop settings from `PLAN.md` sections 3 and 5. No IP addresses.
- [ ] Tests:
  - ports are unique;
  - every org is on exactly one PC;
  - issuer codes use only alphabet characters and are unique;
  - every shop has the location fields.
- [ ] Commit `M5.1`.

### Task 5.2: Stack generator and simulation stack

**Files:** Create `infra/scripts/make_stack.py`, `infra/compose/templates/*.j2` (use `string.Template` if you'd rather not add Jinja), `infra/caddy/Caddyfile.tmpl`, and tests.

- [ ] `make_stack.py --pc <PC> --ip <ip> --directory-url <url>` and `make_stack.py --simulation` write `infra/out/<PC|SIM>/{compose.yml, Caddyfile, .env}`. `.env` holds generated random passwords; keep existing ones on re-run.
- [ ] The memory limits from `PLAN.md` section 16.5 are written into the compose file.
- [ ] Caddy uses the certificate files `infra/out/<PC>/certs/{cert.pem,key.pem}` made by `make_cert.py` (Task 11.1). For simulation, use `tls internal`.
- [ ] **Verify:**
  - `uv run python infra/scripts/make_stack.py --simulation`;
  - `docker compose -f infra/out/SIM/compose.yml --env-file infra/out/SIM/.env up -d --build`;
  - after 60 s, `uv run python infra/scripts/check_stack.py --simulation` prints 12 lines `OK <org> <host>`, and the directory lists 12 orgs online.
- [ ] Commit `M5.2`.

### Task 5.3: Seed through the portals

**Files:** Create `seed/seed_network.py`, `seed/catalogue.yaml`.

- [ ] The catalogue: 3 pharma × 4 products (realistic generics: amoxicillin 500 mg, paracetamol 650 mg, insulin glargine 100 IU/ml for cold chain, azithromycin 500 mg, atorvastatin 10 mg, pantoprazole 40 mg…), each with fictional brand names. 3 batches per product, 40 packs per batch.
- [ ] The flow uses only portal APIs, logged in as each org's seeded staff:
  - pharma commissions;
  - pharma ships to distributors according to region;
  - distributors receive, then dispatch to shops in their states;
  - shops receive and sell about 60% of their stock over simulated dates;
  - consumers check about 30% of the sold packs.
- [ ] Every scan goes through the scan-session endpoints with source `typed`. About 3% of inputs have injected confusions, so the correction path is used.
- [ ] Simulated time: the seed passes `at` values. The portal API accepts `at` only when `ASALI_MODE=simulation`.
- [ ] **Verify:** `uv run python seed/seed_network.py --simulation` prints per-org counts. Running it twice doesn't duplicate anything; it checks first.
- [ ] Commit `M5.3`.

### Task 5.4: Scenarios S1–S9

**Files:** Create `seed/scenarios.py`, `seed/expected.json`.

- [ ] Plant each scenario from `PLAN.md` section 17 through the portal APIs. S3 needs two shops to each record a sale of the same serial: give `shop-mumbai` a receipt for a pack it was never shipped. It is a fake pack carrying a copied code; the receipt comes from a distributor ref that doesn't exist, which is also what makes it a copy.
- [ ] Write the expected verdict and reason codes per scenario.
- [ ] Commit `M5.4`.

---

## M6: Verification (structured)

### Task 6.1: Cities

**Files:** `verify/cities.py` and a test.

- [ ] The coordinates of every city in `network.yaml` plus the cities used in the corpus; `distance_km(a, b)` with haversine.
- [ ] Test: Delhi–Mumbai is between 1,100 and 1,200 km.

### Task 6.2: Rules, table-driven, no network

**Files:** `verify/rules.py`, `tests/verify/test_rules.py`.

```python
@dataclass(frozen=True)
class Facts:
    pack: PackInfo | None; chain: list[Hop]; alerts: list[Alert]; licences: list[Licence]
    other_sells: list[Event]; scan_stats: list[ScanStat]; doc_signals: list[DocSignal]; missing: list[SourceStatus]
    issuer_known: bool; issuer_reachable: bool; today: date
def reasons(f: Facts) -> list[Reason]          # PLAN.md 12.2, in that order
```

- [ ] Each reason gets at least one case where it is raised and one where it isn't. Edge cases:
  - expiry today counts as not expired;
  - two sells by the same shop (a return and a resale) is not a copied code if a return event lies between them;
  - a licence that expired after the sale date doesn't count.
- [ ] Pass, commit `M6.2`.

### Task 6.3: Verdict and wording

**Files:** `verify/verdict.py`, `verify/wording.py`, tests.

- [ ] The precedence in `PLAN.md` section 12.3, and the headlines in section 12.3 plus `DESIGN.md` section 10.
- [ ] Tests:
  - every verdict and reason combination has a headline;
  - headlines contain no banned word (`DESIGN.md` section 10.2 rule 4; share the list in `verify/banned_words.py` with the UI check);
  - no headline has an em dash or an exclamation mark.

### Task 6.4: Trace

**Files:** `verify/trace.py`, `tests/verify/test_trace.py`. The tests use a fake `ShareClient` with canned responses.

- [ ] The pseudocode in `PLAN.md` section 12.1. Every hop's `served_by` goes into the result.
- [ ] Tests:
  - a 3-hop chain;
  - a gap at hop 2 (unreachable);
  - a chain break;
  - an unknown issuer;
  - the budget is exceeded on a side query: the result still comes back, with that source marked `budget`.

### Task 6.5: Verify endpoints

**Files:** `portal/consumer.py` (`POST /api/check`), `verify/stream.py` (`GET /api/verify/stream?raw=...`, with SSE events `progress {asked, answered, total}` and `result {...}`), and `portal/regulator.py` (`POST /api/investigate`, the same engine).

- [ ] `/api/check` runs `codes.read` with `context="consumer"`. If the decision is `needs_confirmation`, it returns that and doesn't verify. `POST /api/check/confirm {check_id, serial}` continues.
- [ ] Every check is recorded with `record_check`.

### Task 6.6: Network scenario tests

**Files:** `tests/network/test_scenarios.py`, marked `network`, which run only when `--simulation-up` is given.

- [ ] For S1, S2, S3 (structured part: `COPIED_CODE`), S4, S7, S8 and S9: call the consumer-delhi node and compare with `seed/expected.json`.
- [ ] S8: `docker compose stop dist-west-app` inside the test, then restart it.
- [ ] **Verify:** `uv run pytest -m network --simulation-up -q` → all pass. Commit `M6.6`.

---

## M7: Text and ML

Follow `TEXT_ML.md` exactly. File names are as in its section 11.

### Task 7.1: Vault

**Files:** `vault/client.py`, `vault/bootstrap.py`, `share/documents.py` (real implementation), tests (Meilisearch from `test-engines.yml`, add it there).

- [ ] Bootstrap:
  - create index `docs` with the searchable, filterable and sortable settings from `TEXT_ML.md` section 5;
  - create the scoped admin key and the search-only key;
  - save their uids, not the master key, to `DATA_DIR/vault_keys.json`.
- [ ] Test: the search key can't add documents (Meilisearch returns 403).

### Task 7.2: Clean, redact, language

**Files:** `clean.py`, `language.py`, tests. Cases: Indian phone formats, e-mails, a 12-digit id, Hinglish detection.

### Task 7.3: Mentions and gazetteer

**Files:** `mentions.py`, `gazetteer.py`, tests. One test per row of the `TEXT_ML.md` section 4.4 table, with the span checked.

### Task 7.4: Corpus generator

**Files:**
- `ml/generate_corpus.py`;
- `ml/templates/<doc_type>/*.yaml` (at least 6 families per type, each with paraphrase banks);
- tests that check determinism (same seed, same output), the family split (no family in two splits), the noise rates and the hard negatives present.

- [ ] It reads the seeded simulation network through share APIs, signed as a dev tool identity registered with the directory in simulation mode only.
- [ ] **Verify:** `uv run python ml/generate_corpus.py --seed 42 --out ml/data/generated` prints counts per type and split close to `TEXT_ML.md` section 2.

### Task 7.5: M1 and M2

**Files:** `classify_type.py`, `classify_issue.py`, `train.py` (these two models), and tests on a small fixture set.

- [ ] **Verify:** `uv run python -m asali_text.train --models m1,m2 --corpus ml/data/generated --out ml/models` prints the validation scores. The test-set scores are printed only by `evaluate`.

### Task 7.6: M3 linking

**Files:** `link.py`, `features.py`, `train.py` (m3), and tests.

- [ ] Candidate generation per `TEXT_ML.md` section 4.5.
- [ ] Features f1–f11; each feature gets a unit test with a hand-made pair.
- [ ] Training pairs come from `truth.jsonl`: positives are the true links, negatives are all other candidates, including the hard negatives.
- [ ] The baseline "exact code match only" is implemented for the ablation.

### Task 7.7: Claims

**Files:** `claims.py` and tests, one per row of `TEXT_ML.md` section 4.6.

### Task 7.8: Pipeline in the node

**Files:**
- `asali_text/pipeline.py`;
- `text/service.py`;
- `portal/documents.py` (`POST /api/documents`, `GET /api/documents`, `GET /api/documents/{id}`, `POST /api/documents/{id}/links/{key}/reject`);
- `text/relink.py` (background task);
- system documents: the recall notice (pharma recall), the regulator notice (alert) and the discrepancy note (receipt with missing units), written from templates in `text/system_docs.py`.

- [ ] Models load once at start-up from `/app/ml/models`.
- [ ] Ingest is synchronous for documents under 20 KB, and runs as a background task above that.
- [ ] Re-seed the corpus through the portal APIs: `ml/generate_corpus.py --post`.

### Task 7.9: Clusters

**Files:** `clusters.py`, the regulator `GET /api/complaints` (bulk read of consumer reports, grouped), and tests.

### Task 7.10: Text in the verdict

**Files:** `verify/documents.py`, `verify/text_checks.py`; update `rules.py` with `DocSignal` handling; tests.

- [ ] Retrieval per `TEXT_ML.md` section 7; claim checks per section 6.2; rules per section 6.3 and `PLAN.md` section 12.4.
- [ ] Table-driven tests:
  - a single complaint changes nothing;
  - an official notice at 0.95 raises `QUALITY_FAILED`;
  - the same notice at 0.7 raises `QUALITY_NOTICE_POSSIBLE`;
  - an excursion on a non-cold-chain product raises nothing.
- [ ] **Verify:** `uv run pytest -m network --simulation-up -k "S3 or S5 or S6"` → pass.

### Task 7.11: Evaluation report

**Files:** `evaluate.py`, `ml/data/handwritten/README.md` (format and instructions for the team, no documents), `ml/models/MODEL_CARD.md`.

- [ ] **Verify:** `uv run python -m asali_text.evaluate --out docs/evidence/ml` writes `report.md` and `metrics.json`.
  - The first lines give the date, the commit, the dataset sizes, and the hand-written set status.
  - Compare with the targets in `TEXT_ML.md` section 9.2. If any target is missed, write it under "Missed targets" in the report and tell the user. Don't tune on the test split.

---

## M8: UI foundation

Before starting: run `/impeccable shape the scan session screen for warehouse staff` and `/impeccable shape the consumer check screen`. Save the outputs to `docs/evidence/ui/shape-*.md`. Where they differ from `DESIGN.md` section 6, keep `DESIGN.md` and note why in the same file.

### Task 8.1: Libraries, tokens, fonts

- [ ] Install, pinning each exact version:
  - `tailwindcss` v4 with its Vite plugin;
  - `motion`, `@tanstack/react-query`, `react-router`, `lucide-react`, `sonner`, `qrcode`, `barcode-detector`;
  - `@fontsource/atkinson-hyperlegible-next` and `@fontsource/atkinson-hyperlegible-mono`. If these names don't exist, find the right ones on npm, or self-host from Google Fonts; record what you did.
- [ ] `npx shadcn@latest init`. Add only Button, Input, Label, Select, Dialog, Sheet, Popover, Tooltip, Table, Badge, Separator, Skeleton, Sonner.
- [ ] `src/styles/tokens.css` exactly as in `DESIGN.md` section 3.1. Then re-skin the shadcn components to use the tokens: remove `shadow-sm` from static surfaces, use our radii.
- [ ] `scripts/check_contrast.mjs`: computes the contrast of every text/background pair in the token file, for both themes, and fails under the thresholds in `DESIGN.md` section 3.1.
- [ ] **Verify:** `npm run check:contrast` passes; `npm run build` passes.

### Task 8.2: Shell and routing

- [ ] `/api/config` → `data-portal` attribute, the role's routes (`DESIGN.md` section 5.2), the sidebar and the mobile bottom bar.
- [ ] Login page; the simulation band; `NetworkStatus`.
- [ ] Vitest tests: each portal type renders its own nav; the simulation band appears only in simulation.

### Task 8.3: `Code`, `ScanBox`, `ScanList`, sounds

- [ ] Wedge burst detection per `PLAN.md` section 10.3 as a hook, `useScannerBursts`, with unit tests feeding timed key events.
- [ ] Camera: `barcode-detector`, in a Sheet. Only on secure contexts; otherwise the message from `DESIGN.md` section 6.1.
- [ ] Sounds and vibration per `DESIGN.md` section 8.

### Task 8.4: Result components

- [ ] `VerdictBlock`, `PackHistory`, `ReasonList`, `EvidenceList`, `EmptyState`, `ProblemMessage`, `PartyPicker`.
- [ ] A `/dev/components` route showing every state from `DESIGN.md` section 7.
- [ ] One Vitest render test per state.

### Task 8.5: First design review

- [ ] Run `/impeccable critique` and `/impeccable audit` on `/dev/components` and the shell. Save them to `docs/evidence/ui/m8-critique.md` and `m8-audit.md`.
- [ ] Fix every P0 and P1 item, and list what you didn't fix and why.
- [ ] Run `npx impeccable detect --json apps/portal-web/src` and fix all findings.

---

## M9: Screens

For each screen: build it, then run `/impeccable layout <screen>` and `/impeccable typeset <screen>`, apply the fixes, and add or extend a Playwright test.

### Task 9.1: Pharma

`/dispatch`, `/batches`, `/batches/:lot`, `/batches/:lot/labels` (print stylesheet: A4, 3×8 labels, QR from `qrcode` as SVG, the human-readable line in the mono font), `/products`, `/recalls`, `/documents`, `/activity`.

### Task 9.2: Distributor

`/receive` (incoming list with sender, date and count), `/receive/:shipment` (scan session with "18 of 20" and "Show the 2 missing"), `/dispatch`, `/stock` (near-expiry highlighted), `/documents`, `/activity`.

### Task 9.3: Shop

- `/sell`, with the receipt print: receipt language from settings, shop details, packs, verify QR to the city's consumer portal. Translations live in `src/i18n/receipt.{en,hi,mr,kn}.json`. **The team must check the Hindi, Marathi and Kannada strings**: mark them "needs review" in the file until a person confirms.
- `/receive`, `/stock`, `/returns`, `/alerts`, `/documents`.

### Task 9.4: Consumer

- `/` (check, with typed input and camera);
- the confirmation step for corrected readings;
- live progress from SSE;
- `/result/:checkId`, `/report`, `/history` (local storage, wrapped in try/catch).

### Task 9.5: Regulator

`/investigate` (trace plus document search with filters), `/complaints` (grouped by batch, M5 flag), `/alerts`, `/licences`, `/network`.

### Task 9.6: End-to-end tests

**Files:** `apps/portal-web/e2e/*.spec.ts`, with Playwright running against the simulation stack.

The flows:
1. Pharma creates a batch, makes 10 packs and dispatches 5 to `dist-north`, scanned by typing.
2. `dist-north` receives 4 of them; "1 missing" is shown and a discrepancy note is created.
3. `dist-north` dispatches 3 to `shop-delhi`.
4. `shop-delhi` receives them and sells 1.
5. `consumer-delhi` checks the sold pack → Genuine, with 3 different host names in the history (all simulation host names, labelled as simulation).
6. The consumer types the code with O for 0 → confirmation → Genuine.
7. A wedge burst is simulated with `page.keyboard.type(code, {delay: 5})` followed by Enter.
8. The S3 serial → Do not use, with the contradiction shown.
9. `dist-west` is stopped → the Cannot check wording for a pack on its route.

Every test runs `@axe-core/playwright` → 0 violations. Screenshots go to `docs/evidence/ui/e2e/`.

**Verify:** `npm run e2e` → all pass.

---

## M10: De-slop and polish

### Task 10.1: Impeccable passes

- [ ] Run, one at a time, over all routes, committing between them: `/impeccable distill`, `/impeccable clarify`, `/impeccable harden`, `/impeccable adapt`, `/impeccable polish`.
- [ ] Save each report to `docs/evidence/ui/m10-<command>.md`.
- [ ] Don't use `bolder`, `overdrive` or `delight`.
- [ ] **Verify:** `npx impeccable detect --json apps/portal-web/dist > docs/evidence/ui/detect.json` reports 0 findings; so does `npx impeccable detect http://localhost:8202` against the running simulation.

### Task 10.2: Copy check

**Files:** `apps/portal-web/scripts/check_copy.mjs`.

- [ ] It scans `src/**/*.{ts,tsx,json}` string literals and JSX text for:
  - the banned words (shared list);
  - `!`;
  - em dashes;
  - emoji (Unicode `Extended_Pictographic`);
  - Title Case on buttons (a heuristic: more than one capitalised word that isn't a proper noun from an allow-list).
- [ ] **Verify:** `npm run check:copy` → 0 findings.

### Task 10.3: Docs prose

- [ ] Run `/humanizer` on `README.md`, `docs/runbook/*.md`, help notes in `src/help/*.md`, and the report (M12).
- [ ] Review the changes; keep facts, commands and numbers exactly as they were.

### Task 10.4: Backend clean-up

- [ ] `/simplify` on `services/` and `packages/`, then `/code-review` on the full branch diff. Fix the findings, or record why one doesn't apply.
- [ ] `infra/scripts/check_file_sizes.py`: fails if any `.py`, `.ts` or `.tsx` file is over 400 lines.
- [ ] **Verify:** these all pass: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run pytest -q`, `npm run lint`, `npm run test -- --run`, `uv run python infra/scripts/check_file_sizes.py`.

---

## M11: Four PCs

### Task 11.1: Certificates and network checks

**Files:** `infra/scripts/make_cert.py`, `infra/scripts/check_lan.py`, `infra/scripts/windows_firewall.ps1`.

- [ ] `make_cert.py --ip <ip> --pc <PC>` calls mkcert with SANs for the IP, the PC's hostname and `localhost`, and writes `infra/out/<PC>/certs/`.
- [ ] `check_lan.py --peers ...` does a TCP connect to the peers' Caddy ports and prints a matrix. Before stacks are up, a tiny `--listen` mode opens test ports.

### Task 11.2: Runbook

**Files:** `docs/runbook/FOUR_PCS.md`.

- [ ] The exact steps from `PLAN.md` section 16.4, with the commands for Windows (PowerShell) and Mac (zsh), what success looks like at each step, and what to do when a step fails.
- [ ] Have it checked by `/humanizer`.

### Task 11.3: Run it on four PCs

This needs the team at four machines; it can't be done by the agent alone.

- [ ] Walk the user through the runbook. After each PC is up, `check_stack.py --pc <PC>`.
- [ ] Seed from one PC: `seed/seed_network.py --directory-url https://<PC-A-ip>:8400`, then `seed/scenarios.py`, then `ml/generate_corpus.py --post`.
- [ ] `infra/scripts/collect_evidence.py` writes `docs/evidence/four_pcs/<timestamp>/`:
  - the directory listing;
  - every PC's host name;
  - a pairwise latency matrix;
  - S1–S9 results, with `served_by` host names and pass/fail against `expected.json`.
- [ ] **Verify:** in the evidence folder, at least one scenario's history shows 3 or more distinct host names, and `mode` is `network`. If the four-PC run can't be done (no admin rights, network isolation), write exactly that in `docs/evidence/four_pcs/NOT_RUN.md` with the reason, and stop.

---

## M12: Report and record

### Task 12.1: Architecture document

**Files:** `docs/architecture/ARCHITECTURE.md` and diagrams (Mermaid in Markdown).

Contents:
- the four PCs;
- inside a node;
- the bind-join trace sequence;
- the text pipeline;
- a mapping table from course concepts (wrappers, mediator, GAV, entity resolution, provenance) to files;
- how each professor requirement is met, with evidence links.

### Task 12.2: Final report

**Files:** `docs/REPORT.md`.

- [ ] Top section "Not done or partly done", listing everything incomplete, even if empty.
- [ ] Then: requirements → evidence; S1–S9 results from the evidence files, not retyped; ML metrics from `metrics.json`, not retyped. Generate the tables with `docs/scripts/build_report.py`.
- [ ] Run `/humanizer` on the prose parts.

### Task 12.3: Demo script

**Files:** `docs/DEMO.md`.

A 10-minute demo order, with what to click on which PC and what the audience should see:
1. Pharma dispatches.
2. The distributor receives, with one misread corrected.
3. The shop sells.
4. A consumer checks.
5. The copied-code scenario.
6. A text notice changes a verdict.
7. A node is turned off.
8. The Network page.

### Task 12.4: Vibe-coding record

- [ ] `docs/vibe/PROMPTS.md` has every prompt used.
- [ ] `docs/vibe/generated/` has the snapshots.
- [ ] `docs/vibe/CHANGES.md` has every post-run change.
- [ ] `docs/scripts/vibe_diffs.py` writes `docs/vibe/DIFFS.md`: every snapshotted file against its current version, as a unified diff.
- [ ] **Verify:** `uv run python docs/scripts/vibe_diffs.py` prints a count of files with and without changes.

---

## Self-review checklist (for the agent, before claiming a milestone is done)

- [ ] Every "Verify" in the milestone was run, and its output is in your report, copied, not paraphrased.
- [ ] `git status` shows only files under `asali-net/` changed (and the root `.gitignore` in M0).
- [ ] No file over 400 lines; no secret in `git diff --cached`.
- [ ] Snapshots exist for every new code file of the milestone.
- [ ] Anything not done is listed as not done.
