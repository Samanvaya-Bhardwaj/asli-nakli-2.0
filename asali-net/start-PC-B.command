#!/bin/bash
# Starts PC-B's share of the four-computer run: Docker, databases, Python, portal, data and the organisations.
# Double-click it in Finder, or run it in Terminal. Extra options: --fresh (reload the seeded data), --stop (stop).
# Leave the window open while the demo runs; Ctrl+C or closing it stops this computer's organisations.
# If double-clicking does nothing, run it once in Terminal as:  bash start-PC-B.command
cd "$(dirname "$0")" || exit 1
exec bash infra/scripts/start-pc.sh PC-B "$@"
