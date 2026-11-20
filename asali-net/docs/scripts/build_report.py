"""Build docs/REPORT.md from the evidence files. Numbers and results are read, never retyped.

    python docs/scripts/build_report.py

Reads: docs/evidence/checks.json, docs/evidence/simulation/results.json, docs/evidence/ml/metrics.json,
docs/evidence/ui/e2e-results.json (if present), docs/evidence/four_pcs/ (if present).
"""

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / "docs" / "evidence"


def load(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def main() -> int:
    checks, scen = load(EV / "checks.json"), load(EV / "simulation" / "results.json")
    ml, e2e = load(EV / "ml" / "metrics.json"), load(EV / "ui" / "e2e-results.json")
    four = sorted((EV / "four_pcs").glob("*/SUMMARY.md")) if (EV / "four_pcs").exists() else []

    not_done = [
        "**The four-computer run has not been done.** Everything ran as one-computer simulation (local processes on real PostgreSQL, MongoDB and SQLite). "
        + (
            "Evidence folders from a multi-computer run exist: "
            + ", ".join(p.parent.name for p in four)
            + "."
            if four
            else "There is no evidence folder from a multi-computer run."
        ),
        "**Docker was never run.** The development PC has no WSL2. The generated compose files are tested as data (`infra/tests/test_make_stack.py`) and have not been started.",
        "**The text vault is SQLite full-text search, not Meilisearch.** Meilisearch's binary is blocked by Windows Smart App Control on the development PC.",
        "**The hand-written ML test set has not been provided** by the team. The ML report says so in its first line.",
        "**Superpowers and Humanizer plugins were not installed** (they need the user's `/plugin` commands). Impeccable's detector was run and is at zero findings; its critique, audit and polish commands were not run as skills, and no humanizer pass was made on the prose.",
        '**Not written:** generated API types (task 4.8; the types are written by hand), the dark-mode switch (the portal follows the system setting), a "More" menu on the phone bottom bar, and addressing other computers from the seed scripts.',
        "**Hindi, Marathi and Kannada receipt text is unreviewed** and marked so in the files and on screen.",
    ]
    if ml and ml["missed"]:
        for k, (got, want) in ml["missed"].items():
            not_done.append(
                f"**ML target missed:** {k} is {got:.3f} against a target of {want} on the generated test families. Thresholds were not tuned on test data."
            )
    if checks:
        for r in checks["results"]:
            if not r["passed"]:
                not_done.append(
                    f"**Check failing:** {r['check']}. Last output: {' | '.join(r['tail'])[:200]}"
                )
    if scen:
        for name, r in scen["results"].items():
            if not r["passed"]:
                not_done.append(f"**Scenario {name} did not give the expected result.**")

    lines = [
        "# Asali Network: report",
        "",
        f"Built {datetime.now():%d %b %Y} from the files in `docs/evidence/`.",
        "",
        "## Not done or partly done",
        "",
    ]
    lines += [f"- {x}" for x in not_done] + [""]

    lines += [
        "## What the professor asked for, and where it is",
        "",
        "| Request | Where it is shown |",
        "|---|---|",
        "| Each company, distributor and shop has its own database with a different structure | 12 stores in `services/node/asali_node/stores/`, schemas and mappings in `schemas/<org>/`; three engines; contract tests in `services/node/tests/stores/` |",
        "| Databases are shared read-only | Three layers (HTTP, database account, scope); `test_readonly.py` shows PostgreSQL, MongoDB and SQLite refusing writes |",
        "| Portals for pharma, distributor, shop, consumer and regulator from one UI | `apps/portal-web/`, one codebase, routes built from `/api/config` |",
        "| Distributor scans packs in and records where they go; shops scan in and sell | Scan sessions (`scan_sessions.py`, `portal/scan.py`), browser flow in `apps/portal-web/e2e/custody.spec.ts` |",
        "| Fix wrongly scanned characters | `packages/asali_codes` (Python and TypeScript), staff auto-correct against the expected set, consumers always confirm |",
        "| Unstructured data is text, with ML, linked to structured data to verify | `packages/asali_text`, vaults, `verify/documents.py`; scenarios S3, S5 and S6 use it |",
        "| Real orchestration across computers | `infra/network.yaml`, `make_stack.py`, runbook `docs/runbook/FOUR_PCS.md`; **run only as a one-computer simulation so far** |",
        "| The old UI looked machine-made | Tokens, banned patterns, `check_copy.mjs`, Impeccable detector at zero; see `docs/plan/DESIGN.md` |",
        "",
    ]

    if checks:
        lines += [
            "## Automated checks",
            "",
            f"Run {checks['run_at']}.",
            "",
            "| Check | Result |",
            "|---|---|",
        ]
        lines += [
            f"| {r['check']} | {'passed' if r['passed'] else 'FAILED'} |" for r in checks["results"]
        ] + [""]
    if scen:
        lines += [
            "## Scenarios (simulation on one computer)",
            "",
            f"Run {scen['run_at']}.",
            "",
            "| Scenario | Verdict | Reasons | Expected | Computers named | Result |",
            "|---|---|---|---|---|---|",
        ]
        for name, r in scen["results"].items():
            if "verdict" in r:
                lines.append(
                    f"| {name} | {r['verdict']} | {', '.join(r['reasons']) or 'none'} | {r['expected']['verdict']} {', '.join(r['expected']['reasons'])} | {', '.join(r['computers'])} | {'pass' if r['passed'] else 'FAIL'} |"
                )
            else:
                lines.append(
                    f"| {name} | {r['status']} | | {r['expected']} | | {'pass' if r['passed'] else 'FAIL'} |"
                )
        lines += [
            "",
            "Scenario S8 (a stopped organisation) is run by `tests/network/test_scenarios.py` because it stops and starts a node.",
            "",
        ]
    if ml:
        m = ml["metrics"]
        lines += [
            "## Text and ML",
            "",
            "Measured on template families the models never saw (`docs/evidence/ml/report.md` has the confusion matrices, the reliability chart and the baseline comparison).",
            "",
            "| Metric | Result | Target |",
            "|---|---|---|",
        ]
        lines += [
            f"| {k} | {m[k]:.3f} | {'at most ' if k.endswith('_max') else 'at least '}{t} |"
            for k, t in ml["targets"].items()
        ] + [""]
    if e2e:
        lines += [
            "## Browser tests",
            "",
            f"{e2e.get('passed', 0)} passed, {e2e.get('failed', 0)} failed. Screenshots in `docs/evidence/ui/e2e/`.",
            "",
        ]
    lines += [
        "## Deviations from the plan",
        "",
        "Every deviation, with its reason, is in `docs/vibe/CHANGES.md`.",
        "",
    ]
    (ROOT / "docs" / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote docs/REPORT.md ({len(not_done)} items under 'Not done')")
    return 0


if __name__ == "__main__":
    sys.exit(main())
