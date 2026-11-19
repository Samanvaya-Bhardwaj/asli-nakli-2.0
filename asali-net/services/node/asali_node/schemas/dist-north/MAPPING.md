# North Star Distributors (dist-north): native schema to canonical model

PostgreSQL, separate receipt and dispatch tables, stock as a view. Adapter: `stores/dist_north.py`.

| Canonical field | Native field(s) | Conversion | Example |
|---|---|---|---|
| `Event(receive).from_org`, `ref`, `at` | `receipts.from_org_id`, `source_ref`, `received_at` joined through `receipt_items` | timestamptz to IST | `tarang`, `SHP-1` |
| `Event(ship).to_org`, `ref`, `at` | `dispatches.to_org_id`, `dispatch_id`, `dispatched_at` joined through `dispatch_items` | timestamptz to IST | `shop-delhi`, `DSP-1` |
| `UnitView.status_here` | latest of the unit's receipt and dispatch times | dispatch at or after the latest receipt is shipped, otherwise in_stock; no rows is never_held | |
| `Shipment` (to the caller) | `dispatches` where `to_org_id = caller` and `dispatch_items` | one `UnitRef` (gtin, serial) per row | |
| `StockLine` | view `stock_now` | received serials that no later dispatch covers; `since` is the receipt time | |
| `UnitView.lot`, `expiry`, `UnitRef.lot` | not stored | null. The issuer holds lot and expiry. | |
| `Event.city` | not stored | the node's configured city | `Delhi` |

Not kept: the raw scan text and whether a code was corrected. `received_by` is stored in `receipts.received_by`.
