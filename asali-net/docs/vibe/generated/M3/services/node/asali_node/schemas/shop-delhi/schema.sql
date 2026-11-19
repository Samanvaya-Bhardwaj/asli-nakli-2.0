-- Sharma Medicos, Lajpat Nagar, Delhi: SQLite, purchase and sale bills.
CREATE TABLE IF NOT EXISTS purchases (
  pur_id TEXT PRIMARY KEY, distributor_org TEXT NOT NULL, bill_no TEXT NOT NULL, bill_date TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS purchase_items (
  pur_id TEXT NOT NULL REFERENCES purchases(pur_id), gtin TEXT NOT NULL, sn TEXT NOT NULL, lot TEXT, exp TEXT,
  PRIMARY KEY (pur_id, sn));
CREATE TABLE IF NOT EXISTS sales (
  bill_no TEXT PRIMARY KEY, sold_at TEXT NOT NULL, customer_ref_hash TEXT, total_paise INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS sale_items (
  bill_no TEXT NOT NULL REFERENCES sales(bill_no), gtin TEXT NOT NULL, sn TEXT NOT NULL, mrp_paise INTEGER NOT NULL,
  PRIMARY KEY (bill_no, sn));
CREATE TABLE IF NOT EXISTS returns (
  ret_id TEXT PRIMARY KEY, bill_no TEXT NOT NULL, sn TEXT NOT NULL, reason TEXT NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (
  username TEXT PRIMARY KEY, pw_hash TEXT NOT NULL, user_role TEXT NOT NULL, full_name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS scan_fixes (
  fix_id INTEGER PRIMARY KEY, fixed_at TEXT NOT NULL, raw TEXT NOT NULL, which TEXT NOT NULL, chosen TEXT NOT NULL,
  cost REAL NOT NULL, by_user TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS doc_links (
  doc_id TEXT NOT NULL, ent_type TEXT NOT NULL, ent_key TEXT NOT NULL, conf REAL NOT NULL, linked_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_pitems_sn ON purchase_items(sn);
CREATE INDEX IF NOT EXISTS ix_sitems_sn ON sale_items(sn);
CREATE INDEX IF NOT EXISTS ix_doc_links_key ON doc_links(ent_key)
