"""Phase 3 on the running simulation: the context each organisation finds, and what it does to the text search.

    python infra/scripts/context_demo.py

For the scenario packs and a sample of sold packs, checks each one through a consumer portal and records which
organisations were asked, which tables each explored through which keys, the strongest merged terms, and the
documents the context found. As a comparison it also searches the same vaults with only the words of the question
(no context) and reports how many of the documents each way returned even name the pack's product. Simulation on
one computer; the corpus is generated, so the comparison shows the method, not real-world retrieval quality.
"""

import json
import random
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import httpx

ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT / "infra" / "out" / "SIM"
sys.path.insert(0, str(ROOT / "services" / "node"))
from asali_node.verify.context import INTENT_WORDS

VAULTS = [
    "tarang",
    "medivra",
    "kesar",
    "dist-north",
    "dist-west",
    "dist-south",
    "shop-delhi",
    "shop-mumbai",
    "shop-bengaluru",
    "regulator",
    "consumer-delhi",
    "consumer-mumbai",
]
SAMPLE = 25


def element(g: str, s: str) -> str:
    return f"(01){g}(21){s}"


def names_product(text: str, brand: str, generic: str) -> bool:
    t = text.lower()
    return brand.lower() in t or generic.lower() in t


def question_only(regulator: httpx.Client, brand_terms: tuple[str, str]) -> list[str]:
    """Documents the question's own words find: at least two of them, newest first, five at most (the same rule as the context search)."""
    q = " ".join(INTENT_WORDS[:12])
    found: list[tuple[int, int, str]] = []
    for org in VAULTS:
        r = regulator.get(
            "/api/debug/ask", params={"org": org, "path": f"/share/v1/documents/search?q={quote(q)}&limit=40"}
        )
        if r.status_code != 200:
            continue
        for h in r.json().get("hits", []):
            text = f"{h.get('title', '')} {h['body']}".lower()
            n = sum(1 for w in INTENT_WORDS if re.search(r"\b" + re.escape(w), text))
            if n >= 2:
                found.append((n, h["created_at"], h["body"]))
    found.sort(key=lambda x: (-x[0], -x[1]))
    return [b for _, _, b in found[:5]]


def main() -> int:
    password = json.loads((SIM / "secrets.json").read_text())["staff_password"]
    scenarios = json.loads((SIM / "scenarios.json").read_text())
    state = json.loads((SIM / "seed_state.json").read_text())
    consumer = httpx.Client(base_url="http://127.0.0.1:8402", timeout=300)
    regulator = httpx.Client(base_url="http://127.0.0.1:8401", timeout=300)
    assert regulator.post("/api/login", json={"username": "staff", "password": password}).status_code == 200
    rng = random.Random(5)
    sold = [c for b in state["bills"] for c in b["codes"]]
    packs = {name: s["raw"] for name, s in scenarios.items() if name in ("S1", "S3", "S5", "S6", "S7")}
    for i, (g, s) in enumerate(rng.sample(sold, SAMPLE)):
        packs[f"sample-{i + 1:02d}"] = element(g, s)
    rows: list[dict] = []
    for name, raw in packs.items():
        r = consumer.post("/api/check", json={"raw": raw, "city": "Delhi"}).json()
        if r["status"] != "done":
            continue
        res = r["result"]
        ctx = res["context"]
        p = res["pack"]["product"] or {"brand": "", "generic": ""}
        by_ctx = [d["snippet"]["text"] for d in res["context_documents"]]
        rows.append({
            "pack": name, "verdict": res["verdict"], "product": f"{p['brand']} ({p['generic']})",
            "asked": len(ctx["organisations_asked"]), "contributing": len(ctx["organisations_contributing"]),
            "engines": sorted({o["engine"] for o in ctx["organisations"] if o["engine"]}),
            "tables_explored": {o["org_id"]: o["explored_tables"] for o in ctx["organisations"] if o["status"] == "answered"},
            "joins": {o["org_id"]: o["joins"] for o in ctx["organisations"] if o["joins"]},
            "terms": [{"term": t["term"], "score": t["score"], "orgs": t["organisations"], "why": t["why_relevant"]} for t in ctx["terms"][:6]],
            "context_docs": len(by_ctx),
            "context_docs_naming_product": sum(names_product(t, p["brand"], p["generic"]) for t in by_ctx) if p["brand"] else None,
            "linked_docs": len(res["documents"]),
            "question_only_docs": ((qo := question_only(regulator, (p["brand"], p["generic"]))) and len(qo)) or 0,
            "question_only_naming_product": sum(names_product(t, p["brand"], p["generic"]) for t in qo) if p["brand"] else None,
        })  # fmt: skip

    def share(key_n: str, key_d: str) -> float | None:
        n = sum(r[key_n] or 0 for r in rows)
        d = sum(r[key_d] for r in rows)
        return round(n / d, 3) if d else None

    summary = {
        "packs": len(rows),
        "mean_organisations_contributing": round(sum(r["contributing"] for r in rows) / len(rows), 2),
        "mean_joins_followed": round(sum(sum(len(j) for j in r["joins"].values()) for r in rows) / len(rows), 2),
        "engines_seen": sorted({e for r in rows for e in r["engines"]}),
        "context_docs_naming_product": share("context_docs_naming_product", "context_docs"),
        "question_only_docs_naming_product": share("question_only_naming_product", "question_only_docs"),
        "context_docs_per_pack": round(sum(r["context_docs"] for r in rows) / len(rows), 2),
        "question_only_docs_per_pack": round(sum(r["question_only_docs"] for r in rows) / len(rows), 2),
    }  # fmt: skip
    out = ROOT / "docs" / "evidence" / "context"
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(
        json.dumps(
            {
                "run_at": datetime.now().isoformat(timespec="seconds"),
                "mode": "simulation on one computer",
                "summary": summary,
                "packs": rows,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    lines = ["# Context discovered across organisations", "", f"Run {datetime.now():%Y-%m-%d %H:%M}. Simulation on one computer; generated corpus.", "",
             f"{summary['packs']} packs checked. On average {summary['mean_organisations_contributing']} organisations found context and {summary['mean_joins_followed']} foreign-key joins were followed per pack, over {', '.join(summary['engines_seen'])}.", "",  # fmt: skip
             "## Does the context find documents about the pack's product?", "",
             f"- Documents found by the context: {summary['context_docs_per_pack']} per pack, {summary['context_docs_naming_product']} of them name the pack's product or its generic name.",
             f"- Documents found by the question's words alone: {summary['question_only_docs_per_pack']} per pack, {summary['question_only_docs_naming_product']} of them name the product.", "",  # fmt: skip
             "The comparison is on generated documents and generated packs. It shows what the context adds, not how real documents would behave.", "", "## Scenario packs", ""]  # fmt: skip
    for r in rows:
        if r["pack"].startswith("S"):
            lines += [
                f"### {r['pack']}: {r['verdict']}, {r['product']}",
                "",
                f"{r['contributing']} of {r['asked']} organisations found context.",
                "",
            ]
            for org, tables in r["tables_explored"].items():
                lines.append(
                    f"- {org}: explored {', '.join(tables) or 'nothing'}"
                    + (f"; followed {'; '.join(r['joins'].get(org, []))}" if r["joins"].get(org) else "")
                )
            lines += [
                "",
                "Strongest terms: "
                + "; ".join(f"{t['term']} ({', '.join(t['orgs'])})" for t in r["terms"][:5]),
                "",
            ]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:14]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
