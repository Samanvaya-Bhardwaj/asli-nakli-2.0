from datetime import datetime

from asali_node.canonical import IST, DocLink, ScanCorrection, StaffRecord

AT = datetime(2026, 11, 2, 10, 30, tzinfo=IST)


def test_staff_round_trip(env):
    s = env.rw()
    assert s.get_staff("asha") is None
    s.add_staff(StaffRecord(username="asha", password_hash="$2b$12$x", role="admin", display_name="Asha Rao"))
    got = s.get_staff("asha")
    assert got is not None and got.role == "admin" and got.display_name == "Asha Rao"


def test_scan_correction_is_saved(env):
    s = env.rw()
    s.add_scan_correction(
        ScanCorrection(
            at=AT, raw="TPM9S346Q3I", field="serial", chosen="TPM9S346Q31", cost=0.25, confirmed_by="asha"
        )
    )


def test_document_links_replace_and_lookup(env):
    s = env.rw()
    s.upsert_document_links("d1", [DocLink(entity_type="batch", entity_key="G/L1", confidence=0.95, linked_at=AT),
                                   DocLink(entity_type="unit", entity_key="G/S1", confidence=0.7, linked_at=AT)])  # fmt: skip
    s.upsert_document_links(
        "d2", [DocLink(entity_type="batch", entity_key="G/L1", confidence=0.6, linked_at=AT)]
    )
    assert s.documents_linked_to(["G/L1"]) == ["d1", "d2"]
    s.upsert_document_links(
        "d1", [DocLink(entity_type="batch", entity_key="G/L9", confidence=0.9, linked_at=AT)]
    )
    assert s.documents_linked_to(["G/L1"]) == ["d2"]
    assert s.documents_linked_to(["G/S1"]) == []
    assert s.documents_linked_to([]) == []
