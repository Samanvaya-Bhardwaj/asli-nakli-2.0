# Namma Pharmacy (shop-bengaluru): native schema to canonical model

MongoDB, one document per pack. Adapter: `stores/shop_bengaluru.py`.

| Canonical field | Native field(s) | Conversion | Example |
|---|---|---|---|
| `UnitRef.gtin`, `serial` | `stock._id` | split `"<gtin>/<serial>"` | `08901001000124/TP000000001` |
| `Event(receive).from_org`, `ref`, `at` | `stock.in.from`, `in.ref`, `in.at` | BSON date to IST | |
| `Event(sell).ref`, `at` | `stock.sale.bill`, `sale.at` | BSON date to IST | |
| `Event(return).ref`, `at` | `stock.sale.bill`, `stock.ret.at` | the return keeps the bill of the sale it undoes | |
| `UnitView.status_here` | `stock.ret`, `stock.sale` | ret set is returned, sale set is sold, neither is in_stock | |
| `StockLine` | `stock` where `sale` and `ret` are both null | `since` is `in.at` | |
| not in the canonical model | `bills.amountPaise`, `bills.customerRef`, `stock.ret.why` | kept in the shop's own database only | |

A pack that was already received cannot be received again (duplicate `_id` raises `ValueError`).
Common collections: `staff`, `scanFixes`, `docLinks`.
