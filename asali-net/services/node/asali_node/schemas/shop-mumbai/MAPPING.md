# Apna Chemist (shop-mumbai): native schema to canonical model

PostgreSQL, one inventory ledger. Adapter: `stores/shop_mumbai.py`.

| Canonical field | Native field(s) | Conversion | Example |
|---|---|---|---|
| `Event.event_type` | `inventory_ledger.kind` | IN is receive, SALE is sell, RETURN is return, DAMAGE is destroy; other values are refused by a CHECK | `SALE` gives sell |
| `Event.from_org` | `inventory_ledger.counterparty` where `kind = 'IN'` | as is | `dist-north` |
| `Event.ref` | `inventory_ledger.doc_no` | the distributor's shipment id for IN; the bill number for SALE and RETURN | `B-1` |
| `Event.at` | `inventory_ledger.at` | timestamptz to IST | |
| `UnitView.status_here` | `kind` of the unit's last ledger row (highest `entry_id`) | IN in_stock, SALE sold, RETURN returned, DAMAGE destroyed | |
| `StockLine` | ledger rows whose `kind = 'IN'` and are the unit's last row | `since` is `at` | |

For `RETURN` rows `counterparty` holds the customer's reason. The plan's ledger has no reason column.
`bills` keeps the total and the hashed customer reference; neither is shared.
Common tables: `staff`, `scan_corrections`, `document_links`.
