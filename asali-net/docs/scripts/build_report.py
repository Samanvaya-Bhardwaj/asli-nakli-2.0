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


def rubric_section(ev: Path) -> list[str]:
    """The three phases' marking rubrics, one line each, with what shows it and its numbers where there are any."""
    matching = load(ev / "matching" / "metrics.json")
    quality = load(ev / "quality" / "results.json")
    context = load(ev / "context" / "results.json")
    m_line = "run `python -m asali_codes.evaluate` (not run yet)"
    if matching:
        o = matching["overall"]
        m_line = (
            f"`docs/evidence/matching/report.md`: top 1 {o['levenshtein']['top1']:.1%} (plain edit distance) to {o['weighted_checksum_context']['top1']:.1%} "
            f"(weighted, check character, lot); decides alone {o['levenshtein']['auto_accept']:.1%} to {o['weighted_checksum_context']['auto_accept']:.1%}; "
            f"wrong and decided alone {o['weighted_checksum_context']['wrong_auto_accept']:.1%}"
        )
    q_line = "run `python infra/scripts/quality_demo.py` (not run yet)"
    if quality:
        s = quality["summary"]
        q_line = f"`docs/evidence/quality/report.md`: {s['planted']} planted, {s['found']} found, {s['proposed_correctly']} right proposals, {s['applied']} applied"
    c_line = "run `python infra/scripts/context_demo.py` (not run yet)"
    if context:
        s = context["summary"]
        c_line = (
            f"`docs/evidence/context/report.md`: {s['packs']} packs, {s['mean_organisations_contributing']} organisations found context per pack, "
            f"{s['mean_joins_followed']} joins followed per pack over {', '.join(s['engines_seen'])}; documents naming the pack's product: "
            f"{s['context_docs_naming_product']} by context, {s['question_only_docs_naming_product']} by the question's words alone"
        )
    return [
        "## The three phases' rubrics",
        "",
        "One project in three phases. Each line is a marking item, what answers it, and where.",
        "",
        "### Phase 1",
        "",
        "| Rubric item | Marks | Where |",
        "|---|---|---|",
        "| Scope of work | 1 | `docs/plan/PLAN.md` section 1 |",
        "| What is new | 1 | Per-organisation databases in three engines with different schemas; read-only sharing; text linked by ML to structured records; misread-code correction (`docs/vibe/CHANGES.md`) |",
        "| Database schema design | 2 | `schemas/<org>/schema.sql` and `validators.json`, each with a `MAPPING.md` |",
        "| Populating the tables | 2 | `seed/seed_network.py` through the portals' own APIs; `seed/catalogue.yaml` |",
        "| Schema matching / mapping, or APIs for fetching | 2 | Each store maps its native schema to the canonical model (`MAPPING.md`); the share API (`services/node/asali_node/share/`) is the fetching API |",
        "| Query decomposition and federation, or querying through APIs | 2 | `verify/trace.py`: a dependent join along the custody chain, side queries in parallel |",
        "| Communication between the sources | 2 | Signed HTTP between nodes, a directory of addresses and keys (`network/`, `auth/`); `tests/network/` |",
        "| Result integration and a simple GUI | 3 | Result page of the portal: verdict, reasons, history, documents, context (`apps/portal-web/`) |",
        "",
        "### Phase 2",
        "",
        "| Rubric item | Marks | Where |",
        "|---|---|---|",
        f"| Approximate matching of a noisy code, and the reverse; why this algorithm | 5 | `packages/asali_codes` (weighted edit search, check character, issued set); `POST /api/similar` and the Investigate page; {m_line} |",
        f"| Cleansing recorded data with the other information on the label, so no anomalies remain | 5 | Label lot and expiry separate candidates (`asali_codes/read.py`); `/api/quality` audit, proposals and applied fixes with a trail; {q_line} |",
        "| Prompt, generated code, and the changes | 5 | `docs/vibe/PROMPTS.md`, `docs/vibe/generated/`, `docs/vibe/CHANGES.md`, `docs/scripts/vibe_diffs.py` |",
        "",
        "### Phase 3",
        "",
        "| Rubric item | Marks | Where |",
        "|---|---|---|",
        "| Each database has four to five related tables, some joined by foreign keys | 2 | `services/node/tests/stores/test_phase3_shape.py` checks all twelve; `MAPPING.md` lists the related tables of each |",
        f"| Context found through the keys, in each database on its own machine, accumulated and related to the query | 3 | `asali_node/context/` (per database), `share/context.py`, `verify/context.py` (merge); {c_line}. **Each database ran as its own process on one computer; not on different machines** |",
        "| The context searches the unstructured data, and the two are integrated | 3 | `verify/context.py` `context_documents`; the result page shows linked documents, context, and related documents apart; related documents never change a verdict |",
        "| Prompt, generated code, modified code | 2 | As Phase 2 |",
        "",
    ]


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
        "**Superpowers and Humanizer plugins were not installed** (they need the user's `/plugin` commands), so no humanizer pass was made on the prose. Impeccable's detector is at zero findings; its audit and critique were done as a pass by Claude, not by a second person (`docs/evidence/ui/impeccable-review.md`).",
        "**The seed and scenario scripts address nodes through the directory** (`--directory-url`, `--ca`), but have only been run against the local directory, never against four computers.",
        "**The Phase 1 to 3 code at the repository root is not connected to this system.** It still runs on its own (`scripts/run_federation.py`) and was not changed. This network re-implements what the three phases asked for: Phase 3's context discovery was ported into the nodes (`asali_node/context/`); Phase 1's integration is the per-organisation mapping to a canonical model; Phase 2's matching is `packages/asali_codes`. Phase 2's probabilistic entity-matching posterior, Phase 1's hash-chained audit log and Phase 2's replication were not carried over.",
        "**Phase 3 \"databases on different machines\" is only simulated:** each database and its node ran as its own process on one computer. The context discovery has never run across machines.",
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

    lines += rubric_section(EV)
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
