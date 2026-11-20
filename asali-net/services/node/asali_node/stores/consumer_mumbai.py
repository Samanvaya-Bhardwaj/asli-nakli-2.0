"""Consumer node, Mumbai: MongoDB, scans and reports. See schemas/consumer-mumbai/MAPPING.md."""

from datetime import datetime

from asali_node.canonical import NewCheck, NewReport, ReportRecord, ScanStat
from asali_node.stores.consumer_delhi import build_stat
from asali_node.stores.mongobase import MongoStore
from asali_node.stores.sqlbase import new_id, to_ist
from asali_node.verify.cities import CITY_STATE


class ConsumerMumbaiStore(MongoStore):
    ORG = "consumer-mumbai"
    CONTEXT_COLLECTIONS = ("scans", "reports", "verdicts", "cities", "reasons")
    CONTEXT_REFS = (
        ("reports", "scan", "scans", "_id"), ("scans", "result.verdict", "verdicts", "_id"),
        ("scans", "where.city", "cities", "_id"), ("reasons", "scan", "scans", "_id"), ("reports", "where.city", "cities", "_id"),
    )  # fmt: skip
    CONTEXT_ROOTS = (("scans", "code.sn", "serial"), ("reports", "code.sn", "serial"))

    def _seed(self) -> None:
        for verdict, meaning in (
            ("genuine", "Every record found agrees the pack is genuine"),
            ("caution", "Something does not fit; check with the seller"),
            ("do_not_use", "The records show this pack should not be used"),
            ("cannot_check", "Not enough organisations answered to say"),
        ):
            self._ensure("verdicts", verdict, {"meaning": meaning})

    def _city(self, city: str) -> None:
        self._ensure("cities", city, {"state": CITY_STATE.get(city)})

    def record_check(self, c: NewCheck) -> str:
        cid = new_id("chk_")
        self._city(c.city)
        self.db["scans"].insert_one(
            {"_id": cid, "input": {"raw": c.raw_input}, "code": {"gtin": c.gtin, "sn": c.serial},
             "result": {"verdict": c.verdict, "why": list(c.reasons)}, "where": {"city": c.city}, "when": c.at,
             "device": c.device_hash}
        )  # fmt: skip
        codes = list(dict.fromkeys(c.reasons))
        if codes:
            self.db["reasons"].insert_many(
                [{"_id": f"{cid}/{code}", "scan": cid, "code": code} for code in codes]
            )
        return cid

    def record_report(self, r: NewReport) -> str:
        rid = new_id("rep_")
        self._city(r.city)
        self.db["reports"].insert_one(
            {"_id": rid, "scan": r.check_id, "doc": r.doc_id, "code": {"gtin": r.gtin, "sn": r.serial},
             "where": {"city": r.city}, "when": r.at}
        )  # fmt: skip
        return rid

    def scan_stat(self, gtin: str, serial: str) -> ScanStat:
        rows = [
            (d["where"]["city"], to_ist(d["when"]))
            for d in self.db["scans"].find({"code.gtin": gtin, "code.sn": serial})
        ]
        return build_stat(gtin, serial, rows)

    def raw_inputs(self, gtin: str, serial: str) -> list[dict[str, str]]:
        """What was typed or scanned for this pack, with city and time to the minute. No device information."""
        found = self.db["scans"].find({"code.gtin": gtin, "code.sn": serial}).sort("when", 1)
        return [
            {
                "raw_input": d["input"]["raw"],
                "city": d["where"]["city"],
                "at": to_ist(d["when"]).replace(second=0, microsecond=0).isoformat(),
            }
            for d in found
        ]

    def reports(self, since: datetime | None = None) -> list[ReportRecord]:
        out = [
            ReportRecord(report_id=d["_id"], doc_id=d["doc"], gtin=d["code"]["gtin"], serial=d["code"]["sn"],
                         city=d["where"]["city"], at=to_ist(d["when"]))
            for d in self.db["reports"].find().sort([("when", 1), ("_id", 1)])
        ]  # fmt: skip
        return [r for r in out if since is None or r.at >= since]
