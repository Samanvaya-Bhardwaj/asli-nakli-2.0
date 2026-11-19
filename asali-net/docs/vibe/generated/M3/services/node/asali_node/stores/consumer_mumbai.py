"""Consumer node, Mumbai: MongoDB, scans and reports. See schemas/consumer-mumbai/MAPPING.md."""

from datetime import datetime

from asali_node.canonical import NewCheck, NewReport, ReportRecord, ScanStat
from asali_node.stores.consumer_delhi import build_stat
from asali_node.stores.mongobase import MongoStore
from asali_node.stores.sqlbase import new_id, to_ist


class ConsumerMumbaiStore(MongoStore):
    ORG = "consumer-mumbai"

    def record_check(self, c: NewCheck) -> str:
        cid = new_id("chk_")
        self.db["scans"].insert_one(
            {"_id": cid, "input": {"raw": c.raw_input}, "code": {"gtin": c.gtin, "sn": c.serial},
             "result": {"verdict": c.verdict, "why": list(c.reasons)}, "where": {"city": c.city}, "when": c.at,
             "device": c.device_hash}
        )  # fmt: skip
        return cid

    def record_report(self, r: NewReport) -> str:
        rid = new_id("rep_")
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

    def reports(self, since: datetime | None = None) -> list[ReportRecord]:
        out = [
            ReportRecord(report_id=d["_id"], doc_id=d["doc"], gtin=d["code"]["gtin"], serial=d["code"]["sn"],
                         city=d["where"]["city"], at=to_ist(d["when"]))
            for d in self.db["reports"].find().sort([("when", 1), ("_id", 1)])
        ]  # fmt: skip
        return [r for r in out if since is None or r.at >= since]
