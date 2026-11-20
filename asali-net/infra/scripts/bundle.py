"""Move the seeded data from the one-computer simulation to the four computers: one zip per computer.

    python infra/scripts/bundle.py export                      # on the computer that ran the simulation
    python infra/scripts/bundle.py import --pc PC-C --zip infra/out/bundles/PC-C.zip   # run_pc.py calls this

Export reads every organisation's own database (PostgreSQL tables as CSV in foreign-key order, MongoDB collections as
extended JSON, SQLite files by the backup API) and its data folder (signing key, text vault, activity log), and
writes infra/out/bundles/PC-A.zip ... PC-D.zip with only that computer's organisations, plus the scenario codes.
Import recreates each database empty with the organisation's own schema, then loads the rows back.

Why a bundle: the history of the packs (made, shipped, received, sold, months of documents) is created once and the
same on every run, so the demonstration does not depend on seeding a few thousand records over Wi-Fi on the day.
Every check, trace, context search and new record during the demonstration is live across the four computers.
"""

import argparse
import io
import json
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

import local_engines as le
import network_model

ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT / "infra" / "out" / "SIM"
BUNDLES = ROOT / "infra" / "out" / "bundles"
SKIP_FILES = {"directory_cache.json"}  # addresses of the simulation; each computer learns its own


def _db_name(org_id: str) -> str:
    return "asali_" + org_id.replace("-", "_")


# ---------- data folder ----------
def _copy_data_dir(src: Path, dst: Path) -> None:
    for p in src.rglob("*"):
        rel = p.relative_to(src)
        if p.is_dir() or p.name in SKIP_FILES or p.name.endswith(("-wal", "-shm", "-journal")):
            continue
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if p.suffix == ".sqlite":  # a consistent copy even while the node writes
            with sqlite3.connect(p) as s, sqlite3.connect(out) as d:
                s.backup(d)
        else:
            shutil.copy2(p, out)


