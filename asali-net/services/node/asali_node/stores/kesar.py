"""Kesar Biologics: SQLite, legacy ERP schema. See schemas/kesar/MAPPING.md."""

import calendar
import re
from datetime import date, datetime

from asali_node.canonical import (
    IST,
    Batch,
    Event,
    NewBatch,
    NewProduct,
    NewShipment,
    Product,
    Shipment,
    StockLine,
    UnitRef,
    UnitView,
)  # fmt: skip
from asali_node.stores.sqlbase import new_id, to_ist
from asali_node.stores.sqlcommon import SqlStore, batch_from, chunks, in_clause, product_from, view

FORM_CODE = {"tablet": "TAB", "capsule": "CAP", "injection": "INJ", "syrup": "SYR", "other": "OTH"}
FORM_NAME = {v: k for k, v in FORM_CODE.items()}
LOT_STATUS = {"A": "released", "Q": "quarantine", "R": "recalled"}
LOT_CODE = {v: k for k, v in LOT_STATUS.items()}
STAMP = "%d/%m/%Y %H:%M:%S"


def stamp(d: datetime) -> str:
    return to_ist(d).strftime(STAMP)


def unstamp(s: str) -> datetime:
    return datetime.strptime(s, STAMP).replace(tzinfo=IST)


def month_end(mm_yyyy: str) -> date:
    m, y = mm_yyyy.split("/")
    return date(int(y), int(m), calendar.monthrange(int(y), int(m))[1])


def storage_text(lo: float | None, hi: float | None) -> str:
    def n(x: float) -> str:
        return str(int(x)) if x == int(x) else str(x)

    if lo is not None and hi is not None:
        return f"{n(lo)}-{n(hi)} C"
    if hi is not None:
        return f"BELOW {n(hi)} C"
    if lo is not None:
        raise ValueError("Kesar's storage text cannot say 'only a minimum'")
    return ""


def storage_parse(s: str) -> tuple[float | None, float | None]:
    if s == "":
        return None, None
    if m := re.fullmatch(r"(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?) C", s):
        return float(m[1]), float(m[2])
    if m := re.fullmatch(r"BELOW (\d+(?:\.\d+)?) C", s):
        return None, float(m[1])
    raise ValueError(f"unknown storage text {s!r}")


def _status(code: str) -> str:
    table = {"C": "commissioned", "D": "dispatched", "X": "destroyed"}
    if code not in table:
        raise ValueError(f"unknown serial status {code!r}")
    return table[code]


