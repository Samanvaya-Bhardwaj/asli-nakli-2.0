"""Run every automated check and record its real outcome in docs/evidence/checks.json.

    python docs/scripts/run_checks.py

Nothing is retyped: each entry holds the command, the exit code and the last lines it printed. The report reads this file.
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = (
    str(ROOT / ".venv" / "Scripts" / "python.exe")
    if (ROOT / ".venv" / "Scripts").exists()
    else sys.executable
)
WEB = ROOT / "apps" / "portal-web"
DETECT = str(ROOT.parent / ".claude" / "skills" / "impeccable" / "scripts" / "impeccable.cmd")

CHECKS: list[tuple[str, list[str], Path]] = [
    ("pytest (all, network tests skipped)", [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider"], ROOT),
    (
        "pytest scenarios against the running simulation",
        [PY, "-m", "pytest", "tests/network", "--simulation-up", "-q", "-p", "no:cacheprovider"],
        ROOT,
    ),
    ("ruff check", [PY, "-m", "ruff", "check", "."], ROOT),
    ("ruff format check", [PY, "-m", "ruff", "format", "--check", "."], ROOT),
    ("mypy (strict, asali_codes)", [PY, "-m", "mypy"], ROOT),
    ("vitest", ["cmd", "/c", "npx", "vitest", "run"], WEB),
    ("eslint", ["cmd", "/c", "npx", "eslint", "."], WEB),
    ("typescript build", ["cmd", "/c", "npm", "run", "build"], WEB),
    ("contrast of every token pair", ["node", "scripts/check_contrast.mjs"], WEB),
    ("copy check (banned words, dashes, emoji)", ["node", "scripts/check_copy.mjs"], WEB),
    ("Impeccable detector on the portal source", [DETECT, "detect", "--json", "src"], WEB),
    ("file sizes (400 lines)", [PY, "infra/scripts/check_file_sizes.py"], ROOT),
]


def main() -> int:
    results = []
    for name, cmd, cwd in CHECKS:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False, timeout=900)
        out = [
            line
            for line in (p.stdout + p.stderr).splitlines()
            if line.strip() and not line.startswith('{"request_id')
        ]
        passed = p.returncode == 0 and (
            name.startswith("Impeccable") is False or p.stdout.strip() in ("[]", "")
        )
        results.append({"check": name, "passed": passed, "exit_code": p.returncode, "tail": out[-4:]})
        print(f"{'PASS' if passed else 'FAIL'}  {name}")
    path = ROOT / "docs" / "evidence" / "checks.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"run_at": datetime.now().isoformat(timespec="seconds"), "results": results}, indent=1),
        encoding="utf-8",
    )
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
