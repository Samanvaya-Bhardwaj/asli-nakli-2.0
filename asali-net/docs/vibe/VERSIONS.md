# Tool and library versions

Recorded when first installed (18 Nov 2026, PC-D, the 8 GB Windows PC). Exact pins are in the `pyproject.toml` files, `uv.lock`, `apps/portal-web/package.json` and `package-lock.json`.

## Tools

| Tool | Version | Note |
|---|---|---|
| Python | 3.11.9 | `py -3.11` |
| uv | 0.13.9 | Installed with `py -3.11 -m pip install --user uv`. Not on PATH in Git Bash, so run as `py -3.11 -m uv ...` |
| Node | 24.20.0 | |
| npm | 11.19.0 | |
| git | 2.55.0.windows.5 | |
| Docker Desktop | installed, **not running** | WSL2 is not installed on this PC. Needs `wsl --install --no-distribution` in an administrator terminal, then a restart. Until then, tests that need Postgres, Mongo or Meilisearch are skipped, and the skip reason says so. |
| mkcert | not installed | Not needed until M11 |
| Impeccable | engine 0.1.24 | Project scope, no hooks, telemetry off |

## Python (runtime)

| Package | Version |
|---|---|
| fastapi | 0.164.0 |
| uvicorn[standard] | 0.54.0 |
| pydantic | 2.14.3 |
| pydantic-settings | 2.16.3 |
| psycopg[binary,pool] | 3.3.9 |
| psycopg-pool | 3.3.3 |
| pymongo | 4.20.0 |
| httpx | 0.28.1 |
| cryptography | 50.0.2 |
| bcrypt | 5.0.0 |
| meilisearch | 0.43.0 |
| scikit-learn | 1.9.1 |
| scipy | 1.17.1 |
| numpy | 2.4.6 |
| joblib | 1.6.0 |
| rapidfuzz | 3.14.6 |

## Python (dev)

| Package | Version |
|---|---|
| pytest | 9.2.0 |
| hypothesis | 6.170.15 |
| ruff | 0.17.5 |
| mypy | 2.4.1 |

## Frontend (scaffolded by `create-vite`, react-ts template)

| Package | Version |
|---|---|
| react, react-dom | 19.3.1 |
| vite | 8.3.8 |
| @vitejs/plugin-react | 6.3.0 |
| typescript | 6.0.3 (the template installed 7.0.2; lowered because typescript-eslint supports < 6.1; see `CHANGES.md` D6) |
| eslint | 10.15.0 (replaces the template's oxlint, which Windows Smart App Control blocks on PC-D) |
| @eslint/js | 10.0.1 |
| typescript-eslint | 8.73.0 |
| eslint-plugin-react-hooks | 7.1.1 |
| eslint-plugin-react-refresh | 0.5.8 |
| globals | 17.14.0 |
| vitest | 5.1.1 |
| @types/react | 19.3.0 |
| @types/react-dom | 19.3.0 |
| @types/node | 24.19.2 |
