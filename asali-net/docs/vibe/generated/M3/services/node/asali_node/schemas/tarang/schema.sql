-- Tarang Pharma: PostgreSQL, normalised, snake_case.
CREATE TABLE IF NOT EXISTS products (
  gtin char(14) PRIMARY KEY, brand_name text NOT NULL, generic_name text NOT NULL, strength text NOT NULL,
  dosage_form text NOT NULL, pack_size int NOT NULL, storage_min_c numeric, storage_max_c numeric, schedule text);
CREATE TABLE IF NOT EXISTS batches (
  lot text PRIMARY KEY, gtin char(14) NOT NULL REFERENCES products(gtin), mfg_date date NOT NULL,
  expiry_date date NOT NULL, quantity int NOT NULL,
  status text NOT NULL CHECK (status IN ('released', 'quarantine', 'recalled')));
CREATE TABLE IF NOT EXISTS units (
  serial char(11) PRIMARY KEY, gtin char(14) NOT NULL REFERENCES products(gtin),
  lot text NOT NULL REFERENCES batches(lot),
  status text NOT NULL CHECK (status IN ('commissioned', 'shipped', 'destroyed')),
  commissioned_at timestamptz NOT NULL);
CREATE TABLE IF NOT EXISTS shipments (
  shipment_id text PRIMARY KEY, to_org_id text NOT NULL, shipped_at timestamptz NOT NULL, vehicle_no text,
  created_by text);
CREATE TABLE IF NOT EXISTS shipment_units (
  shipment_id text NOT NULL REFERENCES shipments(shipment_id), serial char(11) NOT NULL REFERENCES units(serial),
  PRIMARY KEY (shipment_id, serial));
CREATE TABLE IF NOT EXISTS recalls (
  recall_id text PRIMARY KEY, lot text NOT NULL REFERENCES batches(lot), reason text NOT NULL, level text NOT NULL,
  issued_at timestamptz NOT NULL);
CREATE TABLE IF NOT EXISTS staff (
  username text PRIMARY KEY, password_hash text NOT NULL, role text NOT NULL, display_name text NOT NULL);
CREATE TABLE IF NOT EXISTS scan_corrections (
  id bigserial PRIMARY KEY, at timestamptz NOT NULL, raw text NOT NULL, field text NOT NULL, chosen text NOT NULL,
  cost numeric NOT NULL, confirmed_by text NOT NULL);
CREATE TABLE IF NOT EXISTS document_links (
  doc_id text NOT NULL, entity_type text NOT NULL, entity_key text NOT NULL, confidence numeric NOT NULL,
  linked_at timestamptz NOT NULL);
CREATE INDEX IF NOT EXISTS ix_units_lot ON units(lot);
CREATE INDEX IF NOT EXISTS ix_document_links_key ON document_links(entity_key)
