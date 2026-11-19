import asyncio

import pytest
from asali_node.network.client import SourceUnavailable
from asali_node.verify.engine import verify_pack
from asali_node.verify.trace import Tracer
from builders import CITY, G, LOT, NAMES, S, TODAY, edit, ev, normal_chain, hop

pytestmark = pytest.mark.anyio

ORGS = [
    {"org_id": "kesar", "org_type": "pharma", "name": NAMES["kesar"], "city": "Pune", "issuer_code": "KS", "host_name": "PC-B"},
    {"org_id": "dist-south", "org_type": "distributor", "name": NAMES["dist-south"], "city": "Bengaluru", "host_name": "PC-C"},
    {"org_id": "shop-delhi", "org_type": "shop", "name": NAMES["shop-delhi"], "city": "Delhi", "host_name": "PC-D"},
    {"org_id": "shop-mumbai", "org_type": "shop", "name": NAMES["shop-mumbai"], "city": "Mumbai", "host_name": "PC-D"},
    {"org_id": "regulator", "org_type": "regulator", "name": NAMES["regulator"], "city": "Delhi", "host_name": "PC-A"},
    {"org_id": "consumer-delhi", "org_type": "consumer", "name": "Asali Check", "city": "Delhi", "host_name": "PC-A"},
]  # fmt: skip


@pytest.fixture
def anyio_backend():
    return "asyncio"


class Net:
    """Canned answers by (org, path prefix). Anything not listed is unreachable. `slow` orgs answer too late."""

    def __init__(self, chain=None, down=(), slow=()):
        self.down, self.slow = set(down), set(slow)
        self.answers: dict[tuple[str, str], dict] = {}
        for h in chain or normal_chain():
            self.put_view(h)
        prod = {"gtin": G, "brand": "Glargikes", "generic": "insulin glargine", "strength": "100 IU/ml", "form": "injection",
                "pack_size": 1, "storage_min_c": 2, "storage_max_c": 8, "owner_org": "kesar"}  # fmt: skip
        self.answers[("kesar", "/share/v1/products")] = {"products": [prod]}
        self.answers[("kesar", "/share/v1/batches")] = {"batches": [{"gtin": G, "lot": LOT, "mfg_date": "2026-10-01", "expiry_date": "2027-03-31", "status": "released", "owner_org": "kesar"}]}  # fmt: skip
        self.answers[("regulator", "/share/v1/alerts")] = {"alerts": []}
        self.answers[("regulator", "/share/v1/licences")] = {"licences": []}
        self.answers[("consumer-delhi", f"/share/v1/scans/{G}/{S}")] = {"gtin": G, "serial": S, "total": 0, "by_city": []}
        empty = {"gtin": G, "serial": S, "known": False, "lot": None, "expiry": None, "status_here": "never_held", "events": []}
        for shop in ("shop-delhi", "shop-mumbai"):
            self.answers.setdefault((shop, f"/share/v1/units/{G}/{S}"), {**empty, "served_by": {"org_id": shop, "host_name": "PC-D", "at": "2026-11-20T10:00:00+05:30"}})

    def put_view(self, h):
        body = h.view.model_dump(mode="json")
        body["served_by"] = {"org_id": h.org_id, "host_name": {"kesar": "PC-B", "dist-south": "PC-C"}.get(h.org_id, "PC-D"), "at": "2026-11-20T10:00:00+05:30"}
        self.answers[(h.org_id, f"/share/v1/units/{G}/{S}")] = body

    async def get(self, org, path, params=None):
        if org in self.slow:
            await asyncio.sleep(5)
        if org in self.down:
            raise SourceUnavailable(org, "unreachable")
        key = (org, path)
        if key not in self.answers:
            raise SourceUnavailable(org, "http_404")
        return self.answers[key]


async def run(net, **kw):
    return await verify_pack(net, ORGS, G, S, mode="simulation", tracer=Tracer(net, ORGS, budget_s=kw.pop("budget", 2.0)), **kw)


