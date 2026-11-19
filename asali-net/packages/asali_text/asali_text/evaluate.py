"""Score the trained models on the held-out test families and the hand-written set (TEXT_ML.md section 9).

    python -m asali_text.evaluate --out docs/evidence/ml

Writes report.md and metrics.json. The targets are fixed in TARGETS and are not tuned on test data; a miss
is reported as a miss. The test split is read here and nowhere else.
"""

import argparse
import json
import random
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from asali_codes.confusion import weighted_distance
from sklearn.metrics import brier_score_loss, confusion_matrix, f1_score
from sklearn.metrics.pairwise import cosine_similarity

from asali_text import corpus
from asali_text.link import LINKED
from asali_text.mentions import extract
from asali_text.models import load_models

TARGETS = {
    "m1_macro_f1": 0.90, "m2_micro_f1": 0.80, "codes_precision": 0.98, "codes_recall": 0.95, "names_precision": 0.90,
    "names_recall": 0.85, "m3_precision": 0.95, "m3_recall": 0.85, "m4_f1": 0.85, "retrieval_recall_at_10": 0.90,
    "retrieval_unrelated_max": 1.0,
}  # fmt: skip
COMPLAINTS = {"consumer_complaint", "counter_note"}


def prf(tp: int, fp: int, fn: int) -> tuple[float, float]:
    return tp / max(1, tp + fp), tp / max(1, tp + fn)


def mention_scores(docs: list[dict[str, Any]], gaz: Any) -> dict[str, tuple[float, float]]:
    counts = {k: [0, 0, 0] for k in ("serial", "lot", "shipment_ref", "product", "org", "city")}
    for d in docs:
        found: dict[str, set[str]] = {k: set() for k in counts}
        for m in extract(d["text"], gaz, 2026):
            if m.kind in found:
                found[m.kind].add(
                    m.value["gtin"]
                    if m.kind == "product"
                    else m.value["org_id"]
                    if m.kind == "org"
                    else m.value.upper()
                    if m.kind == "shipment_ref"
                    else m.value
                )
        for k, c in counts.items():
            truth = {t.upper() if k == "shipment_ref" else t for t in d.get("true_mentions", {}).get(k, [])}
            if (
                k == "serial"
            ):  # a misread code is found as a different string: it counts when it is within correction range
                hit = {
                    t for t in truth if any(weighted_distance(t, f) <= 1.5 for f in found[k] if len(f) == 11)
                }
                tp, fp = (
                    len(hit),
                    len([f for f in found[k] if not any(weighted_distance(t, f) <= 1.5 for t in truth)]),
                )
            else:
                tp, fp = len(truth & found[k]), len(found[k] - truth)
            c[0] += tp
            c[1] += fp
            c[2] += len(truth) - tp
    return {k: prf(*v) for k, v in counts.items()}


def link_eval(docs: list[dict[str, Any]], world: Any, gaz: Any, models: Any) -> dict[str, Any]:
    x, y, owners = corpus.link_rows(docs, world, gaz)
    p = models.link.proba(x)
    sel = p >= LINKED
    tp = int(y[sel].sum())
    prec, rec = prf(tp, int(sel.sum()) - tp, int(y.sum()) - tp)
    # baseline: link only on an exact code match
    exact = x[:, 1] == 1
    btp = int(y[exact].sum())
    bprec, brec = prf(btp, int(exact.sum()) - btp, int(y.sum()) - btp)
    noisy_true = [i for i in range(len(y)) if y[i] and x[i, 1] == 0 and x[i, 11] + x[i, 12] + x[i, 13] > 0]
    return {"precision": prec, "recall": rec, "brier": float(brier_score_loss(y, p)) if len(y) else None,
            "baseline_precision": bprec, "baseline_recall": brec, "true_links": int(y.sum()), "candidates": len(y),
            "noisy_code_links": len(noisy_true), "found_noisy_by_m3": int(sum(p[i] >= LINKED for i in noisy_true)),
            "found_noisy_by_baseline": 0, "probs": p.tolist(), "labels": y.tolist()}  # fmt: skip


def reliability_png(p: list[float], y: list[int], path: Path) -> bool:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    bins = np.linspace(0, 1, 11)
    pa, ya = np.array(p), np.array(y)
    mid, obs = [], []
    for lo, hi in zip(bins, bins[1:], strict=False):
        sel = (pa >= lo) & (pa < hi if hi < 1 else pa <= hi)
        if sel.sum() >= 5:
            mid.append(float(pa[sel].mean()))
            obs.append(float(ya[sel].mean()))
    plt.figure(figsize=(4.5, 4.5))
    plt.plot([0, 1], [0, 1], "--", color="#888", label="perfect")
    plt.plot(mid, obs, "o-", color="#1f6f8b", label="M3 on the test families")
    plt.xlabel("predicted link probability")
    plt.ylabel("share that were true links")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=140)
    plt.close()
    return True


