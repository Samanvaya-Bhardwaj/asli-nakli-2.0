-- State and Central Drug Control (fictional): PostgreSQL.
CREATE TABLE IF NOT EXISTS alerts (
  alert_id text PRIMARY KEY, kind text NOT NULL CHECK (kind IN ('recall', 'nsq', 'ban')), gtin char(14) NOT NULL,
  lot text, manufacturer_org text NOT NULL, issued_at timestamptz NOT NULL, reason text NOT NULL, doc_id text,
  states text);
CREATE TABLE IF NOT EXISTS licences (
  org_id text PRIMARY KEY, licence_no text NOT NULL, licence_type text NOT NULL, valid_from date NOT NULL,
  valid_to date NOT NULL, status text NOT NULL CHECK (status IN ('active', 'suspended', 'cancelled')));
CREATE TABLE IF NOT EXISTS inspections (
  inspection_id text PRIMARY KEY, org_id text NOT NULL, inspected_at timestamptz NOT NULL, outcome text NOT NULL,
  doc_id text);
CREATE TABLE IF NOT EXISTS staff (
  username text PRIMARY KEY, password_hash text NOT NULL, role text NOT NULL, display_name text NOT NULL);
CREATE TABLE IF NOT EXISTS scan_corrections (
  id bigserial PRIMARY KEY, at timestamptz NOT NULL, raw text NOT NULL, field text NOT NULL, chosen text NOT NULL,
  cost numeric NOT NULL, confirmed_by text NOT NULL);
CREATE TABLE IF NOT EXISTS document_links (
  doc_id text NOT NULL, entity_type text NOT NULL, entity_key text NOT NULL, confidence numeric NOT NULL,
  linked_at timestamptz NOT NULL);
CREATE INDEX IF NOT EXISTS ix_alerts_pack ON alerts(gtin, lot);
CREATE INDEX IF NOT EXISTS ix_document_links_key ON document_links(entity_key)
