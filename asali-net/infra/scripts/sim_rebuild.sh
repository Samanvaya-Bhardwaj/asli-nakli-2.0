#!/usr/bin/env bash
# Rebuild the whole local simulation from nothing: network, seed, scenarios, corpus, models, evaluation, text.
# Simulation on one computer (see run_local_network.py). Stays in the foreground to keep the nodes running.
set -e
py=.venv/Scripts/python.exe
out=infra/out/SIM
$py infra/scripts/run_local_network.py --stop || true
sleep 2
rm -f $out/ready $out/seed_state.json $out/scenarios.json $out/corpus_posted.json $out/rebuild_done
PYTHONUNBUFFERED=1 $py infra/scripts/run_local_network.py --fresh > $out/runner1.log 2>&1 &
until [ -f $out/ready ]; do sleep 2; done
$py seed/seed_network.py --simulation | tail -3
$py seed/scenarios.py --simulation
$py ml/generate_corpus.py --seed 42 | tail -3
$py -W ignore -m asali_text.train --models m1,m2,m3 --corpus ml/data/generated --out ml/models | tail -5
$py -W ignore -m asali_text.evaluate --out docs/evidence/ml | sed -n 1,25p
$py infra/scripts/run_local_network.py --stop
sleep 3
rm -f $out/ready
PYTHONUNBUFFERED=1 $py infra/scripts/run_local_network.py --keep > $out/runner2.log 2>&1 &
until [ -f $out/ready ]; do sleep 2; done
$py ml/post_corpus.py | tail -5
$py seed/scenarios.py --simulation --text
touch $out/rebuild_done
echo REBUILD DONE
wait
