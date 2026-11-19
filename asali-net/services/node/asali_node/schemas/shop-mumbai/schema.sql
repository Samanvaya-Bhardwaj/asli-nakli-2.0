-- Apna Chemist, Andheri, Mumbai: PostgreSQL, one inventory ledger.
CREATE TABLE IF NOT EXISTS inventory_ledger (
  entry_id bigserial PRIMARY KEY, kind text NOT NULL CHECK (kind IN ('IN', 'SALE', 'RETURN', 'DAMAGE')),
  gtin char(14) NOT NULL, serial char(11) NOT NULL, counterparty text, doc_no text NOT NULL, at timestamptz NOT NULL);
CREATE TABLE IF NOT EXISTS bills (
  doc_no text PRIMARY KEY, at timestamptz NOT NULL, amount_paise int NOT NULL, customer_ref_hash text);
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
