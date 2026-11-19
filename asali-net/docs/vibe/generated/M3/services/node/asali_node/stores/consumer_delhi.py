"""Consumer node, Delhi: SQLite. Records every check and problem report. See schemas/consumer-delhi/MAPPING.md."""

import json
from datetime import datetime

from asali_node.canonical import CityCount, NewCheck, NewReport, ReportRecord, ScanStat
from asali_node.stores.sqlbase import new_id, to_ist
from asali_node.stores.sqlcommon import SqlStore


def minute(d: datetime) -> datetime:
    """Public scan statistics never show anything finer than the minute."""
    return to_ist(d).replace(second=0, microsecond=0)


def build_stat(gtin: str, serial: str, rows: list[tuple[str, datetime]]) -> ScanStat:
    by: dict[str, list[datetime]] = {}
    for city, at in rows:
        by.setdefault(city, []).append(at)
    cities = [
        CityCount(city=c, count=len(v), first_at=minute(min(v)), last_at=minute(max(v))) for c, v in by.items()
    ]
    cities.sort(key=lambda c: (-c.count, c.city))
    return ScanStat(gtin=gtin, serial=serial, total=len(rows), by_city=cities)


class ConsumerDelhiStore(SqlStore):
    ORG = "consumer-delhi"

    def record_check(self, c: NewCheck) -> str:
        cid = new_id("chk_")
        self.db.run(
            "INSERT INTO checks (check_id, raw_input, gtin, serial, verdict, reasons_json, city, at, device_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            cid, c.raw_input, c.gtin, c.serial, c.verdict, json.dumps(c.reasons), c.city, c.at, c.device_hash,
        )  # fmt: skip
        return cid

    def record_report(self, r: NewReport) -> str:
        rid = new_id("rep_")
        self.db.run(
            "INSERT INTO reports (report_id, check_id, doc_id, gtin, serial, city, at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            rid, r.check_id, r.doc_id, r.gtin, r.serial, r.city, r.at,
        )  # fmt: skip
        return rid

    def scan_stat(self, gtin: str, serial: str) -> ScanStat:
        rows = self.db.rows("SELECT city, at FROM checks WHERE gtin = ? AND serial = ?", gtin, serial)
        return build_stat(gtin, serial, [(city, to_ist(at)) for city, at in rows])

    def reports(self, since: datetime | None = None) -> list[ReportRecord]:
        rows = self.db.rows("SELECT report_id, doc_id, gtin, serial, city, at FROM reports ORDER BY at, report_id")
        out = [
            ReportRecord(report_id=i, doc_id=d, gtin=g, serial=s, city=c, at=to_ist(a))
            for i, d, g, s, c, a in rows
        ]
        return [r for r in out if since is None or r.at >= since]
