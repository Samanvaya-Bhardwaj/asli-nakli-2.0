"""Train the models from the generated corpus.

    python -m asali_text.train --models m1,m2,m3 --corpus ml/data/generated --out ml/models

Only the validation split is scored here. The test split is touched by evaluate.py alone.
"""

import argparse
from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score

from asali_text import corpus
from asali_text.classify_issue import IssueModel
from asali_text.classify_type import TypeModel
from asali_text.models import Models, load_models, save_models
from asali_text.ranker import LinkModel

COMPLAINTS = {"consumer_complaint", "counter_note"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="m1,m2,m3")
    ap.add_argument("--corpus", type=Path, default=Path("ml/data/generated"))
    ap.add_argument("--out", type=Path, default=Path("ml/models"))
    args = ap.parse_args()
    wanted = set(args.models.split(","))
    docs = corpus.load_docs(args.corpus)
    world = corpus.load_world(args.corpus)
    gaz = corpus.gazetteer_from(world)
    by = {s: [d for d in docs if d["split"] == s] for s in ("train", "val", "test")}
    print(f"train {len(by['train'])}  validation {len(by['val'])} documents (test split not used here)")
    existing = (
        load_models(args.out) if (args.out / "meta.json").exists() and wanted != {"m1", "m2", "m3"} else None
    )
    type_m = existing.type if existing and "m1" not in wanted else TypeModel()
    issue_m = existing.issue if existing and "m2" not in wanted else IssueModel()
    link_m = existing.link if existing and "m3" not in wanted else LinkModel()
    meta: dict[str, object] = {}
    if "m1" in wanted:
        type_m.fit([d["text"] for d in by["train"]], [d["doc_type"] for d in by["train"]])
        pred = type_m.predict_many([d["text"] for d in by["val"]])
        meta["m1_val_macro_f1"] = round(
            float(f1_score([d["doc_type"] for d in by["val"]], pred, average="macro")), 4
        )
        print("M1 type: validation macro-F1", meta["m1_val_macro_f1"])
    if "m2" in wanted:
        tr = [d for d in by["train"] if d["doc_type"] in COMPLAINTS]
        va = [d for d in by["val"] if d["doc_type"] in COMPLAINTS]
        issue_m.fit(
            [d["text"] for d in tr],
            [d["issue_labels"] for d in tr],
            [d["text"] for d in va],
            [d["issue_labels"] for d in va],
        )
        y = issue_m.mlb.transform([d["issue_labels"] for d in va])
        meta["m2_val_micro_f1"] = round(
            float(f1_score(y, issue_m.predict_matrix([d["text"] for d in va]), average="micro")), 4
        )
        print("M2 issues: validation micro-F1", meta["m2_val_micro_f1"])
    if "m3" in wanted:
        x, y3, _ = corpus.link_rows(by["train"], world, gaz)
        vx, vy, _ = corpus.link_rows(by["val"], world, gaz)
        link_m.fit(x, y3, vx, vy)
        p = link_m.proba(vx)
        sel = p >= 0.8
        prec = float(vy[sel].mean()) if sel.any() else 0.0
        rec = float(vy[sel].sum() / max(1, vy.sum()))
        meta["m3_val_precision_at_08"], meta["m3_val_recall_at_08"] = round(prec, 4), round(rec, 4)
        print(
            f"M3 links: validation precision {prec:.3f}, recall {rec:.3f} at 0.8 ({int(vy.sum())} true links, {len(vy)} candidates)"
        )
    save_models(Models(type_m, issue_m, link_m, meta), args.out, corpus.data_hash(docs), meta)
    print("saved", args.out, "size", sum(f.stat().st_size for f in args.out.glob("*.joblib")) // 1024, "KB")
    _ = np
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
