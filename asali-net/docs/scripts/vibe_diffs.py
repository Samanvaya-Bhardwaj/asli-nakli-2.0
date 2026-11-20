"""Compare every snapshotted file with its current version and write docs/vibe/DIFFS.md.

    python docs/scripts/vibe_diffs.py

A snapshot is a file as first generated, saved before it was first run. The diff shows what changed afterwards,
whatever the reason. CHANGES.md says why for the changes that came from running the code.
"""

import difflib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "docs" / "vibe" / "generated"


def main() -> int:
    changed: list[tuple[str, str]] = []
    same = 0
    missing: list[str] = []
    for snap in sorted(p for p in GEN.rglob("*") if p.is_file()):
        rel = snap.relative_to(GEN)
        milestone, path = rel.parts[0], Path(*rel.parts[1:])
        current = ROOT / path
        if not current.exists():
            missing.append(f"{milestone}/{path}")
            continue
        a = snap.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").splitlines()
        b = current.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").splitlines()
        if a == b:
            same += 1
            continue
        diff = "\n".join(
            difflib.unified_diff(a, b, f"generated/{milestone}/{path}", str(path), lineterm="", n=2)
        )
        changed.append((f"{milestone}/{path}", diff))
    lines = ["# Generated code against current code", "", f"- Files saved as first generated: {same + len(changed) + len(missing)}",
             f"- Unchanged since: {same}", f"- Changed since: {len(changed)}", f"- No longer present: {len(missing)}", ""]  # fmt: skip
    if missing:
        lines += ["## No longer present", ""] + [f"- {m}" for m in missing] + [""]
    for name, diff in changed:
        lines += [f"## {name}", "", "```diff", diff, "```", ""]
    (ROOT / "docs" / "vibe" / "DIFFS.md").write_text("\n".join(lines), encoding="utf-8")
    print(
        f"{same + len(changed) + len(missing)} snapshotted files: {same} unchanged, {len(changed)} changed, {len(missing)} missing"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
