"""How well each way of matching a noisy code finds the real one (Phase 2: approximate matching, and why this algorithm).

A population of valid serials stands in for the issued packs. Each is damaged the ways scanners and people damage
codes, and five methods try to name the original, each adding one idea to the one before:

  exact                       the code as read must be issued
  levenshtein                 the nearest issued code, every edit costing 1
  weighted                    the nearest issued code, look-alike characters cheap (the Phase 2 shape prior)
  weighted_checksum           only codes that pass the check character, found by search rather than by scanning all
  weighted_checksum_context   and the lot printed on the label has to fit

Measured per method: top1 (the best-ranked code is the real one), top3, auto_accept (the rule the portals use
decides on its own: cost at most 1 and a margin of 0.5 to the next), and wrong_auto_accept (decided on its own
and wrong: the dangerous number, because a fake code must not be turned into a real one).

    python -m asali_codes.evaluate --out docs/evidence/matching
"""

import argparse
import json
import random
from pathlib import Path
from typing import Any

from rapidfuzz.distance import Levenshtein

from asali_codes.alphabet import ALPHABET
from asali_codes.candidates import Candidate, serial_candidates
from asali_codes.checks import luhn32_is_valid
from asali_codes.confusion import _COST, weighted_distance
from asali_codes.read import AUTO_MAX_COST, AUTO_MIN_MARGIN, _by_label

METHODS = ["exact", "levenshtein", "weighted", "weighted_checksum", "weighted_checksum_context"]
NOISE = [
    "lookalike1",
    "lookalike2",
    "swap",
    "drop",
    "double",
    "random1",
    "lookalike_swap",
    "lookalike_neighbours",
]
ISSUERS = ("TP", "MV", "KS")
LOTS = 60


def _check_char(body: str) -> str:
    for ch in ALPHABET:
        if luhn32_is_valid(body + ch):
            return ch
    raise AssertionError(body)


