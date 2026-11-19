import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import network_model as nm


def raw():
    return yaml.safe_load(nm.NETWORK_YAML.read_text(encoding="utf-8"))


def test_the_committed_network_loads_with_twelve_orgs_on_four_pcs():
    net = nm.load()
    assert len(net.orgs) == 12 and set(net.pcs) == {"PC-A", "PC-B", "PC-C", "PC-D"}
    assert {k: len(net.on_pc(k)) for k in net.pcs} == {"PC-A": 3, "PC-B": 3, "PC-C": 3, "PC-D": 3}


def test_ports_are_unique_and_follow_the_plan():
    net = nm.load()
    assert net.directory.port == 8400
    assert net.orgs["dist-north"].port == 8101 and net.orgs["shop-delhi"].port == 8201
    assert net.orgs["tarang"].port == 8301 and net.orgs["consumer-mumbai"].port == 8403


def test_engines_are_mixed_the_way_the_plan_says():
    net = nm.load()
    engines = {k: v.engine for k, v in net.orgs.items()}
    assert engines["tarang"] == "postgres" and engines["medivra"] == "mongo" and engines["kesar"] == "sqlite"
    assert {v for v in engines.values()} == {"postgres", "mongo", "sqlite"}


def test_issuer_codes_use_only_the_code_alphabet():
    codes = {o.issuer_code for o in nm.load().orgs.values() if o.issuer_code}
    assert codes == {"TP", "MV", "KS"} and all(set(c) <= nm.CROCKFORD for c in codes)


def test_no_ip_address_or_secret_appears_in_the_file():
    import re

    text = nm.NETWORK_YAML.read_text(encoding="utf-8")
    assert not re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", text)
    assert "password" not in text.lower() and "token" not in text.lower()


@pytest.mark.parametrize(
    "change, message",
    [
        (lambda d: d["orgs"]["tarang"].update(port=8302), "share a port"),
        (lambda d: d["orgs"]["tarang"].update(pc="PC-Z"), "unknown PC"),
        (lambda d: d["orgs"]["tarang"].update(issuer_code="MV"), "unique"),
        (lambda d: d["orgs"]["tarang"].update(issuer_code="TO"), "alphabet"),
        (lambda d: d["orgs"]["shop-delhi"].pop("shop"), "location settings"),
        (lambda d: d["orgs"]["dist-north"].update(served_states=[]), "served states"),
    ],
)
def test_bad_networks_are_refused(change, message):
    d = raw()
    change(d)
    with pytest.raises(ValueError, match=message):
        nm.Network.model_validate(d)
