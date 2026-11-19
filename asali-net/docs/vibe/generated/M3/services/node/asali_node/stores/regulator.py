"""State and Central Drug Control: PostgreSQL. See schemas/regulator/MAPPING.md."""

from asali_node.canonical import Alert, Licence, NewAlert, NewInspection
from asali_node.stores.sqlbase import new_id, to_date, to_ist
from asali_node.stores.sqlcommon import SqlStore


def _states(text: str | None) -> list[str] | None:
    return None if text is None else [s for s in text.split(",") if s]


class RegulatorStore(SqlStore):
    ENGINE = "pg"
    ORG = "regulator"

    def add_alert(self, a: NewAlert) -> Alert:
        aid = new_id("AL")
        states = None if a.states is None else "," + ",".join(a.states) + ","
        self.db.run(
            "INSERT INTO alerts (alert_id, kind, gtin, lot, manufacturer_org, issued_at, reason, doc_id, states) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            aid, a.kind, a.gtin, a.lot, a.manufacturer_org, a.issued_at, a.reason, a.doc_id, states,
        )  # fmt: skip
        return Alert(alert_id=aid, kind=a.kind, gtin=a.gtin, lot=a.lot, manufacturer_org=a.manufacturer_org,
                     issued_at=to_ist(a.issued_at), reason=a.reason, doc_id=a.doc_id, states=a.states)  # fmt: skip

    def alerts(self, gtin: str | None = None, lot: str | None = None, state: str | None = None) -> list[Alert]:
        where, args = [], []
        if gtin:
            where.append("gtin = ?")
            args.append(gtin)
        if lot:  # an alert with no lot covers every lot of the product
            where.append("(lot = ? OR lot IS NULL)")
            args.append(lot)
        if state:
            where.append("(states IS NULL OR states LIKE ?)")
            args.append(f"%,{state},%")
        sql = "SELECT alert_id, kind, gtin, lot, manufacturer_org, issued_at, reason, doc_id, states FROM alerts"
        if where:
            sql += " WHERE " + " AND ".join(where)
        rows = self.db.rows(sql + " ORDER BY issued_at DESC, alert_id", *args)
        return [
            Alert(alert_id=i, kind=k, gtin=g, lot=lot_, manufacturer_org=m, issued_at=to_ist(at), reason=r,
                  doc_id=d, states=_states(st))
            for i, k, g, lot_, m, at, r, d, st in rows
        ]  # fmt: skip

    def set_licence(self, lic: Licence) -> None:
        self.db.run(
            "INSERT INTO licences (org_id, licence_no, licence_type, valid_from, valid_to, status) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (org_id) DO UPDATE SET licence_no = EXCLUDED.licence_no, "
            "licence_type = EXCLUDED.licence_type, valid_from = EXCLUDED.valid_from, valid_to = EXCLUDED.valid_to, "
            "status = EXCLUDED.status",
            lic.org_id, lic.licence_no, lic.licence_type, lic.valid_from, lic.valid_to, lic.status,
        )  # fmt: skip

    def licences(self, org_ids: list[str] | None = None) -> list[Licence]:
        sql = "SELECT org_id, licence_no, licence_type, valid_from, valid_to, status FROM licences"
        args: list[str] = []
        if org_ids is not None:
            if not org_ids:
                return []
            sql += " WHERE org_id IN (" + ",".join("?" * len(org_ids)) + ")"
            args = list(org_ids)
        rows = self.db.rows(sql + " ORDER BY org_id", *args)
        return [
            Licence(org_id=o, licence_no=n, licence_type=t, valid_from=to_date(f), valid_to=to_date(v), status=s)
            for o, n, t, f, v, s in rows
        ]  # fmt: skip

    def add_inspection(self, i: NewInspection) -> None:
        self.db.run(
            "INSERT INTO inspections (inspection_id, org_id, inspected_at, outcome, doc_id) VALUES (?, ?, ?, ?, ?)",
            new_id("INS"), i.org_id, i.inspected_at, i.outcome, i.doc_id,
        )  # fmt: skip
