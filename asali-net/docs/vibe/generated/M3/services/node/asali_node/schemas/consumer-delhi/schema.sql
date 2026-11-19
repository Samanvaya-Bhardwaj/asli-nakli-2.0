-- Consumer node, Delhi: SQLite. One row per check, one per problem report (the text itself lives in the vault).
CREATE TABLE IF NOT EXISTS checks (
  check_id TEXT PRIMARY KEY, raw_input TEXT NOT NULL, gtin TEXT, serial TEXT, verdict TEXT,
  reasons_json TEXT NOT NULL, city TEXT NOT NULL, at TEXT NOT NULL, device_hash TEXT);
CREATE TABLE IF NOT EXISTS reports (
  report_id TEXT PRIMARY KEY, check_id TEXT REFERENCES checks(check_id), doc_id TEXT NOT NULL, gtin TEXT,
  serial TEXT, city TEXT NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS staff (
  username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, role TEXT NOT NULL, display_name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS scan_corrections (
  id INTEGER PRIMARY KEY, at TEXT NOT NULL, raw TEXT NOT NULL, field TEXT NOT NULL, chosen TEXT NOT NULL,
  cost REAL NOT NULL, confirmed_by TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS document_links (
  doc_id TEXT NOT NULL, entity_type TEXT NOT NULL, entity_key TEXT NOT NULL, confidence REAL NOT NULL,
  linked_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_checks_pack ON checks(gtin, serial);
CREATE INDEX IF NOT EXISTS ix_document_links_key ON document_links(entity_key)
