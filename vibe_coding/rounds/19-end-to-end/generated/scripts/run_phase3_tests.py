#!/usr/bin/env python3
"""
run_phase3_tests.py
-------------------
Runs every test suite of the project, each in its own process (several suites set
their data paths when imported, so they must not share one), plus the page-render
check, and writes the real outcome to phase3/documentation/evidence/test_results.txt.

    python scripts/run_phase3_tests.py
"""

from __future__ import annotations
import os
import re
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "phase3", "documentation", "evidence", "test_results.txt")
SUITES = [
    ("Phase 2 uncertainty + replication (Phase 1/2 regression)", ["tests.test_uncertainty", "tests.test_replication"]),
    ("Phase 3 R1: related tables, keys, integrity", ["tests.test_phase3_schema"]),
    ("Phase 3 R2: distributed services, federation", ["tests.test_phase3_federation"]),
    ("Phase 3: subquery operators on both engines", ["tests.test_phase3_operators"]),
    ("Phase 3 R3: SCORE context discovery + aggregation", ["tests.test_phase3_score"]),
    ("Phase 3 R4: documents, retrieval, integration", ["tests.test_phase3_documents"]),
    ("Phase 3: end to end over HTTP (coordinator service)", ["tests.test_phase3_end_to_end"]),
]


def main():
    lines = [f"Test run {time.strftime('%Y-%m-%d %H:%M')} on {os.environ.get('COMPUTERNAME') or os.uname().nodename}, "
             f"Python {sys.version.split()[0]}", ""]
    total = failed = 0
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    for title, mods in SUITES:
        t0 = time.time()
        p = subprocess.run([sys.executable, "-m", "unittest", *mods], cwd=BASE, env=env, capture_output=True, text=True)
        out = p.stdout + p.stderr
        ran = re.search(r"^Ran (\d+) tests?", out, re.M)
        n = int(ran.group(1)) if ran else 0
        status = "OK" if p.returncode == 0 else "FAILED"
        total += n
        failed += p.returncode != 0
        lines.append(f"{status:<6} {n:>3} tests  {time.time() - t0:6.1f}s  {title}  ({' '.join(mods)})")
        if p.returncode != 0:
            lines += ["       " + l for l in out.splitlines() if l.startswith(("FAIL:", "ERROR:", "AssertionError"))][:20]
    node = subprocess.run(["node", os.path.join("phase3", "tools", "check_page_render.mjs")], cwd=BASE,
                          capture_output=True, text=True)
    lines.append(f"{'OK' if node.returncode == 0 else 'FAILED':<6}   -        -     page render check against real responses "
                 f"(phase3/tools/check_page_render.mjs)")
    lines += ["       " + l for l in node.stdout.strip().splitlines()]
    failed += node.returncode != 0
    lines += ["", f"TOTAL: {total} unit tests in {len(SUITES)} suites; "
                  f"{'all passed' if not failed else f'{failed} suite(s) FAILED'}; page render check "
                  f"{'passed' if node.returncode == 0 else 'FAILED'}"]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
