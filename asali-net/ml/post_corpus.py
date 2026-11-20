"""Put the generated corpus into the running network through each organisation's own portal API.

    python ml/post_corpus.py --simulation
    python ml/post_corpus.py --directory-url https://192.168.1.11:8400 --ca rootCA.pem --password ...

Staff documents go to /api/documents of their owner, consumer complaints to /api/report of the consumer node,
so the real ingest pipeline reads every one. The document type is not declared: the model has to predict it.
"""

import argparse
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "seed"))
sys.path.insert(0, str(ROOT / "infra" / "scripts"))
sys.path.insert(0, str(ROOT / "packages" / "asali_text"))
import addressing  # noqa: E402
import network_model  # noqa: E402
from asali_text import corpus  # noqa: E402
from client import Portal  # noqa: E402

OUT = ROOT / "infra" / "out" / "SIM"


def main() -> int:
    ap = argparse.ArgumentParser()
    addressing.add_arguments(ap)
    args = ap.parse_args()
    if not (args.simulation or args.directory_url):
        args.simulation = True  # no arguments: the local simulation, as before
    addr = addressing.from_args(args)
    net = network_model.load()
    pw = addressing.staff_password(args.password, OUT / "secrets.json")
    docs = corpus.load_docs(ROOT / "ml" / "data" / "generated")
    rng = random.Random(7)
    state = OUT / "corpus_posted.json"
    done: set[str] = set(json.loads(state.read_text())) if state.exists() else set()
    portals: dict[str, Portal] = {}
    consumer = httpx.Client(timeout=60, verify=addr.verify)
    posted = 0
    for d in docs:
        if d["doc_id"] in done:
            continue
        org = d["owner_org"]
        at = (
            datetime.fromisoformat("2026-11-08T09:00:00+05:30") + timedelta(hours=rng.randrange(0, 240))
        ).isoformat()
        if net.orgs[org].type == "consumer":
            r = consumer.post(f"{addr.url(org)}/api/report",
                              json={"text": d["text"], "city": net.orgs[org].city, "at": at})  # fmt: skip
        else:
            portals.setdefault(org, Portal(org, addr.url(org), pw, verify=addr.verify))
            r = portals[org].http.post("/api/documents", json={"text": d["text"], "at": at})
        if r.status_code not in (200, 201):
            print("failed", d["doc_id"], org, r.status_code, r.text[:200])
            continue
        done.add(d["doc_id"])
        posted += 1
        if posted % 100 == 0:
            state.write_text(json.dumps(sorted(done)))
            print(f"{posted} posted")
    state.write_text(json.dumps(sorted(done)))
    print(f"posted {posted} documents ({len(done)} in all)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
