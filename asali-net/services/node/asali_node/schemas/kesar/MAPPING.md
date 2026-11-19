# Kesar Biologics: native schema to canonical model

SQLite, legacy ERP style. Source of truth for the adapter in `stores/kesar.py`.

| Canonical field | Native field(s) | Conversion | Example |
|---|---|---|---|
| `Product.gtin` | `ITEM_MST.GTIN` | as is | `08901003000111` |
| `Product.brand` | `ITEM_MST.ITEM_DESC` | as is | `Glargix` |
| `Product.generic` | `ITEM_MST.MOL_DESC` | as is | `insulin glargine` |
| `Product.strength` | `ITEM_MST.STR` | as is | `100 IU/ml` |
| `Product.form`, `Product.pack_size` | `ITEM_MST.UOM` | `"<code>/<pack>"`; TAB, CAP, INJ, SYR, OTH map to tablet, capsule, injection, syrup, other | `INJ/1` gives injection, 1 |
| `Product.storage_min_c`, `storage_max_c` | `ITEM_MST.STOR_TEMP_TXT` | `"2-8 C"` gives 2 and 8; `"BELOW 25 C"` gives null and 25; empty gives null and null; anything else raises | `2-8 C` |
| `Batch.lot` | `LOT_MST.LOT_NO` | as is | `K/24/0091` |
| `Batch.mfg_date` | `LOT_MST.MFG_DT` | `DD/MM/YYYY` to a date | `05/10/2026` gives 2026-10-05 |
| `Batch.expiry_date` | `LOT_MST.EXP_DT` | `MM/YYYY` means the last day of that month | `09/2028` gives 2028-09-30 |
| `Batch.status` | `LOT_MST.LOT_STAT` | A released, Q quarantine, R recalled; other codes raise | `R` gives recalled |
| `UnitView.status_here` | `SRL_MST.SRL_STAT` and `DSP_DTL` | C is in_stock, D is shipped, X is destroyed; other codes raise | `D` gives shipped |
| `Event(commission).at` | `SRL_MST.CRT_TS` | `DD/MM/YYYY HH:MM:SS`, read as IST | `02/11/2026 10:30:00` |
| `Event(ship).at`, `Shipment.at` | `DSP_HDR.DSP_DT` | as above | |
| `Event(ship).to_org`, `Shipment.to_org` | `DSP_HDR.PARTY_CD` through `PARTY_MST.NET_ORG_ID` | party code to network org id. A party with no network id gives `to_org = null` and `ref = DSP_NO`, which the trace treats as a chain gap | `P001` gives `dist-north` |
| `Event.ref`, `Shipment.shipment_id` | `DSP_HDR.DSP_NO` | as is | `SHP-1` |
| `Shipment.units` | `DSP_DTL` joined to `SRL_MST`, `LOT_MST`, `ITEM_MST` | one `UnitRef` per row | |
| `Event.city` | not stored | the node's configured city | `Baddi` |

Things Kesar does not keep, and what the adapter does about them:

- **Batch quantity** has no column. `NewBatch.quantity` is accepted and not stored.
- **Product schedule** has no column. `NewProduct.schedule` is accepted and not stored.
- **Recall level** has no column. `RCL_REG.RCL_RSN` holds `"<level>: <reason>"`.
- **Expiry within a month** is lost. A batch whose expiry is not a month end reads back as the month end.
- **Common tables** use Kesar's naming: `USR_MST` (staff), `SCN_CORR` (scan corrections), `DOC_LNK` (document links).
