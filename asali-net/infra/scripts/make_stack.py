"""Write one PC's Docker stack from infra/network.yaml (PLAN.md 16.2).

    python infra/scripts/make_stack.py --pc PC-C --ip 192.168.1.23 --directory-url https://192.168.1.11:8400
    python infra/scripts/make_stack.py --simulation

Writes infra/out/<PC|SIM>/{compose.yml, Caddyfile, .env, init/}. Passwords are random, made once and kept on
re-runs. Databases are never published; only Caddy's ports are. Docker is needed to run the result, not to write it.
"""

import argparse
import json
import secrets
import sys
from pathlib import Path
from string import Template
from typing import Any

import network_model
import yaml

ROOT = Path(__file__).resolve().parents[2]
INIT = ROOT / "infra" / "compose" / "init"
MEM = {
    "app": "384m",
    "postgres": "256m",
    "mongo": "512m",
    "caddy": "64m",
    "directory": "128m",
}  # PLAN.md 16.5


def env_name(org_id: str, what: str) -> str:
    return f"{org_id.upper().replace('-', '_')}_{what}"


def load_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return dict(
        line.split("=", 1)
        for line in path.read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )


def secrets_for(
    net: network_model.Network, orgs: dict[str, network_model.Org], existing: dict[str, str]
) -> dict[str, str]:
    env = dict(existing)
    for key in ("JOIN_TOKEN", "ADMIN_TOKEN"):
        env.setdefault(key, secrets.token_hex(16))
    for org_id, org in orgs.items():
        env.setdefault(env_name(org_id, "STAFF_PASSWORD"), secrets.token_urlsafe(9))
        if org.engine != "sqlite":
            env.setdefault(env_name(org_id, "RW_PASSWORD"), secrets.token_hex(12))
            env.setdefault(env_name(org_id, "RO_PASSWORD"), secrets.token_hex(12))
    return env


def app_env(
    org_id: str, org: network_model.Org, simulation: bool, directory_url: str, public_base: str, host: str
) -> dict[str, Any]:
    e: dict[str, Any] = {
        "ORG_ID": org_id, "ORG_TYPE": org.type, "ORG_NAME": org.name, "ORG_CITY": org.city, "ORG_STATE": org.state,
        "ENGINE": org.engine, "DIRECTORY_URL": directory_url, "JOIN_TOKEN": "${JOIN_TOKEN}", "PUBLIC_BASE_URL": public_base,
        "HOST_NAME": host, "ASALI_MODE": "simulation" if simulation else "network", "DATA_DIR": "/data",
        "STAFF_SEED_JSON": json.dumps([{"username": "staff", "password": "${" + env_name(org_id, "STAFF_PASSWORD") + "}", "role": "admin",
                                        "display_name": f"{org.name} staff"}]),
    }  # fmt: skip
    if org.issuer_code:
        e["ISSUER_CODE"], e["GS1_PREFIX"] = org.issuer_code, org.gs1_prefix
    if org.served_states:
        e["SERVED_STATES"] = json.dumps(org.served_states)
    if org.shop:
        e["SHOP_SETTINGS_JSON"] = json.dumps(org.shop.model_dump() | {"salt": org_id})
    rw, ro = env_name(org_id, "RW_PASSWORD"), env_name(org_id, "RO_PASSWORD")
    if org.engine == "sqlite":
        e["SQLITE_PATH"] = "/data/own.sqlite"
    elif org.engine == "postgres":
        e["DB_RW_URL"] = f"postgresql://app_rw:${{{rw}}}@{org_id}-db:5432/asali"
        e["DB_RO_URL"] = f"postgresql://share_ro:${{{ro}}}@{org_id}-db:5432/asali"
    else:
        e["DB_RW_URL"] = f"mongodb://app_rw:${{{rw}}}@{org_id}-db:27017/asali?authSource=asali"
        e["DB_RO_URL"] = f"mongodb://share_ro:${{{ro}}}@{org_id}-db:27017/asali?authSource=asali"
    return e


