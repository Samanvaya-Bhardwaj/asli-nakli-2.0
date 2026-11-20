-- Apna Chemist, Andheri, Mumbai: PostgreSQL, one inventory ledger.
CREATE TABLE IF NOT EXISTS entry_kinds (
  kind text PRIMARY KEY, label text NOT NULL, stock_effect text NOT NULL CHECK (stock_effect IN ('adds', 'removes', 'none')));
INSERT INTO entry_kinds (kind, label, stock_effect) VALUES
  ('IN', 'Received from a distributor', 'adds'), ('SALE', 'Sold to a customer', 'removes'),
  ('RETURN', 'Returned by a customer', 'adds'), ('DAMAGE', 'Written off as damaged', 'removes')
  ON CONFLICT (kind) DO NOTHING;
CREATE TABLE IF NOT EXISTS inventory_ledger (
  entry_id bigserial PRIMARY KEY, kind text NOT NULL REFERENCES entry_kinds(kind),
  gtin char(14) NOT NULL, serial char(11) NOT NULL, counterparty text, doc_no text NOT NULL, at timestamptz NOT NULL);
CREATE TABLE IF NOT EXISTS bills (
  doc_no text PRIMARY KEY, at timestamptz NOT NULL, amount_paise int NOT NULL, customer_ref_hash text);
CREATE TABLE IF NOT EXISTS bill_lines (
  doc_no text NOT NULL REFERENCES bills(doc_no), gtin char(14) NOT NULL, serial char(11) NOT NULL, mrp_paise int NOT NULL,
  PRIMARY KEY (doc_no, serial));
CREATE TABLE IF NOT EXISTS returns (
  return_id bigserial PRIMARY KEY, doc_no text NOT NULL REFERENCES bills(doc_no), gtin char(14) NOT NULL,
  serial char(11) NOT NULL, reason text NOT NULL, at timestamptz NOT NULL);
CREATE TABLE IF NOT EXISTS staff (
  username text PRIMARY KEY, password_hash text NOT NULL, role text NOT NULL, display_name text NOT NULL);
CREATE TABLE IF NOT EXISTS scan_corrections (
  id bigserial PRIMARY KEY, at timestamptz NOT NULL, raw text NOT NULL, field text NOT NULL, chosen text NOT NULL,
  cost numeric NOT NULL, confirmed_by text NOT NULL);
CREATE TABLE IF NOT EXISTS document_links (
  doc_id text NOT NULL, entity_type text NOT NULL, entity_key text NOT NULL, confidence numeric NOT NULL,
  linked_at timestamptz NOT NULL);
CREATE INDEX IF NOT EXISTS ix_ledger_pack ON inventory_ledger(gtin, serial);
CREATE INDEX IF NOT EXISTS ix_document_links_key ON document_links(entity_key)
