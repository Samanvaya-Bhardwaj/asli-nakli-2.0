import sqlite3

import pytest
from asali_node.vault.sqlite_vault import Vault


def doc(i, body, doc_type="consumer_complaint", at=1000):
    return {"id": f"d{i}", "org_id": "consumer-delhi", "doc_type": doc_type, "kind": "allegation", "title": f"t{i}",
            "body": body, "language": "en", "created_at": at + i, "issue_labels": ["no_effect"]}  # fmt: skip


@pytest.fixture
def vault(tmp_path):
    v = Vault(tmp_path)
    v.put(
        doc(1, "Strip colour looks different from last time"),
        [{"entity_key": "batch:G/L1", "entity_type": "batch", "confidence": 0.9, "because": ["exact lot"]}],
        "orig 1",
    )
    v.put(
        doc(2, "Temperature above 8 C for three hours", "temperature_report"),
        [{"entity_key": "shipment:dist-north/DSP-1", "entity_type": "shipment", "confidence": 0.95}],
    )
    v.put(doc(3, "Customer says tablets smell odd"), [])
    return v


def test_linked_lookup_and_text_search(vault):
    assert [d["id"] for d in vault.search(link_keys=["batch:G/L1"])] == ["d1"]
    assert [d["id"] for d in vault.search(q="temperature above")] == ["d2"]
    assert [d["id"] for d in vault.search(q="colour", doc_types=["consumer_complaint"])] == ["d1"]
    assert vault.search(q="colour", doc_types=["coa"]) == []
    assert [d["id"] for d in vault.search(since=1002)] == ["d3", "d2"]  # newest first


def test_the_original_text_is_kept_and_a_link_can_be_rejected(vault):
    assert (vault.dir / "text" / "d1.txt").read_text() == "orig 1"
    d = vault.get("d1")
    assert d["links"][0]["because"] == ["exact lot"] and d["issue_labels"] == ["no_effect"]
    assert vault.reject_link("d1", "batch:G/L1") is True
    assert vault.get("d1")["links"] == [] and vault.search(link_keys=["batch:G/L1"]) == []


def test_unlinked_documents_are_the_ones_without_a_link_at_08(vault):
    assert {d["id"] for d in vault.unlinked(0)} == {"d3"}
    assert {d["id"] for d in vault.listing(linked=True)} == {"d1", "d2"}


def test_the_read_only_vault_can_search_but_not_write(vault, tmp_path):
    ro = Vault(tmp_path, "ro")
    assert [d["id"] for d in ro.search(q="smell")] == ["d3"]
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        ro.put(doc(9, "x"), [])
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        ro.reject_link("d1", "batch:G/L1")


def test_odd_search_text_does_not_break_the_query(vault):
    assert vault.search(q='"; DROP TABLE docs; --') == []
    assert vault.count() == 3