def build(net: network_model.Network, name: str, orgs: dict[str, network_model.Org], simulation: bool, ip: str, directory_url: str,
          with_directory: bool, out: Path) -> dict[str, Any]:  # fmt: skip
    services: dict[str, Any] = {}
    volumes: dict[str, Any] = {}
    for org_id, org in orgs.items():
        public = f"http://caddy:{org.port}" if simulation else f"https://{ip}:{org.port}"
        services[f"{org_id}-app"] = {
            "build": {"context": "../../..", "dockerfile": "services/node/Dockerfile"},
            "environment": app_env(org_id, org, simulation, directory_url, public, "SIM-DOCKER" if simulation else net.orgs[org_id].pc),
            "volumes": [f"{org_id}-data:/data"] + ([] if simulation else ["./certs/rootCA.pem:/certs/rootCA.pem:ro"]),
            "mem_limit": MEM["app"], "restart": "unless-stopped",
        }  # fmt: skip
        volumes[f"{org_id}-data"] = {}
        if not simulation:
            services[f"{org_id}-app"]["environment"]["SSL_CERT_FILE"] = "/certs/rootCA.pem"
        if org.engine != "sqlite":
            services[f"{org_id}-app"]["depends_on"] = [f"{org_id}-db"]
            volumes[f"{org_id}-db"] = {}
            if org.engine == "postgres":
                services[f"{org_id}-db"] = {
                    "image": "postgres:16-alpine", "environment": {"POSTGRES_PASSWORD": "${" + env_name(org_id, "RW_PASSWORD") + "}"},
                    "command": ["postgres", "-c", "shared_buffers=64MB"],
                    "volumes": [f"{org_id}-db:/var/lib/postgresql/data", f"./init/{org_id}.sql:/docker-entrypoint-initdb.d/10-init.sql:ro"],
                    "mem_limit": MEM["postgres"], "restart": "unless-stopped",
                }  # fmt: skip
            else:
                services[f"{org_id}-db"] = {
                    "image": "mongo:7", "command": ["mongod", "--auth", "--wiredTigerCacheSizeGB", "0.25"],
                    "environment": {"MONGO_INITDB_ROOT_USERNAME": "root", "MONGO_INITDB_ROOT_PASSWORD": "${" + env_name(org_id, "RW_PASSWORD") + "}"},
                    "volumes": [f"{org_id}-db:/data/db", f"./init/{org_id}.js:/docker-entrypoint-initdb.d/10-init.js:ro"],
                    "mem_limit": MEM["mongo"], "restart": "unless-stopped",
                }  # fmt: skip
    ports = [f"{o.port}:{o.port}" for o in orgs.values()] + (
        [f"{net.directory.port}:{net.directory.port}"] if with_directory else []
    )
    if with_directory:
        services["directory"] = {
            "build": {"context": "../../..", "dockerfile": "services/directory/Dockerfile"},
            "environment": {"JOIN_TOKEN": "${JOIN_TOKEN}", "ADMIN_TOKEN": "${ADMIN_TOKEN}", "DATA_DIR": "/data"},
            "volumes": ["directory-data:/data"], "mem_limit": MEM["directory"], "restart": "unless-stopped",
        }  # fmt: skip
        volumes["directory-data"] = {}
    caddy_volumes = ["./Caddyfile:/etc/caddy/Caddyfile:ro"] + ([] if simulation else ["./certs:/certs:ro"])
    services["caddy"] = {"image": "caddy:2-alpine", "ports": ports, "volumes": caddy_volumes, "mem_limit": MEM["caddy"],
                         "depends_on": [s for s in services if s.endswith("-app") or s == "directory"], "restart": "unless-stopped"}  # fmt: skip
    return {"name": f"asali-{name.lower()}", "services": services, "volumes": volumes}


def caddyfile(
    orgs: dict[str, network_model.Org], with_directory: bool, directory_port: int, simulation: bool
) -> str:
    tls = "" if simulation else "    tls /certs/cert.pem /certs/key.pem\n"
    scheme = "http://" if simulation else "https://"
    blocks = [
        f"{scheme}:{o.port} {{\n{tls}    reverse_proxy {org_id}-app:8000\n}}" for org_id, o in orgs.items()
    ]
    if with_directory:
        blocks.append(f"{scheme}:{directory_port} {{\n{tls}    reverse_proxy directory:8000\n}}")
    return "{\n    auto_https off\n}\n\n" + "\n\n".join(blocks) + "\n"


def write_init(org_id: str, org: network_model.Org, env: dict[str, str], out: Path) -> None:
    if org.engine == "sqlite":
        return
    ext, tmpl = (
        ("sql", "postgres-init.sql.tmpl") if org.engine == "postgres" else ("js", "mongo-init.js.tmpl")
    )
    text = Template((INIT / tmpl).read_text())
    body = text.substitute(
        DB_NAME="asali",
        RW_PASSWORD=env[env_name(org_id, "RW_PASSWORD")],
        RO_PASSWORD=env[env_name(org_id, "RO_PASSWORD")],
    )
    (out / "init").mkdir(exist_ok=True)
    (out / "init" / f"{org_id}.{ext}").write_text(body)


def generate(
    pc: str | None,
    ip: str,
    directory_url: str | None,
    simulation: bool,
    out_root: Path,
    net: network_model.Network,
) -> Path:
    name = "SIM" if simulation else str(pc)
    orgs = dict(net.orgs) if simulation else net.on_pc(name)
    if not orgs:
        raise SystemExit(f"{name} hosts no organisations in network.yaml")
    with_directory = simulation or net.directory.pc == name
    out = out_root / name
    out.mkdir(parents=True, exist_ok=True)
    env = secrets_for(net, orgs, load_env(out / ".env"))
    env["PUBLIC_HOST_IP"] = ip
    dir_url = (
        "http://directory:8000" if simulation else (directory_url or f"https://{ip}:{net.directory.port}")
    )
    env["DIRECTORY_URL"] = dir_url
    (out / ".env").write_text(
        "# generated by make_stack.py; never committed\n"
        + "".join(f"{k}={v}\n" for k, v in sorted(env.items()))
    )
    compose = build(net, name, orgs, simulation, ip, dir_url, with_directory, out)
    (out / "compose.yml").write_text(yaml.safe_dump(compose, sort_keys=False, width=120))
    (out / "Caddyfile").write_text(caddyfile(orgs, with_directory, net.directory.port, simulation))
    for org_id, org in orgs.items():
        write_init(org_id, org, env, out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--pc")
    g.add_argument("--simulation", action="store_true")
    ap.add_argument("--ip", default="127.0.0.1")
    ap.add_argument("--directory-url")
    args = ap.parse_args()
    out = generate(
        args.pc, args.ip, args.directory_url, args.simulation, ROOT / "infra" / "out", network_model.load()
    )
    print(f"wrote {out}/compose.yml, Caddyfile, .env and init/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
