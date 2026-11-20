# Phase 3 deployment: four database services, one coordinator

```
 MACHINE 1                                         MACHINE 2
 +-----------------------------------------+       +------------------------------+
 | coordinator :8030  (holds no database)  |       |                              |
 |   GAV mediator, federated planner,      | HTTP  |  DB3 Manufacturer Registry   |
 |   Phase 1 verifier over remote wrappers |------>|      :8023   SQLite          |
 |                                         |       |  DB4 Ministry Reports        |
 |  DB1 Retail POS        :8021  JSON docs |------>|      :8024   REST over SQLite|
 |  DB2 Distributor ERP   :8022  SQLite    |       |                              |
 +-----------------------------------------+       +------------------------------+
```

Each database service:
- holds only its own database;
- **refuses to start if it can see another database's file** (`ASALI_STRICT_ISOLATION=1`);
- requires its own bearer token;
- executes its subqueries and discovers context through its own FK–PK relationships.

The coordinator never opens a database file. Every address, port and token comes from an env file; none is in the code.

| Layout | What it proves | How |
|---|---|---|
| A. Local simulation, processes | Separate processes and data directories, HTTP between them. **Not** separate machines. | §1 |
| B. One computer, Docker | The same, inside containers that each see only their own data. **Not** separate machines. | §2 |
| C. Two machines, Docker | **Actual multi-machine execution** | §3 |
| D. Two machines, no Docker | **Actual multi-machine execution** | §4 |

The coordinator tells you which layout it is running in. `GET /api/v3/federation/nodes`, and the first lines of `scripts/federated_demo.py`, print `LOCAL_SIMULATION`, `SINGLE_HOST_NETWORKED` or `MULTI_MACHINE` (§5).

---

## 0. Once, on the machine holding the full project data

```bash
python scripts/migrate_phase3.py        # if the databases predate Phase 3
python scripts/prepare_node_data.py     # deploy/nodes/db1..db4, each holding only its own files
```

`deploy/nodes/` is git-ignored. For two machines, copy `deploy/nodes/db3` and `deploy/nodes/db4` to Machine 2, and **delete them from Machine 1** if you want Machine 1 to hold no copy at all.

## 1. Local simulation, processes (Layout A)

```bash
python scripts/run_federation.py --env-file deploy/local.env
python scripts/federated_demo.py "Is MED-ASALI-009 genuine and was its cold chain maintained?"
```

The launcher starts four `api/node_db.py` processes on 127.0.0.1:8021–8024, each with `ASALI_DB_DIR` pointing at its own `deploy/nodes/<db>`, plus the coordinator on :8030. Ctrl+C stops all of them. A recorded run is in `phase3/documentation/evidence/requirement2_local_simulation.txt`.

## 2. One computer with Docker (Layout B)

```bash
docker compose --env-file deploy/local.env -f deploy/docker-compose.local.yml up --build
```

Each container bind-mounts only `deploy/nodes/<db>`, read-only, at `/data`. The image contains no database at all: see `Dockerfile.phase3.dockerignore`.

## 3. Two machines with Docker (Layout C)

**Both machines:** clone the project, install Docker, be on the same network, and know each machine's LAN address and hostname:

| | address | hostname |
|---|---|---|
| Windows | `ipconfig` → IPv4 Address | `hostname` |
| macOS | `ipconfig getifaddr en0` | `hostname` |
| Linux | `hostname -I` | `hostname` |

Generate four tokens once, and use the same four on both machines:

```bash
python -c "import secrets; [print(f'ASALI_DB{n}_TOKEN=' + secrets.token_urlsafe(24)) for n in range(1, 5)]"
```

**Machine 2** (DB3, DB4):

```bash
cp deploy/machine2.env.example deploy/machine2.env     # fill in ASALI_PHYSICAL_HOST and the DB3/DB4 tokens
# put deploy/nodes/db3 and deploy/nodes/db4 here (copied from step 0)
docker compose -f deploy/docker-compose.machine2.yml up --build -d
```

**Machine 1** (DB1, DB2, coordinator):

