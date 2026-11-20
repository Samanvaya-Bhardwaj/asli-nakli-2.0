#!/usr/bin/env bash
# One command for one Mac (or Linux) computer of the four-computer run. Normally started by start-PC-B.command
# in the asali-net folder (double-click it in Finder, or run it in Terminal).
#
#   bash infra/scripts/start-pc.sh PC-B            start or restart
#   bash infra/scripts/start-pc.sh PC-B --fresh    reload the seeded data
#   bash infra/scripts/start-pc.sh PC-B --stop     stop
#
# This file only makes sure Docker is running and the Python 3.11 environment exists; infra/scripts/start_pc.py
# does the rest (databases, portal build, leftovers, data, the organisations).
set -u
PC="${1:-}"
case "$PC" in PC-A|PC-B|PC-C|PC-D) ;; *) echo "usage: $0 PC-A|PC-B|PC-C|PC-D [--fresh|--stop]"; exit 2 ;; esac
shift
cd "$(dirname "$0")/../.." || exit 1

say() { echo "[start] $*"; }
fail() { echo; echo "[start] STOPPED: $*"; echo; exit 1; }

# ---- Docker ----
if [ "${1:-}" != "--stop" ]; then
  command -v docker >/dev/null 2>&1 || fail "Docker is not installed. Install Docker Desktop, start it once, then run this again."
  if ! docker info >/dev/null 2>&1; then
    if [ "$(uname)" = "Darwin" ]; then
      say "starting Docker Desktop (this can take a minute) ..."
      open -a Docker || fail "Docker Desktop could not be opened. Start it yourself, then run this again."
    else
      fail "Docker is not running. Start it (sudo systemctl start docker), then run this again."
    fi
    for _ in $(seq 1 48); do sleep 5; docker info >/dev/null 2>&1 && break; done
    docker info >/dev/null 2>&1 || fail "Docker did not become ready within 4 minutes. Open Docker Desktop, wait until it is running, then run this again."
  fi
  say "Docker is running"
fi

# ---- Python 3.11 environment ----
PY=".venv/bin/python"
venv_ok() {
  [ -x "$PY" ] && "$PY" -c "import sys, asali_node, asali_directory, psycopg, pymongo, yaml, httpx, uvicorn; sys.exit(0 if sys.version_info[:2] == (3, 11) else 1)" >/dev/null 2>&1
}
if ! venv_ok; then
  say "setting up the Python 3.11 environment (first time only; a few minutes) ..."
  if command -v uv >/dev/null 2>&1; then
    uv sync --python 3.11
  elif command -v python3.11 >/dev/null 2>&1; then
    python3.11 -m venv --clear .venv && "$PY" -m pip install --disable-pip-version-check -r requirements.txt
  elif command -v python3 >/dev/null 2>&1; then
    # Any Python 3 (the Mac's own is enough) can install uv, and uv fetches Python 3.11 by itself.
    say "installing uv with python3 ..."
    python3 -m pip install --user --quiet --disable-pip-version-check uv && python3 -m uv sync --python 3.11
  else
    fail "No Python found. Install Python 3.11 (brew install python@3.11, or python.org), then run this again."
  fi
  venv_ok || fail "the Python environment could not be set up (see the messages above)."
  say "Python environment ready"
fi

[ "${1:-}" != "--stop" ] && say "if macOS asks whether Python may accept incoming connections: click Allow"
exec "$PY" infra/scripts/start_pc.py --pc "$PC" "$@"
