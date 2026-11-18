"""Save new code files as first generated, before they are run, for the vibe-coding record.

Usage, from asali-net/:  python docs/vibe/snapshot.py M1 packages/asali_codes/asali_codes/checks.py ...
"""

from __future__ import annotations

import shutil
import sys
from collections.abc import Iterable
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]


class SnapshotError(Exception):
    pass


def snapshot(milestone: str, files: Iterable[Path], base: Path = BASE) -> list[Path]:
    base = base.resolve()
    out_root = base / "docs" / "vibe" / "generated" / milestone
    plan: list[tuple[Path, Path]] = []
    for f in files:
        src = Path(f).resolve()
        if not src.is_file():
            raise SnapshotError(f"{f} does not exist")
        try:
            rel = src.relative_to(base)
        except ValueError:
            raise SnapshotError(f"{f} is outside {base}") from None
        target = out_root / rel
        if target.exists():
            raise SnapshotError(f"{rel.as_posix()} is already snapshotted for {milestone}")
        plan.append((src, target))
    for src, target in plan:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
    return [target for _, target in plan]


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: snapshot.py <milestone> <file>...", file=sys.stderr)
        return 2
    try:
        written = snapshot(argv[0], [Path(a) for a in argv[1:]])
    except SnapshotError as e:
        print(f"snapshot refused: {e}", file=sys.stderr)
        return 1
    for w in written:
        print(f"saved {w.relative_to(BASE).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