```bash
cp deploy/machine1.env.example deploy/machine1.env     # fill in both IPs, ASALI_PHYSICAL_HOST and all four tokens
python scripts/prepare_node_data.py --db db1 --db db2
docker compose -f deploy/docker-compose.machine1.yml up --build -d
python scripts/federated_demo.py --coordinator http://<MACHINE1_IP>:8030 "Is MED-ASALI-009 genuine?"
```

## 4. Two machines without Docker (Layout D)

```bash
# Machine 2
python scripts/run_federation.py --env-file deploy/machine2.env --only db3,db4
# Machine 1
python scripts/run_federation.py --env-file deploy/machine1.env --only db1,db2 --coordinator
python scripts/federated_demo.py "Is MED-ASALI-009 genuine?"
```

### Firewall

The services listen on 0.0.0.0 in the machine profiles. Allow the ports:
- **Windows (administrator):** `New-NetFirewallRule -DisplayName "Asali Phase 3" -Direction Inbound -Protocol TCP -LocalPort 8021-8024,8030 -Action Allow`
- **macOS:** accept the prompt the first time.
- **Linux:** `sudo ufw allow 8021:8030/tcp`

Check from Machine 1 that Machine 2 answers: `curl http://<MACHINE2_IP>:8023/health`.

## 5. Proving it is really two machines

Run `curl http://<MACHINE1_IP>:8030/api/v3/federation/nodes`, or read the first block of `federated_demo.py`. A genuine two-machine run shows **all** of the following:

1. `deployment.mode = MULTI_MACHINE`, with two `distinct_physical_hosts` and two `distinct_addresses`.
2. DB3 and DB4 with a `resolved_ip` equal to Machine 2's LAN address, and DB1 and DB2 with Machine 1's.
3. DB3 and DB4 reporting `seen_client` equal to **Machine 1's LAN address**: the coordinator's requests reached them over the network, from the other computer.
4. In the query result, every subquery for DB3/DB4 carrying `served_by.physical_host` = Machine 2's hostname and a `pid` of a process on Machine 2.
5. Stopping Machine 2's containers makes the next query report `db3: unreachable, db4: unreachable` with `partial: true` and the verdict `WITHHELD`, while DB1/DB2 still answer.

`physical_host` and `machine_label` are self-reported from the env files. Points 2 and 3 are the network's own evidence.

**What has been verified so far.** Layout A was run on one Windows laptop, and that transcript is in `phase3/documentation/evidence/`. Layouts B–D have **not** been executed yet: the Docker engine on that laptop needs WSL2, which needs an administrator install and a restart. The compose files pass `docker compose config`. A second machine has not been available.

## 6. Configuration reference

| Variable | Used by | Meaning |
|---|---|---|
| `ASALI_DBn_URL` | coordinator | where database n is reached |
| `ASALI_DBn_TOKEN` | coordinator and service n | bearer token of database n |
| `ASALI_DBn_PORT` | service n | port, when no URL is set (Machine 2) |
| `ASALI_DBn_MACHINE` | coordinator | label for reports |
| `ASALI_NODE_BIND` | services | interface to listen on |
| `ASALI_MACHINE_LABEL`, `ASALI_PHYSICAL_HOST` | all | what `/health` reports |
| `ASALI_STRICT_ISOLATION` | services | 1 = refuse to start beside another database's file |
| `ASALI_DB_DIR`, `ASALI_NOSQL_FILE` | services, coordinator | data directory (the coordinator's holds only its audit ledger) |
| `ASALI_FEDERATION=remote` | coordinator | the GAV resolver and verifier use the network, never local files |
| `ASALI_NODE_TIMEOUT_SEC` | coordinator | per-request timeout |
| `ASALI_COORDINATOR_BIND`, `_PORT`, `_TOKEN` | coordinator | where it listens; optional token |

Phase 1/2 settings are unchanged. `run_cluster.py --mode pc1|pc2|all` and ports 8011, 8012 and 8001 keep working. `ASALI_DB4_REST_URL` and `ASALI_DB4_LEGACY_TOKEN` now override the Phase 1 DB4 address and token, which used to be fixed in code.
