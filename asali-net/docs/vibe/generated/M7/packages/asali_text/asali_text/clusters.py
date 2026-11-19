"""Models M4 (near-duplicate complaints) and M5 (unusual batch) (TEXT_ML.md 6.5)."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

import numpy as np
from scipy.stats import poisson
from sklearn.metrics.pairwise import cosine_similarity

DUPLICATE_SIMILARITY = 0.9
DUPLICATE_DAYS = 7


@dataclass(frozen=True)
class Complaint:
    doc_id: str
    node: str
    batch_key: str
    at: datetime
    reporter: str = ""


def similarity_matrix(vectors: object) -> np.ndarray:
    return cosine_similarity(vectors)  # type: ignore[arg-type, no-any-return]


def duplicates(items: Sequence[Complaint], sims: np.ndarray, threshold: float = DUPLICATE_SIMILARITY) -> list[tuple[int, int]]:
    """Pairs that count as one complaint: similar text, same consumer node and batch, within 7 days."""
    out = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            if (a.node == b.node and a.batch_key == b.batch_key and abs((a.at - b.at).days) <= DUPLICATE_DAYS
                    and sims[i, j] >= threshold):  # fmt: skip
                out.append((i, j))
    return out


def independent(items: Sequence[Complaint], pairs: list[tuple[int, int]]) -> int:
    """How many complaints remain once duplicates are merged."""
    parent = list(range(len(items)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, j in pairs:
        parent[find(i)] = find(j)
    return len({find(i) for i in range(len(items))})


def unusual(k: int, expected: float, alpha: float = 0.01, minimum: int = 3) -> bool:
    """Are k complaints more than chance explains for a batch that should have `expected`? (Poisson tail)"""
    return k >= minimum and expected > 0 and float(poisson.sf(k - 1, expected)) < alpha
