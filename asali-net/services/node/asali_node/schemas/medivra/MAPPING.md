# Medivra Labs: native schema to canonical model

MongoDB, embedded documents, camelCase. Adapter: `stores/medivra.py`. Validators and indexes: `validators.json`.

| Canonical field | Native field(s) | Conversion | Example |
|---|---|---|---|
| `Product.gtin` | `skus._id` | as is | `08901002000011` |
| `Product.brand`, `generic` | `skus.brand`, `skus.molecule` | as is | |
| `Product.strength` | `skus.strength` `{v, u}` | `"<v> <u>"` | `{v: 500, u: "mg"}` gives `500 mg` |
| `Product.form`, `pack_size` | `skus.form`, `skus.packOf` | as is | |
| `Product.storage_min_c`, `storage_max_c` | `skus.storage.minC`, `maxC` | as is, may be null | |
| `Batch.lot` | `lots._id` | as is | `MV-2410-033` |
| `Batch.gtin` | `lots.sku` | as is | |
| `Batch.mfg_date`, `expiry_date` | `lots.made`, `lots.expires` | BSON date (midnight UTC) to date | |
| `Batch.status` | `lots.recall` | a recall object gives recalled, null gives released | |
| `UnitView.status_here` | `lots.units[].state` | C in_stock, S shipped, D destroyed; other values raise | `S` |
| `Event(commission).at` | `lots.units[].at` | BSON date to IST | |
| `Event(ship).at`, `to_org`, `ref` | `lots.units[].out` `{consignment, to, at}` | BSON date to IST | `CN-7` |
| `Shipment` | `consignments` (`_id`, `consignee`, `dispatchedAt`, `lines[]`) | one `UnitRef` per serial in `lines[].sns`; lot expiry looked up in `lots` | |
| `StockLine` | `lots.units[]` where `state = "C"` | `since` is the unit's `at` | |
| `Event.city` | not stored | the node's configured city | |

Rule kept from the plan: units stay embedded in the lot; seed data stays under 2,000 units per lot.
Duplicate serials are refused by a unique multikey index on `lots.units.sn` and by a check before commissioning.
Common collections: `staff`, `scanFixes`, `docLinks`.