def make_population(n: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    out: set[str] = set()
    while len(out) < n:
        body = ISSUERS[len(out) % 3] + "".join(rng.choice(ALPHABET) for _ in range(8))
        out.add(body + _check_char(body))
    return sorted(out)


def _lookalike(ch: str, rng: random.Random) -> str | None:
    seen = [b for (a, b) in _COST if a == ch]
    return rng.choice(seen) if seen else None


def _sub_lookalike(s: str, rng: random.Random, k: int) -> str:
    spots = [i for i, c in enumerate(s) if i >= 2 and any(a == c for (a, _b) in _COST)]
    for i in rng.sample(spots, k):
        s = s[:i] + (_lookalike(s[i], rng) or s[i]) + s[i + 1 :]
    return s


def make_noisy(s: str, kind: str, rng: random.Random) -> str:
    for _ in range(50):
        if kind in ("lookalike1", "lookalike2", "lookalike_neighbours"):
            out = _sub_lookalike(s, rng, 2 if kind == "lookalike2" else 1)
        elif kind == "swap":
            i = rng.randrange(2, len(s) - 2)
            out = s[:i] + s[i + 1] + s[i] + s[i + 2 :]
        elif kind == "drop":
            i = rng.randrange(2, len(s))
            out = s[:i] + s[i + 1 :]
        elif kind == "double":
            i = rng.randrange(2, len(s))
            out = s[: i + 1] + s[i] + s[i + 1 :]
        elif kind == "random1":
            i = rng.randrange(2, len(s))
            out = s[:i] + rng.choice([c for c in ALPHABET if c != s[i]]) + s[i + 1 :]
        elif kind == "lookalike_swap":
            out = _sub_lookalike(s, rng, 1)
            i = rng.randrange(2, len(out) - 2)
            out = out[:i] + out[i + 1] + out[i] + out[i + 2 :]
        else:
            raise ValueError(kind)
        if out != s:
            return out
    raise RuntimeError(f"could not damage {s} with {kind}")


def _rank(
    method: str, noisy: str, pool: list[str], lot_of: dict[str, str], label_lot: str
) -> list[Candidate]:
    """Candidates, best first, for one method."""
    have = set(pool)
    if method == "exact":
        return [Candidate(noisy, 0.0)] if noisy in have else []
    if method in ("levenshtein", "weighted"):
        near = [(c, d) for c, d, _ in _nearest(noisy, pool)]
        if method == "levenshtein":
            return sorted((Candidate(c, float(d)) for c, d in near), key=lambda c: (c.cost, c.value))
        return sorted(
            (Candidate(c, weighted_distance(c, noisy)) for c, _ in near), key=lambda c: (c.cost, c.value)
        )
    found = [c for c in serial_candidates(noisy, set(ISSUERS)) if c.value in have]
    if method == "weighted_checksum_context" and len(found) > 1:
        facts = {c.value: (lot_of[c.value], None) for c in found}
        found = _by_label(found, lambda ss: {s: facts[s] for s in ss}, label_lot, None)
    return found


def _nearest(noisy: str, pool: list[str]) -> list[tuple[str, int, int]]:
    from rapidfuzz import process

    return [
        (c, int(d), i)
        for c, d, i in process.extract(noisy, pool, scorer=Levenshtein.distance, limit=25, score_cutoff=3)
    ]


def _decides(ranked: list[Candidate], unit: bool = False) -> bool:
    """The portals' rule: one clear best candidate. `unit` for plain edit counts, where a margin below 1 is a tie."""
    if not ranked:
        return False
    margin = 1.0 if unit else AUTO_MIN_MARGIN
    return ranked[0].cost <= AUTO_MAX_COST and (len(ranked) == 1 or ranked[1].cost - ranked[0].cost >= margin)


def evaluate(
    population: int = 3000, per_condition: int = 150, seed: int = 7, kinds: list[str] | None = None
) -> dict[str, Any]:
    kinds = kinds or NOISE
    pool = make_population(population, seed)
    rng = random.Random(seed + 1)
    lot_of = {s: f"L{rng.randrange(LOTS)}" for s in pool}
    rows: dict[str, dict[str, dict[str, int]]] = {
        k: {m: dict.fromkeys(("n", "top1", "top3", "auto", "wrong_auto"), 0) for m in METHODS} for k in kinds
    }
    for kind in kinds:
        for truth in rng.sample(pool, per_condition):
            noisy = make_noisy(truth, kind, rng)
            here, lots = pool, lot_of
            if kind == "lookalike_neighbours":
                # The hard case: other issued codes that look just as much like the reading, with other lots.
                twins = [
                    c.value
                    for c in serial_candidates(noisy, set(ISSUERS), max_cost=2.0)
                    if c.value not in lot_of
                ][:3]
                here = [*pool, *twins]
                lots = {**lot_of, **{x: f"L{LOTS + i}" for i, x in enumerate(twins)}}
            for m in METHODS:
                ranked = _rank(m, noisy, here, lots, lot_of[truth])
                r = rows[kind][m]
                r["n"] += 1
                r["top1"] += bool(ranked) and ranked[0].value == truth
                r["top3"] += truth in [c.value for c in ranked[:3]]
                auto = _decides(ranked, unit=m == "levenshtein")
                r["auto"] += auto
                r["wrong_auto"] += auto and ranked[0].value != truth

    def pct(a: int, n: int) -> float:
        return round(a / n, 4) if n else 0.0

    def summarise(subset: list[dict[str, int]]) -> dict[str, float]:
        n = sum(x["n"] for x in subset)
        return {"top1": pct(sum(x["top1"] for x in subset), n), "top3": pct(sum(x["top3"] for x in subset), n),
                "auto_accept": pct(sum(x["auto"] for x in subset), n),
                "wrong_auto_accept": pct(sum(x["wrong_auto"] for x in subset), n)}  # fmt: skip

    return {
        "population": population,
        "per_condition": per_condition,
        "seed": seed,
        "noise": kinds,
        "methods": METHODS,
        "overall": {m: summarise([rows[k][m] for k in kinds]) for m in METHODS},
        "by_noise": {k: {m: summarise([rows[k][m]]) for m in METHODS} for k in kinds},
        "label": "Generated codes and generated damage: shows how the methods rank against each other, not how many real scans will be right.",
    }


def report(res: dict[str, Any]) -> str:
    lines = ["# Matching a noisy code: accuracy by method", "", res["label"], "",
             f"{res['population']} issued codes, {res['per_condition']} damaged codes per kind of damage, seed {res['seed']}.", "",
             "## Overall", "", "| Method | top 1 | top 3 | decides alone | wrong and decided alone |", "|---|---|---|---|---|"]  # fmt: skip
    for m in res["methods"]:
        o = res["overall"][m]
        lines.append(
            f"| {m} | {o['top1']:.1%} | {o['top3']:.1%} | {o['auto_accept']:.1%} | {o['wrong_auto_accept']:.1%} |"
        )
    lines += [
        "",
        "## By kind of damage (top 1)",
        "",
        "| Damage | " + " | ".join(res["methods"]) + " |",
        "|---|" + "---|" * len(res["methods"]),
    ]
    for k in res["noise"]:
        lines.append(
            f"| {k} | " + " | ".join(f"{res['by_noise'][k][m]['top1']:.1%}" for m in res["methods"]) + " |"
        )
    lines += ["", "## What the numbers say", "",
              "- Exact matching fails on every damaged code by construction.",
              "- With serials this long and this sparse, the nearest issued code is almost always the real one, so every distance method ranks it first. Top 1 does not tell them apart.",
              "- What differs is how often the method can decide on its own with a clear margin, and so how often a person is asked. Weighting look-alikes (0 and O, 5 and S, 1 and I) and using the check character raise that share a lot over plain edit distance, which ties on many readings.",
              "- No method decided alone and was wrong in the main conditions: the margin rule is what keeps a fake code from being turned into a real one.",
              "- The check character is searched, not scanned for: for any one position exactly one character makes a code valid, so the candidate set is small and exact instead of a ranked list of every issued code.",
              "- The last damage kind adds issued codes that look just as much like the reading. Characters cannot separate them; the lot printed beside the code can. The context method uses it only when it rules some out.",
              "- A consumer still confirms any correction against the pack."]  # fmt: skip
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--population", type=int, default=3000)
    ap.add_argument("--per-condition", type=int, default=150)
    args = ap.parse_args()
    res = evaluate(args.population, args.per_condition)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "metrics.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (args.out / "report.md").write_text(report(res), encoding="utf-8")
    print(report(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
