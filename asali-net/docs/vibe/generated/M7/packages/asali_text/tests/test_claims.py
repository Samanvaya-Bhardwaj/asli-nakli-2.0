from asali_text.claims import KIND, extract_claims, minutes_above
from asali_text.gazetteer import Gazetteer, ProductName
from asali_text.mentions import extract

GAZ = Gazetteer(
    products=(ProductName("08901003000111", "Glargikes", "insulin glargine", "100 IU/ml"),),
    orgs={"shop-delhi": "Sharma Medicos", "kesar": "Kesar Biologics", "dist-north": "North Star Distributors"},
)


def claims(doc_type, text):
    return {c["name"]: c["value"] for c in extract_claims(doc_type, text, extract(text, GAZ))}


def test_complaint_claims_where_who_when_and_what_was_printed():
    c = claims("consumer_complaint", "Maine 3 Nov ko Sharma Medicos Delhi se Glargikes liya. Batch K/24/0091, expiry 08/2026.")
    assert c == {"purchase_city": "Delhi", "purchase_shop": "shop-delhi", "purchase_date": "2026-11-03",
                 "stated_expiry": "2026-08", "stated_lot": "K/24/0091"}  # fmt: skip


def test_temperature_report_claims_and_minutes_above_the_limit():
    text = ("Shipment DSP-N-0042 (North Star Distributors to Sharma Medicos). Logger TL-22.\n"
            "12/11 09:10  6.1 C\n12/11 11:40  13.8 C\n12/11 14:30  14.2 C\n"
            "Reefer unit failed. Temperature above 8 C for about 3 h 20 min.")  # fmt: skip
    c = claims("temperature_report", text)
    assert c["shipment_ref"] == "DSP-N-0042" and c["max_temp_c"] == 14.2 and c["stated_minutes"] == 200
    assert len(c["readings"]) == 3
    assert minutes_above(c["readings"], 8, c["stated_minutes"]) == 170  # 11:40 to 14:30, from the readings
    assert minutes_above([], 8, 200) == 200  # no readings: the stated duration
    assert minutes_above([{"minute": 1, "temp_c": 5.0}, {"minute": 60, "temp_c": 6.0}], 8, None) == 0


def test_nsq_alert_has_one_claim_group_per_row():
    text = ("Drugs declared not of standard quality, October 2026.\n"
            "1. Glargikes Injection | B.No. K/24/0091 | Mfd by Kesar Biologics | Dissolution failed\n"
            "2. Other Tablets | B.No. TP24A017 | Mfd by Somewhere Else | Assay low")  # fmt: skip
    rows = [c["value"] for c in extract_claims("nsq_alert", text, extract(text, GAZ))]
    assert rows[0] == {"lot": "K/24/0091", "manufacturer": "kesar", "reason": "Dissolution failed"}
    assert rows[1]["lot"] == "TP24A017" and rows[1]["manufacturer"] is None


def test_coa_result_and_failed_tests():
    assert claims("coa", "Certificate of analysis. Batch K/24/0091. Assay 99.2%. Complies.")["result"] == "pass"
    c = claims("coa", "Certificate. Batch K/24/0091. Dissolution failed at 30 min. Does not comply.")
    assert c["result"] == "fail" and c["failed_tests"] == ["dissolution"]


def test_discrepancy_note_counts_and_missing_serials():
    c = claims("discrepancy_note", "Shipment DSP-0042: expected 20, received 18. Missing TPM9-S346-Q37 and tpd2 5vt4 f5h.")
    assert (c["shipment_ref"], c["expected"], c["received"]) == ("DSP-0042", 20, 18)
    assert len(c["missing_serials"]) == 2


def test_inspection_outcomes():
    assert claims("inspection_report", "Inspection of Sharma Medicos. Records in order.")["outcome"] == "satisfactory"
    assert claims("inspection_report", "Inspection of Sharma Medicos. Licence suspended.")["outcome"] == "licence_action"
    assert claims("inspection_report", "Inspection of Sharma Medicos. Three observations noted.")["outcome"] == "observations"


def test_every_type_has_a_kind_and_unknown_types_have_no_claims():
    assert set(KIND.values()) == {"official", "operational", "allegation"} and len(KIND) == 14
    assert extract_claims("delivery_note", "x", []) == []
