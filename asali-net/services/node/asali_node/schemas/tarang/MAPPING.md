# Tarang Pharma: native schema to canonical model

PostgreSQL, normalised, snake_case. Adapter: `stores/tarang.py`.

| Canonical field | Native field(s) | Conversion | Example |
|---|---|---|---|
| `Product.gtin`, `brand`, `generic`, `strength` | `products.gtin`, `brand_name`, `generic_name`, `strength` | as is | `08901001000124`, `Amoxil-T` |
| `Product.form`, `pack_size` | `products.dosage_form`, `pack_size` | as is (same literals) | `capsule`, 10 |
| `Product.storage_min_c`, `storage_max_c` | `products.storage_min_c`, `storage_max_c` | `numeric` to float | 15.0, 25.0 |
| `Batch.lot`, `mfg_date`, `expiry_date` | `batches.lot`, `mfg_date`, `expiry_date` | as is | `TP24A017` |
| `Batch.status` | `batches.status` | `released`, `quarantine`, `recalled` are canonical already | `recalled` |
| `UnitView.status_here` | `units.status` | commissioned is in_stock, shipped is shipped, destroyed is destroyed; other values raise | `shipped` |
| `Event(commission).at` | `units.commissioned_at` | timestamptz to IST | |
| `Event(ship).at`, `to_org`, `ref` | `shipments.shipped_at`, `to_org_id`, `shipment_id` through `shipment_units` | timestamptz to IST | `dist-north`, `SHP-1` |
| `Shipment.units` | `shipment_units` joined to `units` and `batches` | one `UnitRef` with lot and expiry per row | |
| `StockLine` | `units` where `status = 'commissioned'` | `since` is `commissioned_at` | |
| `Event.city` | not stored | the node's configured city | `Baddi` |

Not kept: nothing the canonical model needs. `NewProduct.schedule` goes to `products.schedule` and is not returned.
Common tables use the usual names: `staff`, `scan_corrections`, `document_links`.
