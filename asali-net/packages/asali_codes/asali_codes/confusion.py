"""Costs of misreading one character as another, and a weighted edit distance built on them.

Pairs and costs come from the Phase 2 shape prior (integration/uncertainty/confusion.py): characters
that look alike in print are cheap to confuse; anything else costs a full edit.
"""

from asali_codes.alphabet import INDEX

TRANSPOSE_COST = 0.6
INDEL_COST = 1.0
DOUBLED_KEY_COST = 0.5

_PRIOR_PAIRS: list[tuple[str, float]] = [
    ("O0", 0.25), ("D0", 0.35), ("Q0", 0.4), ("OD", 0.4), ("OQ", 0.4),
    ("I1", 0.25), ("L1", 0.35), ("IL", 0.35), ("17", 0.5), ("T7", 0.55),
    ("S5", 0.3), ("B8", 0.3), ("38", 0.5), ("Z2", 0.35), ("G6", 0.4),
    ("56", 0.6), ("68", 0.6), ("08", 0.6), ("A4", 0.6), ("EF", 0.6),
    ("UV", 0.6), ("CG", 0.6), ("MN", 0.7), ("HN", 0.7), ("RB", 0.7), ("EB", 0.7),
]  # fmt: skip

_COST: dict[tuple[str, str], float] = {}
for _pair, _cost in _PRIOR_PAIRS:
    _COST[(_pair[0], _pair[1])] = _cost
    _COST[(_pair[1], _pair[0])] = _cost

# For each character: the alphabet characters it is cheaply confused with.
SERIAL_PARTNERS: dict[str, list[tuple[str, float]]] = {}
for (_a, _b), _cost in _COST.items():
    if _b in INDEX:
        SERIAL_PARTNERS.setdefault(_a, []).append((_b, _cost))


def substitution_cost(true_ch: str, seen_ch: str) -> float:
    if true_ch == seen_ch:
        return 0.0
    return _COST.get((true_ch.upper(), seen_ch.upper()), 1.0)


def weighted_distance(true: str, seen: str) -> float:
    """Optimal-string-alignment distance from the true code to what was read."""
    n, m = len(true), len(seen)
    d = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        d[i][0] = i * INDEL_COST
    for j in range(1, m + 1):
        d[0][j] = d[0][j - 1] + _insert_cost(seen, j)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            best = min(
                d[i - 1][j - 1] + substitution_cost(true[i - 1], seen[j - 1]),
                d[i - 1][j] + INDEL_COST,
                d[i][j - 1] + _insert_cost(seen, j),
            )
            if i > 1 and j > 1 and true[i - 1] == seen[j - 2] and true[i - 2] == seen[j - 1]:
                best = min(best, d[i - 2][j - 2] + TRANSPOSE_COST)
            d[i][j] = best
    return round(d[n][m], 4)


def _insert_cost(seen: str, j: int) -> float:
    """An extra character in what was read; a repeated key is cheaper than a random one."""
    return DOUBLED_KEY_COST if j > 1 and seen[j - 1] == seen[j - 2] else INDEL_COST
