# Sharma Medicos (shop-delhi): native schema to canonical model

SQLite, purchase and sale bills. Adapter: `stores/shop_delhi.py`.

| Canonical field | Native field(s) | Conversion | Example |
|---|---|---|---|
| `Event(receive).from_org`, `ref`, `at` | `purchases.distributor_org`, `bill_no`, `bill_date` | `bill_no` holds the distributor's shipment id; ISO text to IST | `dist-north`, `DSP-1` |
| `Event(sell).ref`, `at` | `sales.bill_no`, `sold_at` through `sale_items` | ISO text to IST | `B-1` |
| `Event(return).ref`, `at` | `returns.bill_no`, `at` | ISO text to IST | |
| `UnitView.status_here` | the unit's latest event (receive, sell, return; ties in that order) | in_stock, sold, returned | |
| `UnitView.lot`, `expiry` | `purchase_items.lot`, `exp` | ISO date | |
| `StockLine` | `purchase_items` with no later sale or return | `since` is `bill_date` | |
| not in the canonical model | `sales.customer_ref_hash`, `sales.total_paise`, `sale_items.mrp_paise`, `returns.reason` | kept in the shop's own database only | |

A shop returns no shipments (`shipments_to` is empty) and raises `NotSupported` for dispatch.
Common tables: `users`, `scan_fixes`, `doc_links`.

## Related tables for Phase 3 (context discovery)

Every organisation's database holds at least four related tables, joined by keys, so that what is known about a pack is spread across them and a database can find context by following its own keys.

- `parties` (org id, kind): `purchases.distributor_org` references it. `returns.bill_no` now references `sales`.