def duplicates_eval(
    docs: list[dict[str, Any]], val_docs: list[dict[str, Any]], models: Any
) -> dict[str, float]:
    vec = models.type.pipe.named_steps["vec"]

    def best_threshold_and_f1(ds: list[dict[str, Any]], threshold: float | None) -> tuple[float, float]:
        cs = [d for d in ds if d["doc_type"] == "consumer_complaint"]
        sims = cosine_similarity(vec.transform([d["text"] for d in cs]))
        truth = {
            (i, j)
            for i, d in enumerate(cs)
            if d["duplicate_of"]
            for j, e in enumerate(cs)
            if e["doc_id"] == d["duplicate_of"]
        }
        truth |= {(j, i) for i, j in truth}
        best = (0.9, 0.0)
        for t in [threshold] if threshold else np.arange(0.5, 0.99, 0.02):
            pred = {(i, j) for i in range(len(cs)) for j in range(len(cs)) if i != j and sims[i, j] >= t}
            tp = len(pred & truth)
            pr, rc = prf(tp, len(pred) - tp, len(truth) - tp)
            f = 2 * pr * rc / max(1e-9, pr + rc)
            if f > best[1]:
                best = (float(t), f)
        return best

    t, _ = best_threshold_and_f1(val_docs, None)
    _, f1 = best_threshold_and_f1(docs, t)
    return {"threshold_from_validation": round(t, 2), "f1": f1}


def retrieval_eval(docs: list[dict[str, Any]], world: Any, gaz: Any, models: Any) -> dict[str, float]:
    """Ingest the test documents into a fresh vault; ask for documents linked to a pack or batch; score the top 10."""
    from asali_node.vault.sqlite_vault import Vault

    from asali_text.pipeline import ingest

    with tempfile.TemporaryDirectory() as tmp:
        vault = Vault(Path(tmp))
        now = datetime(2026, 11, 20, tzinfo=UTC)
        for d in docs:
            r = ingest(
                d["text"],
                owner_org=d["owner_org"],
                declared_type=None,
                world=world,
                gaz=gaz,
                models=models,
                now=now,
                doc_id=d["doc_id"],
            )
            vault.put(
                r["doc"],
                [
                    {
                        "entity_key": link["entity_key"],
                        "entity_type": link["entity_type"],
                        "confidence": link["confidence"],
                    }
                    for link in r["links"]
                    if link["confidence"] >= 0.8
                ],
            )
        keys: dict[str, set[str]] = {}
        for d in docs:
            for k in corpus.implied(d["true_links"], world):
                if k.split(":")[0] in ("unit", "batch"):
                    keys.setdefault(k, set()).add(d["doc_id"])
        rng = random.Random(1)
        sample = rng.sample(sorted(keys), min(150, len(keys)))
        recalls, unrelated = [], []
        for k in sample:
            got = [h["id"] for h in vault.search(link_keys=[k], limit=10)]
            recalls.append(len(set(got) & keys[k]) / min(10, len(keys[k])))
            unrelated.append(len([g for g in got if g not in keys[k]]))
        vault.close()
    return {
        "recall_at_10": float(np.mean(recalls)),
        "unrelated_in_top_10": float(np.mean(unrelated)),
        "queries": len(sample),
    }


