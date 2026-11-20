-- State and Central Drug Control (fictional): PostgreSQL.
CREATE TABLE IF NOT EXISTS alert_kinds (
  kind text PRIMARY KEY, label text NOT NULL, action_for_shops text NOT NULL);
INSERT INTO alert_kinds (kind, label, action_for_shops) VALUES
  ('nsq', 'Not of standard quality', 'Stop selling the batch and keep the stock aside'),
  ('recall', 'Recall', 'Stop selling the batch and return the stock to the distributor'),
  ('ban', 'Ban', 'Do not sell this product')
  ON CONFLICT (kind) DO NOTHING;
CREATE TABLE IF NOT EXISTS alerts (
  alert_id text PRIMARY KEY, kind text NOT NULL REFERENCES alert_kinds(kind), gtin char(14) NOT NULL,
  lot text, manufacturer_org text NOT NULL, issued_at timestamptz NOT NULL, reason text NOT NULL, doc_id text,
  states text);
CREATE TABLE IF NOT EXISTS alert_states (
  alert_id text NOT NULL REFERENCES alerts(alert_id), state text NOT NULL, PRIMARY KEY (alert_id, state));
CREATE TABLE IF NOT EXISTS licence_types (
  licence_type text PRIMARY KEY, label text NOT NULL);
INSERT INTO licence_types (licence_type, label) VALUES
  ('retail', 'Retail sale of medicines'), ('wholesale', 'Wholesale distribution of medicines'),
  ('manufacturing', 'Manufacture of medicines') ON CONFLICT (licence_type) DO NOTHING;
CREATE TABLE IF NOT EXISTS licences (
  org_id text PRIMARY KEY, licence_no text NOT NULL, licence_type text NOT NULL REFERENCES licence_types(licence_type),
  valid_from date NOT NULL, valid_to date NOT NULL, status text NOT NULL CHECK (status IN ('active', 'suspended', 'cancelled')));
CREATE TABLE IF NOT EXISTS inspection_outcomes (
  outcome text PRIMARY KEY, label text NOT NULL);
INSERT INTO inspection_outcomes (outcome, label) VALUES
  ('passed', 'Passed'), ('minor', 'Passed with minor observations'), ('major', 'Major deficiencies found')
  ON CONFLICT (outcome) DO NOTHING;
CREATE TABLE IF NOT EXISTS inspections (
  inspection_id text PRIMARY KEY, org_id text NOT NULL, inspected_at timestamptz NOT NULL,
  outcome text NOT NULL REFERENCES inspection_outcomes(outcome), doc_id text);
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
