#!/usr/bin/env bash
# Rebuild only the text side of the running local simulation: clear the vaults, regenerate the corpus from the
# seeded network, retrain, evaluate, post the documents again and plant the scenarios. One computer, simulation.
set -e
py=.venv/Scripts/python.exe
out=infra/out/SIM
wait_up() { for i in $(seq 1 120); do if [ -f $out/ready ] && curl -s -m 2 http://127.0.0.1:8402/api/config >/dev/null; then return; fi; sleep 4; done; echo "network did not come up"; exit 1; }
$py infra/scripts/run_local_network.py --stop || true
sleep 3
rm -rf $out/data/*/vault $out/data/*/documents
rm -f $out/ready $out/scenarios.json $out/corpus_posted.json $out/rebuild_done
PYTHONUNBUFFERED=1 $py infra/scripts/run_local_network.py --keep > $out/runner1.log 2>&1 &
wait_up
$py ml/generate_corpus.py --seed 42 | tail -3
$py -W ignore -m asali_text.train --models m1,m2,m3 --corpus ml/data/generated --out ml/models | tail -5
$py -W ignore -m asali_text.evaluate --out docs/evidence/ml | sed -n 1,25p
$py infra/scripts/run_local_network.py --stop
sleep 3
rm -f $out/ready
PYTHONUNBUFFERED=1 $py infra/scripts/run_local_network.py --keep > $out/runner2.log 2>&1 &
wait_up
$py ml/post_corpus.py | tail -3
$py seed/scenarios.py --simulation | tail -2
$py seed/scenarios.py --simulation --text | tail -2
$py infra/scripts/run_scenarios.py || true
touch $out/rebuild_done
echo TEXT REBUILD DONE
wait
