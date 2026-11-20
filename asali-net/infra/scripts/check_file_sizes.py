"""Fail if any Python or TypeScript source file is over 400 lines (PLAN.md 15, rule 1)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIMIT = 400
SKIP = {".venv", "node_modules", "dist", "generated", "out", "data"}


def main() -> int:
    big = []
    for pattern in ("*.py", "*.ts", "*.tsx"):
        for p in ROOT.rglob(pattern):
            if SKIP & set(p.relative_to(ROOT).parts) or p.name.endswith(".d.ts"):
                continue
            n = sum(1 for _ in p.open(encoding="utf-8", errors="replace"))
            if n > LIMIT:
                big.append((n, p.relative_to(ROOT)))
    for n, p in sorted(big, reverse=True):
        print(f"{n:5} {p}")
    print("File sizes OK" if not big else f"{len(big)} file(s) over {LIMIT} lines")
    return 1 if big else 0


if __name__ == "__main__":
    sys.exit(main())