def handwritten(root: Path) -> str:
    labels = root / "labels.jsonl"
    return (
        f"{sum(1 for _ in labels.open(encoding='utf-8'))} documents"
        if labels.exists()
        else "not yet provided"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=Path("ml/data/generated"))
    ap.add_argument("--models", type=Path, default=Path("ml/models"))
    ap.add_argument("--handwritten", type=Path, default=Path("ml/data/handwritten"))
    ap.add_argument("--out", type=Path, default=Path("docs/evidence/ml"))
    args = ap.parse_args()
    docs = corpus.load_docs(args.corpus)
    world, models = corpus.load_world(args.corpus), load_models(args.models)
    gaz = corpus.gazetteer_from(world)
    test = [d for d in docs if d["split"] == "test"]
    val = [d for d in docs if d["split"] == "val"]
    m: dict[str, Any] = {}
    pred = models.type.predict_many([d["text"] for d in test])
    truth_t = [d["doc_type"] for d in test]
    m["m1_macro_f1"] = float(f1_score(truth_t, pred, average="macro"))
    classes = sorted(set(truth_t) | set(pred))
    cm = confusion_matrix(truth_t, pred, labels=classes)
    cp = [d for d in test if d["doc_type"] in COMPLAINTS]
    y = models.issue.mlb.transform([d["issue_labels"] for d in cp])
    ypred = models.issue.predict_matrix([d["text"] for d in cp])
    m["m2_micro_f1"] = float(f1_score(y, ypred, average="micro"))
    per_label = {
        lab: float(f1_score(y[:, j], ypred[:, j], zero_division=0))
        for j, lab in enumerate(models.issue.mlb.classes_)
    }
    ms = mention_scores(test, gaz)
    code, name = (
        [ms[k] for k in ("serial", "lot", "shipment_ref")],
        [ms[k] for k in ("product", "org", "city")],
    )
    m["codes_precision"], m["codes_recall"] = (
        float(np.mean([p for p, _ in code])),
        float(np.mean([r for _, r in code])),
    )
    m["names_precision"], m["names_recall"] = (
        float(np.mean([p for p, _ in name])),
        float(np.mean([r for _, r in name])),
    )
    le = link_eval(test, world, gaz, models)
    m["m3_precision"], m["m3_recall"] = le["precision"], le["recall"]
    dup = duplicates_eval(test, val, models)
    m["m4_f1"] = dup["f1"]
    ret = retrieval_eval(test, world, gaz, models)
    m["retrieval_recall_at_10"], m["retrieval_unrelated_max"] = (
        ret["recall_at_10"],
        ret["unrelated_in_top_10"],
    )
    args.out.mkdir(parents=True, exist_ok=True)
    chart = reliability_png(le.pop("probs"), le.pop("labels"), args.out / "m3_reliability.png")
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    miss = {k: (m[k], t) for k, t in TARGETS.items() if (m[k] > t if k.endswith("_max") else m[k] < t)}
    (args.out / "metrics.json").write_text(
        json.dumps(
            {
                "metrics": m,
                "targets": TARGETS,
                "missed": {k: list(v) for k, v in miss.items()},
                "m3": le,
                "mentions": {k: list(v) for k, v in ms.items()},
                "duplicates": dup,
                "retrieval": ret,
                "per_label_f1": per_label,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    lines = [
        f"Hand-written set: {handwritten(args.handwritten)}",
        "",
        f"Date {datetime.now(UTC):%Y-%m-%d}, commit {commit or 'unknown'}, data hash {models.meta.get('data_hash')}",
        f"Dataset: {len(docs)} documents; train {sum(d['split'] == 'train' for d in docs)}, validation {len(val)}, test {len(test)}. Test families are not in training.",
        "",
        "## Results on the generated test families",
        "",
        "| Component | Metric | Result | Target | |",
        "|---|---|---|---|---|",
    ]
    for k, t in TARGETS.items():
        ok = k not in miss
        lines.append(
            f"| {k.split('_')[0].upper()} | {k} | {m[k]:.3f} | {'<= ' if k.endswith('_max') else '>= '}{t} | {'met' if ok else 'MISSED'} |"
        )
    lines += ["", "## Missed targets", ""] + (
        [f"- {k}: {v[0]:.3f} against a target of {v[1]}" for k, v in miss.items()] or ["None."]
    )
    lines += [
        "",
        "## M3 against the baseline (exact code match only)",
        "",
        f"- M3 at 0.8: precision {le['precision']:.3f}, recall {le['recall']:.3f}",
        f"- Baseline: precision {le['baseline_precision']:.3f}, recall {le['baseline_recall']:.3f}",
        f"- Links reached through a misread code or a name only (the baseline cannot find these): {le['noisy_code_links']} in the test set, M3 found {le['found_noisy_by_m3']}.",
        f"- Brier score {le['brier']:.4f}. Reliability chart: {'m3_reliability.png' if chart else 'not drawn (matplotlib missing)'}",
        "",
        "## M1 confusion matrix (rows true, columns predicted)",
        "",
        "| |" + "|".join(classes) + "|",
        "|---|" + "---|" * len(classes),
    ]
    lines += [
        f"| {c} | " + " | ".join(str(int(v)) for v in row) + " |" for c, row in zip(classes, cm, strict=True)
    ]
    lines += ["", "## M2 F1 per label", ""] + [f"- {k}: {v:.3f}" for k, v in per_label.items()]
    lines += ["", "## Mentions (precision, recall)", ""] + [
        f"- {k}: {p:.3f}, {r:.3f}" for k, (p, r) in ms.items()
    ]
    lines += [
        "",
        "## M4 duplicates and retrieval",
        "",
        f"- M4 threshold {dup['threshold_from_validation']} (from validation), F1 {dup['f1']:.3f}.",
        f"- Retrieval over {ret['queries']} queries: recall@10 {ret['recall_at_10']:.3f}, unrelated documents in the top 10 {ret['unrelated_in_top_10']:.2f} on average.",
    ]
    (args.out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:22]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