class KesarStore(SqlStore):
    ORG = "kesar"
    CONTEXT_ROOTS = (("SRL_MST", "SRL_NO", "serial"), ("DSP_DTL", "SRL_NO", "serial"))
    STAFF = ("USR_MST", "USR_ID", "PWD_HASH", "USR_ROLE", "USR_NM")
    CORR = ("SCN_CORR", "CORR_TS", "RAW_TXT", "FLD", "CHOSEN_VAL", "COST", "CONF_BY")
    DOCLNK = ("DOC_LNK", "DOC_ID", "ENT_TYPE", "ENT_KEY", "CONF", "LNK_TS")

    # ---- catalogue ----
    def add_product(self, p: NewProduct) -> Product:
        n = int(self.db.rows("SELECT COUNT(*) FROM ITEM_MST")[0][0]) + 1
        uom = f"{FORM_CODE[p.form]}/{p.pack_size}"
        self.db.run(
            "INSERT INTO ITEM_MST (ITEM_CD, GTIN, ITEM_DESC, MOL_DESC, STR, UOM, STOR_TEMP_TXT) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            f"KB{n:04d}", p.gtin, p.brand, p.generic, p.strength, uom,
            storage_text(p.storage_min_c, p.storage_max_c),
        )  # fmt: skip
        return next(x for x in self.products() if x.gtin == p.gtin)

    def products(self) -> list[Product]:
        out = []
        for gtin, brand, mol, strength, uom, stor in self.db.rows(
            "SELECT GTIN, ITEM_DESC, MOL_DESC, STR, UOM, STOR_TEMP_TXT FROM ITEM_MST ORDER BY ITEM_CD"
        ):
            code, pack = uom.split("/")
            lo, hi = storage_parse(stor)
            out.append(product_from(gtin, brand, mol, strength, FORM_NAME[code], int(pack), lo, hi, self.ORG))
        return out

    def create_batch(self, b: NewBatch) -> Batch:
        item = self.db.rows("SELECT ITEM_CD FROM ITEM_MST WHERE GTIN = ?", b.gtin)
        if not item:
            raise ValueError(f"unknown product {b.gtin}")
        self.db.run(
            "INSERT INTO LOT_MST (LOT_NO, ITEM_CD, MFG_DT, EXP_DT, LOT_STAT) VALUES (?, ?, ?, ?, 'A')",
            b.lot, item[0][0], b.mfg_date.strftime("%d/%m/%Y"), b.expiry_date.strftime("%m/%Y"),
        )  # fmt: skip
        return next(x for x in self.batches(b.gtin) if x.lot == b.lot)

    def batches(self, gtin: str | None = None) -> list[Batch]:
        sql = ("SELECT i.GTIN, l.LOT_NO, l.MFG_DT, l.EXP_DT, l.LOT_STAT FROM LOT_MST l "
               "JOIN ITEM_MST i ON i.ITEM_CD = l.ITEM_CD")  # fmt: skip
        rows = self.db.rows(sql + (" WHERE i.GTIN = ?" if gtin else "") + " ORDER BY l.LOT_NO",
                            *([gtin] if gtin else []))  # fmt: skip
        return [
            batch_from(g, lot, datetime.strptime(m, "%d/%m/%Y").date(), month_end(e), LOT_STATUS[s], self.ORG)
            for g, lot, m, e, s in rows
        ]

    # ---- serials ----
    def commission_units(self, gtin: str, lot: str, serials: list[str], at: datetime) -> int:
        ok = self.db.rows(
            "SELECT 1 FROM LOT_MST l JOIN ITEM_MST i ON i.ITEM_CD = l.ITEM_CD WHERE l.LOT_NO = ? AND i.GTIN = ?",
            lot, gtin,
        )  # fmt: skip
        if not ok:
            raise ValueError(f"lot {lot} does not belong to {gtin}")
        with self.db.tx() as tx:
            for s in serials:
                tx.run("INSERT INTO SRL_MST (SRL_NO, LOT_NO, SRL_STAT, CRT_TS) VALUES (?, ?, 'C', ?)",
                       s, lot, stamp(at))  # fmt: skip
        return len(serials)

    def _party(self, tx, org_id: str) -> str:  # type: ignore[no-untyped-def]
        rows = tx.rows("SELECT PARTY_CD FROM PARTY_MST WHERE NET_ORG_ID = ?", org_id)
        if rows:
            return str(rows[0][0])
        n = int(tx.rows("SELECT COUNT(*) FROM PARTY_MST")[0][0]) + 1
        code = f"P{n:03d}"
        tx.run(
            "INSERT INTO PARTY_MST (PARTY_CD, PARTY_NM, NET_ORG_ID) VALUES (?, ?, ?)", code, org_id, org_id
        )
        return code

    def record_shipment(self, s: NewShipment) -> Shipment:
        with self.db.tx() as tx:
            for u in s.units:
                st = tx.rows("SELECT SRL_STAT FROM SRL_MST WHERE SRL_NO = ?", u.serial)
                if not st or st[0][0] != "C":
                    raise ValueError(f"{u.serial} is not in stock to ship")
            party = self._party(tx, s.to_org)
            tx.run("INSERT INTO DSP_HDR (DSP_NO, PARTY_CD, DSP_DT, TRUCK_NO) VALUES (?, ?, ?, ?)",
                   s.shipment_id, party, stamp(s.at), s.vehicle_no)  # fmt: skip
            for u in s.units:
                tx.run("INSERT INTO DSP_DTL (DSP_NO, SRL_NO) VALUES (?, ?)", s.shipment_id, u.serial)
                tx.run("UPDATE SRL_MST SET SRL_STAT = 'D' WHERE SRL_NO = ?", u.serial)
        return self._shipment(s.shipment_id, s.to_org, s.at)

    def recall_batch(self, gtin: str, lot: str, reason: str, level: str, at: datetime) -> None:
        with self.db.tx() as tx:
            tx.run("INSERT INTO RCL_REG (RCL_NO, LOT_NO, RCL_RSN, RCL_DT) VALUES (?, ?, ?, ?)",
                   new_id("RC"), lot, f"{level}: {reason}", stamp(at))  # fmt: skip
            tx.run("UPDATE LOT_MST SET LOT_STAT = 'R' WHERE LOT_NO = ?", lot)

    # ---- reading ----
    def unit_view(self, gtin: str, serial: str) -> UnitView:
        rows = self.db.rows(
            "SELECT s.SRL_STAT, s.CRT_TS, l.LOT_NO, l.EXP_DT FROM SRL_MST s "
            "JOIN LOT_MST l ON l.LOT_NO = s.LOT_NO JOIN ITEM_MST i ON i.ITEM_CD = l.ITEM_CD "
            "WHERE s.SRL_NO = ? AND i.GTIN = ?", serial, gtin,
        )  # fmt: skip
        if not rows:
            return view(gtin, serial, [], "never_held")
        stat, crt, lot, exp = rows[0]
        events = [Event(event_id=f"kesar:C:{serial}", org_id=self.ORG, event_type="commission",
                        at=unstamp(crt), gtin=gtin, serial=serial, lot=lot, city=self.city)]  # fmt: skip
        for dsp, dt, net in self.db.rows(
            "SELECT h.DSP_NO, h.DSP_DT, p.NET_ORG_ID FROM DSP_DTL d JOIN DSP_HDR h ON h.DSP_NO = d.DSP_NO "
            "JOIN PARTY_MST p ON p.PARTY_CD = h.PARTY_CD WHERE d.SRL_NO = ?", serial,
        ):  # fmt: skip
            events.append(Event(event_id=f"kesar:D:{dsp}:{serial}", org_id=self.ORG, event_type="ship",
                                at=unstamp(dt), gtin=gtin, serial=serial, lot=lot, to_org=net, ref=dsp,
                                city=self.city))  # fmt: skip
        status = {"commissioned": "in_stock", "dispatched": "shipped", "destroyed": "destroyed"}[
            _status(stat)
        ]
        return view(gtin, serial, events, status, lot, month_end(exp))

    def existing_serials(self, gtin: str | None, serials: list[str]) -> set[str]:
        found: set[str] = set()
        for part in chunks(serials):
            sql = ("SELECT s.SRL_NO FROM SRL_MST s JOIN LOT_MST l ON l.LOT_NO = s.LOT_NO "
                   "JOIN ITEM_MST i ON i.ITEM_CD = l.ITEM_CD "
                   f"WHERE s.SRL_NO IN {in_clause(len(part))}")  # fmt: skip
            args: list[str] = list(part)
            if gtin:
                sql += " AND i.GTIN = ?"
                args.append(gtin)
            found |= {r[0] for r in self.db.rows(sql, *args)}
        return found

    def _units_of(self, dsp: str) -> list[UnitRef]:
        rows = self.db.rows(
            "SELECT i.GTIN, d.SRL_NO, l.LOT_NO, l.EXP_DT FROM DSP_DTL d JOIN SRL_MST s ON s.SRL_NO = d.SRL_NO "
            "JOIN LOT_MST l ON l.LOT_NO = s.LOT_NO JOIN ITEM_MST i ON i.ITEM_CD = l.ITEM_CD "
            "WHERE d.DSP_NO = ? ORDER BY d.SRL_NO", dsp,
        )  # fmt: skip
        return [UnitRef(gtin=g, serial=s, lot=lot, expiry=month_end(e)) for g, s, lot, e in rows]

    def _shipment(self, dsp: str, to_org: str, at: datetime) -> Shipment:
        return Shipment(
            shipment_id=dsp, from_org=self.ORG, to_org=to_org, at=to_ist(at), units=self._units_of(dsp)
        )

    def shipments_to(self, org_id: str, since: datetime | None = None) -> list[Shipment]:
        out = []
        for dsp, dt in self.db.rows(
            "SELECT h.DSP_NO, h.DSP_DT FROM DSP_HDR h JOIN PARTY_MST p ON p.PARTY_CD = h.PARTY_CD "
            "WHERE p.NET_ORG_ID = ?", org_id,
        ):  # fmt: skip
            at = unstamp(dt)
            if since is None or at >= since:
                out.append(self._shipment(dsp, org_id, at))
        return sorted(out, key=lambda s: s.at)

    def stock(self) -> list[StockLine]:
        rows = self.db.rows(
            "SELECT i.GTIN, s.SRL_NO, l.LOT_NO, l.EXP_DT, s.CRT_TS FROM SRL_MST s "
            "JOIN LOT_MST l ON l.LOT_NO = s.LOT_NO JOIN ITEM_MST i ON i.ITEM_CD = l.ITEM_CD "
            "WHERE s.SRL_STAT = 'C' ORDER BY s.SRL_NO"
        )  # fmt: skip
        return [
            StockLine(gtin=g, serial=s, lot=lot, expiry=month_end(e), since=unstamp(t))
            for g, s, lot, e, t in rows
        ]
