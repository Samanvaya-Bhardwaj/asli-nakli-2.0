"""Generate the text corpus from the seeded network (TEXT_ML.md section 10).

    python ml/generate_corpus.py --seed 42 --out ml/data/generated

Reads the real packs, batches and shipments of the running simulation through the portals' own APIs, writes
documents that refer to them, and keeps an answer key (truth.jsonl): the true links, claims and labels.
Families (sentence structures) are split 4 train / 1 validation / 1 test, so the test text has phrasing the
models never saw. Same seed, same corpus.
"""

import argparse
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "seed"))
sys.path.insert(0, str(ROOT / "infra" / "scripts"))
sys.path.insert(0, str(ROOT / "packages" / "asali_text"))
import templates as T  # noqa: E402
from asali_text.claims import KIND  # noqa: E402
from asali_text.world import World  # noqa: E402

COUNTS = {"coa": 120, "batch_release_note": 60, "deviation_report": 40, "recall_notice": 15, "temperature_report": 120,
          "delivery_note": 80, "discrepancy_note": 40, "damage_report": 30, "counter_note": 80, "return_note": 40,
          "consumer_complaint": 400, "nsq_alert": 24, "ban_order": 6, "inspection_report": 40}  # fmt: skip
from corpus_gen import Gen  # noqa: E402
from corpus_world import (  # noqa: E402
    REC,
    build_world,
    complete_mentions,
    keep_printed,
    write_all,
)


def generate(world: World, state: dict[str, Any], seed: int, scale: float) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    g = Gen(world, state, rng)
    docs: list[dict[str, Any]] = []
    for doc_type, count in COUNTS.items():
        n = max(2, round(count * scale))
        for i in range(n):
            fam = i % T.FAMILIES
            REC.clear()
            text, truth = g.make(doc_type, fam)  # type: ignore[misc]
            mentions = {k: sorted(v) for k, v in REC.items()}
            split = "train" if fam in T.TRAIN else "val" if fam in T.VAL else "test"
            doc = {
                "doc_id": g.next_id(doc_type),
                "owner_org": truth.pop("owner"),
                "doc_type": doc_type,
                "kind": KIND[doc_type],
                "family_id": f"{doc_type}:{fam}",
                "split": split,
                "text": text,
                "issue_labels": truth.pop("labels", []),
                "true_links": sorted(set(truth.pop("links"))),
                "true_claims": truth.pop("claims"),
                "duplicate_of": None,
                "language": truth.pop("language", "en"),
                "true_mentions": mentions,
            }
            complete_mentions(doc, world)
            keep_printed(doc, world)
            docs.append(doc)
            if (
                doc_type == "consumer_complaint" and rng.random() < 0.05
            ):  # a near copy for the duplicate model
                words = text.split(" ")
                words[rng.randrange(len(words))] = rng.choice(["really", "again", "also"])
                docs.append(
                    {
                        **doc,
                        "doc_id": g.next_id(doc_type),
                        "text": " ".join(words),
                        "duplicate_of": doc["doc_id"],
                    }
                )
    return docs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=ROOT / "ml" / "data" / "generated")
    ap.add_argument("--sample", type=int, default=700, help="packs to put in the world")
    ap.add_argument("--scale", type=float, default=1.0)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    world, state = build_world(args.sample, rng)
    docs = generate(world, state, args.seed, args.scale)
    args.out.mkdir(parents=True, exist_ok=True)
    write_all(docs, world, args.out)
    counts: dict[tuple[str, str], int] = {}
    for d in docs:
        counts[(d["doc_type"], d["split"])] = counts.get((d["doc_type"], d["split"]), 0) + 1
    for t in COUNTS:
        print(f"{t:20} " + "  ".join(f"{s} {counts.get((t, s), 0):4}" for s in ("train", "val", "test")))
    print(
        f"total {len(docs)} documents; world: {len(world.units)} packs, {len(world.batches)} batches, {len(world.shipments)} shipments"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
