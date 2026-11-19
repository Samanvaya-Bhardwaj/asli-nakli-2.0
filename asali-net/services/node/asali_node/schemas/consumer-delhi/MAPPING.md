# Consumer node, Delhi (consumer-delhi): native schema to canonical model

SQLite. Adapter: `stores/consumer_delhi.py`.

| Canonical field | Native field(s) | Conversion | Example |
|---|---|---|---|
| `ScanStat.total` | count of `checks` rows with this gtin and serial | | 3 |
| `ScanStat.by_city[].city`, `count` | `checks.city`, grouped | most checks first, then city name | |
| `ScanStat.by_city[].first_at`, `last_at` | min and max of `checks.at` per city | ISO text to IST, **truncated to the minute** | |
| `ReportRecord.report_id`, `doc_id`, `gtin`, `serial`, `city`, `at` | `reports.report_id`, `doc_id`, `gtin`, `serial`, `city`, `at` | ISO text to IST | |
| not shared | `checks.raw_input`, `reasons_json`, `device_hash`, `verdict` | stay in this node's database | |

`reports.doc_id` points at the complaint text in this node's vault; the text itself is not in the database.
Common tables: `staff`, `scan_corrections`, `document_links`.