async def test_a_three_hop_chain_is_genuine_and_names_each_computer():
    r = await run(Net())
    assert r["verdict"] == "genuine" and r["mode"] == "simulation"
    assert [h["org_id"] for h in r["history"]] == ["kesar", "dist-south", "shop-delhi"]
    assert {h["served_by"]["host_name"] for h in r["history"]} == {"PC-B", "PC-C", "PC-D"}
    assert r["pack"]["lot"] == LOT and r["pack"]["product"]["brand"] == "Glargikes"
    assert {s["org_id"] for s in r["sources"]} >= {"kesar", "dist-south", "shop-delhi", "regulator", "consumer-delhi"}
    assert "sold by Sharma Medicos, Delhi" in r["headline"]


async def test_a_gap_at_the_second_hop_is_cannot_check():
    r = await run(Net(down=["dist-south"]))
    assert r["verdict"] == "cannot_check"
    assert "Dakshin Pharma Agencies did not answer" in r["headline"]
    assert r["history"][1]["unavailable"] == "unreachable"
    assert {"org_id": "dist-south", "status": "unreachable", "ms": r["sources"][0]["ms"], "host_name": "PC-C", "reason": "unreachable"} in r["sources"] or any(s["org_id"] == "dist-south" and s["status"] == "unreachable" for s in r["sources"])


async def test_a_chain_break_is_a_caution():
    shop = normal_chain()[2]
    forged = edit(shop, [ev("shop-delhi", "receive", 5, from_org="dist-south", ref="NOT-SENT"), ev("shop-delhi", "sell", 12, ref="B1")])
    r = await run(Net(chain=[*normal_chain()[:2], forged]))
    assert r["verdict"] == "caution" and [x["code"] for x in r["reasons"]] == ["CHAIN_BREAK"]


async def test_an_unknown_issuer_code_is_not_issued():
    net = Net()
    r = await verify_pack(net, ORGS, G, "ZZ000000000", mode="simulation")
    assert r["verdict"] == "do_not_use" and r["reasons"][0]["code"] == "NOT_ISSUED"


async def test_a_pack_the_issuer_does_not_know_is_not_issued():
    unknown = hop("kesar", "pharma", [], known=False, status="never_held")
    r = await run(Net(chain=[unknown]))
    assert r["verdict"] == "do_not_use" and r["reasons"][0]["code"] == "NOT_ISSUED"


async def test_a_side_query_over_budget_is_marked_and_the_result_still_comes_back():
    r = await run(Net(slow=["consumer-delhi"]), budget=0.3)
    assert r["verdict"] == "genuine"  # consumer scan counts only feed a caution rule
    assert not any(s["org_id"] == "consumer-delhi" and s["status"] == "answered" for s in r["sources"])


async def test_a_slow_shop_means_we_cannot_rule_out_a_copy():
    r = await run(Net(slow=["shop-mumbai"]), budget=0.3)
    assert r["verdict"] == "cannot_check" and "Apna Chemist" in r["headline"]


async def test_the_result_names_the_shop_that_sold_a_copy():
    net = Net()
    mumbai = {"gtin": G, "serial": S, "known": True, "lot": LOT, "expiry": "2027-03-31", "status_here": "sold",
              "events": [ev("shop-mumbai", "receive", 6, from_org="dist-south", ref="FORGED").model_dump(mode="json"),
                         ev("shop-mumbai", "sell", 14, ref="B9").model_dump(mode="json")],
              "served_by": {"org_id": "shop-mumbai", "host_name": "PC-D", "at": "2026-11-20T10:00:00+05:30"}}  # fmt: skip
    net.answers[("shop-mumbai", f"/share/v1/units/{G}/{S}")] = mumbai
    r = await run(net)
    assert r["verdict"] == "do_not_use" and r["reasons"][0]["code"] == "COPIED_CODE"
    assert "Apna Chemist, Mumbai" in r["headline"] and TODAY and CITY
