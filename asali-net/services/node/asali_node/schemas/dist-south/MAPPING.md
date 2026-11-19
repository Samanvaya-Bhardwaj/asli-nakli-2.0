# Dakshin Pharma Agencies (dist-south): native schema to canonical model

SQLite, inward and outward registers keeping the raw scanned text. Adapter: `stores/dist_south.py`.

| Canonical field | Native field(s) | Conversion | Example |
|---|---|---|---|
| `Event(receive).from_org`, `ref` | `inward.supplier_org`, `dc_number` | as is | `tarang`, `SHP-1` |
| `Event(receive).at`, `Event(ship).at` | `inward.entry_date`, `outward.entry_date` | `YYYY-MM-DD` to midnight IST. The register keeps dates only. | `2026-11-03` |
| `Event(ship).to_org`, `ref` | `outward.customer_org`, `invoice_no` | as is | `shop-delhi` |
| `UnitView.lot`, `expiry` | `inward_lines.lot`, `exp` | `exp` is an ISO date | |
| `UnitView.status_here` | latest inward or outward entry by (date, inward before outward, entry id) | outward is shipped, inward is in_stock | |
| `Shipment.units` | `outward_lines` | `barcode_raw` goes to `UnitRef.raw` | |
| `StockLine` | `inward_lines` with no outward on or after its inward date | `since` is the inward date | |
| `UnitRef.corrected` | `inward_lines.corrected` | 0 or 1 to bool, written on receipt | |

Lossy on purpose: times of day are not kept, so two events on one day are ordered receive first, then ship.
Common tables use this register's style: `users`, `scan_fixes`, `doc_refs`.
