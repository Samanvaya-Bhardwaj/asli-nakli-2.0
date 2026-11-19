"""Notices the system writes itself when something happens (TEXT_ML.md 3): a recall, an alert, a short delivery."""

from datetime import datetime

from asali_node.canonical import Alert


def _day(at: datetime) -> str:
    return f"{at.day} {at:%b %Y}"


def recall_notice(
    maker: str, product: str, strength: str, lot: str, reason: str, level: str, at: datetime
) -> str:
    return (
        f"RECALL NOTICE\n{maker} is recalling {product} {strength}, lot {lot}.\nReason: {reason}.\nLevel: {level}.\n"
        f"Date: {_day(at)}.\nShops should stop selling this lot and return stock. Patients should not take it."
    )


def regulator_notice(alert: Alert, maker_name: str) -> tuple[str, str]:
    """The document type and text for an alert. An alert without a lot has no notice to write."""
    row = f"1. GTIN {alert.gtin} | B.No. {alert.lot} | Mfd by {maker_name} | {alert.reason}"
    if alert.kind == "nsq":
        return "nsq_alert", f"Drugs declared not of standard quality, {alert.issued_at:%B %Y}.\n{row}"
    if alert.kind == "recall":
        return (
            "recall_notice",
            f"RECALL NOTICE\nBatch {alert.lot} made by {maker_name} (GTIN {alert.gtin}) is recalled.\nReason: {alert.reason}.\nDate: {_day(alert.issued_at)}.",
        )
    return (
        "ban_order",
        f"BAN ORDER\nProduct GTIN {alert.gtin}, batch {alert.lot}, made by {maker_name}.\nGround: {alert.reason}.\nDate: {_day(alert.issued_at)}.",
    )


def discrepancy_note(org_name: str, ref: str, expected: int, received: int, missing: list[str]) -> str:
    return f"Discrepancy note. Shipment {ref}: expected {expected}, received {received}. Missing packs: {', '.join(missing)}. Recorded by {org_name}."
