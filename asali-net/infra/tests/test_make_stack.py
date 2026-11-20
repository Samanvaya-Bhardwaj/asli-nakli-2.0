import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import make_stack as ms
import network_model as nm

NET = nm.load()


def stack(tmp_path, **kw):
    out = ms.generate(
        kw.get("pc"), "10.0.0.7", kw.get("directory_url"), kw.get("simulation", False), tmp_path, NET
    )
    return out, yaml.safe_load((out / "compose.yml").read_text())


def test_simulation_has_every_organisation_the_directory_and_caddy(tmp_path):
    out, c = stack(tmp_path, simulation=True)
    apps = [s for s in c["services"] if s.endswith("-app")]
    assert len(apps) == 12 and "directory" in c["services"] and "caddy" in c["services"]
    assert c["services"]["shop-delhi-app"]["environment"]["ASALI_MODE"] == "simulation"
    assert "tls" not in (out / "Caddyfile").read_text()


def test_a_pc_stack_holds_only_that_pcs_organisations(tmp_path):
    _, c = stack(tmp_path, pc="PC-C", directory_url="https://10.0.0.1:8400")
    assert sorted(s for s in c["services"] if s.endswith("-app")) == [
        "dist-north-app",
        "dist-south-app",
        "dist-west-app",
    ]
    assert "directory" not in c["services"]
    env = c["services"]["dist-north-app"]["environment"]
    assert (
        env["DIRECTORY_URL"] == "https://10.0.0.1:8400" and env["PUBLIC_BASE_URL"] == "https://10.0.0.7:8101"
    )
    assert env["ASALI_MODE"] == "network" and env["SSL_CERT_FILE"] == "/certs/rootCA.pem"


def test_people_pc_runs_the_directory(tmp_path):
    _, c = stack(tmp_path, pc="PC-A")
    assert "directory" in c["services"] and "regulator-app" in c["services"]


def test_only_caddy_publishes_ports_and_memory_limits_are_set(tmp_path):
    _, c = stack(tmp_path, simulation=True)
    published = [name for name, s in c["services"].items() if "ports" in s]
    assert published == ["caddy"]
    assert (
        c["services"]["tarang-app"]["mem_limit"] == "384m"
        and c["services"]["tarang-db"]["mem_limit"] == "256m"
    )
    assert c["services"]["medivra-db"]["mem_limit"] == "512m" and c["services"]["caddy"]["mem_limit"] == "64m"
    assert (
        "kesar-db" not in c["services"] and "kesar-data" in c["volumes"]
    )  # SQLite lives in the app's volume


def test_engine_images_and_flags(tmp_path):
    _, c = stack(tmp_path, simulation=True)
    assert c["services"]["tarang-db"]["image"] == "postgres:16-alpine"
    assert (
        c["services"]["medivra-db"]["image"] == "mongo:7"
        and "--auth" in c["services"]["medivra-db"]["command"]
    )
    assert "0.25" in c["services"]["medivra-db"]["command"]


def test_no_password_or_token_is_written_into_compose(tmp_path):
    out, c = stack(tmp_path, simulation=True)
    text = (out / "compose.yml").read_text()
    env = ms.load_env(out / ".env")
    for k, v in env.items():
        if k.endswith(("PASSWORD", "TOKEN")):
            assert v not in text, k
    assert "${TARANG_RW_PASSWORD}" in text


def test_passwords_are_kept_on_a_second_run(tmp_path):
    out, _ = stack(tmp_path, pc="PC-B")
    first = ms.load_env(out / ".env")
    out, _ = stack(tmp_path, pc="PC-B")
    assert ms.load_env(out / ".env") == first and first["TARANG_RW_PASSWORD"] != first["MEDIVRA_RW_PASSWORD"]


def test_database_init_scripts_make_a_read_only_account(tmp_path):
    out, _ = stack(tmp_path, simulation=True)
    sql = (out / "init" / "tarang.sql").read_text()
    assert "CREATE ROLE share_ro" in sql and "GRANT SELECT ON TABLES TO share_ro" in sql and "${" not in sql
    js = (out / "init" / "medivra.js").read_text()
    assert 'role: "read"' in js and "${" not in js
    assert not (out / "init" / "kesar.sql").exists()


def test_a_pc_that_hosts_nothing_is_refused(tmp_path):
    with pytest.raises(SystemExit):
        ms.generate("PC-Z", "1.2.3.4", None, False, tmp_path, NET)
