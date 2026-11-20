-- Dakshin Pharma Agencies, Bengaluru: SQLite. Keeps the raw scanned text next to the parsed values.
CREATE TABLE IF NOT EXISTS parties (
  org_id TEXT PRIMARY KEY, org_type TEXT NOT NULL CHECK (org_type IN ('pharma', 'distributor', 'shop', 'consumer', 'regulator')));
CREATE TABLE IF NOT EXISTS inward (
  entry_id INTEGER PRIMARY KEY, supplier_org TEXT NOT NULL REFERENCES parties(org_id), dc_number TEXT NOT NULL, entry_date TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS inward_lines (
  entry_id INTEGER NOT NULL REFERENCES inward(entry_id), barcode_raw TEXT, gtin TEXT NOT NULL, sn TEXT NOT NULL,
  lot TEXT, exp TEXT, corrected INTEGER NOT NULL DEFAULT 0 CHECK (corrected IN (0, 1)),
  PRIMARY KEY (entry_id, sn));
CREATE TABLE IF NOT EXISTS outward (
  entry_id INTEGER PRIMARY KEY, customer_org TEXT NOT NULL REFERENCES parties(org_id), invoice_no TEXT NOT NULL, entry_date TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS outward_lines (
  entry_id INTEGER NOT NULL REFERENCES outward(entry_id), barcode_raw TEXT, gtin TEXT NOT NULL, sn TEXT NOT NULL,
  PRIMARY KEY (entry_id, sn));
CREATE TABLE IF NOT EXISTS users (
  username TEXT PRIMARY KEY, pw_hash TEXT NOT NULL, user_role TEXT NOT NULL, full_name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS scan_fixes (
  fix_id INTEGER PRIMARY KEY, fixed_at TEXT NOT NULL, raw TEXT NOT NULL, which TEXT NOT NULL, chosen TEXT NOT NULL,
  cost REAL NOT NULL, by_user TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS doc_refs (
  doc_id TEXT NOT NULL, ent_type TEXT NOT NULL, ent_key TEXT NOT NULL, conf REAL NOT NULL, linked_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_inward_sn ON inward_lines(sn);
CREATE INDEX IF NOT EXISTS ix_outward_sn ON outward_lines(sn);
CREATE INDEX IF NOT EXISTS ix_doc_refs_key ON doc_refs(ent_key)
