# Western Medilink (dist-west): native schema to canonical model

MongoDB, one event-sourced `movements` collection. Adapter: `stores/dist_west.py`.

| Canonical field | Native field(s) | Conversion | Example |
|---|---|---|---|
| `Event(receive)` | `movements` where `dir = "IN"` | `party` is `from_org`, `ref` is the sender's shipment id, `at` BSON date to IST | |
| `Event(ship)` | `movements` where `dir = "OUT"` | `party` is `to_org`, `ref` is the dispatch id | |
| `UnitView.status_here` | the direction of the unit's latest movement (by `at`, then insertion order) | IN is in_stock, OUT is shipped; no movement is never_held | |
| `Shipment` (to the caller) | `movements` where `dir = "OUT"` and `party = caller` | one `UnitRef` per `items[]` entry (`g` is gtin, `s` is serial) | |
| `StockLine` | all movements replayed in order | serials whose last movement is IN | |
| `UnitView.lot`, `expiry` | not stored | null | |
| `Event.city` | not stored | the node's configured city | `Mumbai` |

Index: `items.s`, so a serial lookup does not scan the collection.
Common collections: `staff`, `scanFixes`, `docLinks`.

## Related tables for Phase 3 (context discovery)

Every organisation's database holds at least four related tables, joined by keys, so that what is known about a pack is spread across them and a database can find context by following its own keys.

- `partners` (org id, kind), `directions` (IN, OUT) and `movementItems` (one document per code in a movement, next to `movements.items`). References: `movements.party`, `movements.dir`, `movementItems.movement`.
- A movement now has a string `_id` (an ObjectId in text form, so it still sorts by time of writing).
