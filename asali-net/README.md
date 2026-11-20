# Asali Network

Medicine verification across 12 organisations (3 pharmaceutical companies, 3 distributors, 3 shops, 2 consumer portals, 1 regulator), each with its own database and its own text store, shared read-only over a signed HTTP API. One portal codebase serves all five roles.

**Status:** runs as a one-computer simulation. The four-computer run is not done. See `docs/REPORT.md`, "Not done", for the full list.

- `docs/plan/` the plan, text/ML design, UI design, task list
- `docs/REPORT.md` what is done, what is not, and the check results
- `docs/runbook/FOUR_PCS.md` how to run it on four computers
- `docs/DEMO.md` the demo script
- `docs/vibe/` prompts, changes against the plan, and snapshots of generated code

Run the simulation: `infra/scripts/sim_rebuild.sh` (needs PostgreSQL and MongoDB installed locally; see `RUNNING` notes in the runbook). Tests: `python docs/scripts/run_checks.py`.
