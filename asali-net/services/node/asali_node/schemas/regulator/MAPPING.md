# State and Central Drug Control (regulator): native schema to canonical model

PostgreSQL. Adapter: `stores/regulator.py`.

| Canonical field | Native field(s) | Conversion | Example |
|---|---|---|---|
| `Alert.alert_id`, `kind`, `gtin`, `lot`, `manufacturer_org`, `reason`, `doc_id` | `alerts.*` of the same names | as is; an alert with no lot covers every lot of the product | |
| `Alert.issued_at` | `alerts.issued_at` | timestamptz to IST | |
| `Alert.states` | `alerts.states` | `",DL,MH,"` to `["DL", "MH"]`; null means a national alert | |
| `Licence.*` | `licences.*` | dates as is; `status` must be active, suspended or cancelled (CHECK) | |
| not shared | `inspections.*` | stays in the regulator's database | |

State filtering: `alerts(state="DL")` returns alerts for that state plus national ones, newest first.
`states` is an addition to the plan's `alerts` table (see CHANGES.md, D10).
Common tables: `staff`, `scan_corrections`, `document_links`.

## Related tables for Phase 3 (context discovery)

Every organisation's database holds at least four related tables, joined by keys, so that what is known about a pack is spread across them and a database can find context by following its own keys.

- `alert_kinds` (kind, label, action for shops): `alerts.kind` references it.
- `alert_states` (alert, state): one row per state an alert covers, next to the `alerts.states` text kept for filtering.
- `licence_types`: `licences.licence_type` references it. `inspection_outcomes`: `inspections.outcome` references it.
- A kind, licence type or outcome that is new is added to its table when first used.
