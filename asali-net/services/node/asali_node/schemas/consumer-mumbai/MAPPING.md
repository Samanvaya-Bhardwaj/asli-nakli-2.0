# Consumer node, Mumbai (consumer-mumbai): native schema to canonical model

MongoDB. Adapter: `stores/consumer_mumbai.py`. Same information as Delhi, different names and nesting.

| Canonical field | Native field(s) | Conversion | Example |
|---|---|---|---|
| `ScanStat.total`, `by_city` | `scans` with `code.gtin` and `code.sn` | grouped by `where.city`; `when` to IST, **truncated to the minute** | |
| `ReportRecord.report_id`, `doc_id` | `reports._id`, `reports.doc` | as is | |
| `ReportRecord.gtin`, `serial` | `reports.code.gtin`, `reports.code.sn` | as is, may be null | |
| `ReportRecord.city`, `at` | `reports.where.city`, `reports.when` | BSON date to IST | |
| not shared | `scans.input.raw`, `result.verdict`, `result.why`, `device` | stay in this node's database | |

Common collections: `staff`, `scanFixes`, `docLinks`.

## Related tables for Phase 3 (context discovery)

Every organisation's database holds at least four related tables, joined by keys, so that what is known about a pack is spread across them and a database can find context by following its own keys.

- `verdicts`, `cities`, `reasons`: the same three as Delhi's, as collections. `scans.result.verdict`, `scans.where.city`, `reports.where.city` and `reasons.scan` are declared references (`CONTEXT_REFS` in `stores/consumer_mumbai.py`); MongoDB has no foreign keys to read.