# ---------- PostgreSQL ----------
def _pg_order(conn) -> list[str]:  # type: ignore[no-untyped-def]
    """Tables parents first, so loading never breaks a foreign key."""
    tables = [r[0] for r in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")]
    deps = {t: set() for t in tables}
    for child, parent in conn.execute(
        "SELECT cl.relname, fcl.relname FROM pg_constraint k JOIN pg_class cl ON cl.oid = k.conrelid "
        "JOIN pg_class fcl ON fcl.oid = k.confrelid JOIN pg_namespace n ON n.oid = cl.relnamespace "
        "WHERE k.contype = 'f' AND n.nspname = 'public'"
    ):
        if child != parent:
            deps[child].add(parent)
    order: list[str] = []
    while deps:
        ready = sorted(t for t, d in deps.items() if not d - set(order))
        if not ready:
            raise RuntimeError(f"foreign keys form a cycle: {deps}")
        order += ready
        for t in ready:
            del deps[t]
    return order


def _pg_export(url: str, out: Path) -> None:
    import psycopg

    out.mkdir(parents=True, exist_ok=True)
    with psycopg.connect(url) as conn:
        order = _pg_order(conn)
        for t in order:
            buf = io.BytesIO()
            with conn.cursor().copy(f'COPY "{t}" TO STDOUT (FORMAT csv, HEADER)') as cp:
                for chunk in cp:
                    buf.write(bytes(chunk))
            (out / f"{t}.csv").write_bytes(buf.getvalue())
        seqs = {r[0]: r[1] for r in conn.execute("SELECT sequencename, last_value FROM pg_sequences WHERE schemaname = 'public'")}
    (out / "order.json").write_text(json.dumps({"tables": order, "sequences": seqs}))


def _pg_import(url: str, src: Path) -> None:
    import psycopg

    meta = json.loads((src / "order.json").read_text())
    with psycopg.connect(url) as conn:
        conn.execute("TRUNCATE " + ", ".join(f'"{t}"' for t in meta["tables"]) + " CASCADE")
        for t in meta["tables"]:
            with conn.cursor().copy(f'COPY "{t}" FROM STDIN (FORMAT csv, HEADER)') as cp:
                cp.write((src / f"{t}.csv").read_bytes())
        for name, value in meta["sequences"].items():
            if value is not None:
                conn.execute("SELECT setval(%s, %s)", (name, value))
        conn.commit()


# ---------- MongoDB ----------
def _mongo_export(url: str, out: Path) -> None:
    from bson import json_util
    from pymongo import MongoClient

    out.mkdir(parents=True, exist_ok=True)
    client: MongoClient = MongoClient(url)
    db = client.get_default_database()
    for name in sorted(db.list_collection_names()):
        if name.startswith("system."):
            continue
        lines = [json_util.dumps(d, json_options=json_util.CANONICAL_JSON_OPTIONS) for d in db[name].find()]
        (out / f"{name}.jsonl").write_text("\n".join(lines), encoding="utf-8")
    client.close()


def _mongo_import(url: str, src: Path) -> None:
    from bson import json_util
    from pymongo import MongoClient

    client: MongoClient = MongoClient(url)
    db = client.get_default_database()
    for f in sorted(src.glob("*.jsonl")):
        db[f.stem].delete_many({})
        docs = [json_util.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]
        if docs:
            db[f.stem].insert_many(docs, ordered=False)  # they passed the same validators when first written
    client.close()


# ---------- commands ----------
def export() -> int:
    net = network_model.load()
    work = Path(tempfile.mkdtemp(prefix="asali-bundle-"))
    for org_id, org in net.orgs.items():
        env = json.loads((SIM / "envs" / f"{org_id}.json").read_text())
        base = work / org.pc / org_id
        _copy_data_dir(Path(env["DATA_DIR"]), base / "data")
        if org.engine == "postgres":
            _pg_export(env["DB_RW_URL"], base / "db")
        elif org.engine == "mongo":
            _mongo_export(env["DB_RW_URL"], base / "db")
        print(f"exported {org_id} ({org.engine}) for {org.pc}")
    BUNDLES.mkdir(parents=True, exist_ok=True)
    for pc in net.pcs:
        for f in ("scenarios.json", "seed_state.json"):
            if (SIM / f).exists():
                shutil.copy2(SIM / f, work / pc / f)
        target = BUNDLES / f"{pc}.zip"
        target.unlink(missing_ok=True)
        shutil.make_archive(str(target.with_suffix("")), "zip", work / pc)
        print(f"wrote {target.relative_to(ROOT)} ({target.stat().st_size // 1024} KB)")
    shutil.rmtree(work, ignore_errors=True)
    return 0


def import_bundle(pc: str, zip_path: Path, out: Path, store_city: dict[str, str]) -> list[str]:
    """Load one computer's organisations. Returns the organisation ids loaded."""
    from asali_node.stores.registry import open_store

    net = network_model.load()
    work = Path(tempfile.mkdtemp(prefix="asali-import-"))
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(work)
    loaded = []
    for org_id, org in net.on_pc(pc).items():
        src = work / org_id
        if not src.exists():
            continue
        data = out / "data" / org_id
        shutil.rmtree(data, ignore_errors=True)
        shutil.copytree(src / "data", data)
        if org.engine == "sqlite":
            loaded.append(org_id)
            continue
        rw, _ro = (le.provision_pg if org.engine == "postgres" else le.provision_mongo)(_db_name(org_id))
        store = open_store(org_id, rw, "rw", store_city.get(org_id, org.city))
        store.init_schema()  # the organisation's own tables, keys and reference rows
        store.close()
        (_pg_import if org.engine == "postgres" else _mongo_import)(rw, src / "db")
        loaded.append(org_id)
    for f in ("scenarios.json", "seed_state.json"):
        if (work / f).exists():
            shutil.copy2(work / f, out / f)
    shutil.rmtree(work, ignore_errors=True)
    return loaded


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["export", "import"])
    ap.add_argument("--pc")
    ap.add_argument("--zip", type=Path)
    args = ap.parse_args()
    if args.action == "export":
        return export()
    if not (args.pc and args.zip):
        raise SystemExit("import needs --pc and --zip")
    out = ROOT / "infra" / "out" / args.pc
    print("loaded:", ", ".join(import_bundle(args.pc, args.zip, out, {})))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "services" / "node"))
    sys.exit(main())
