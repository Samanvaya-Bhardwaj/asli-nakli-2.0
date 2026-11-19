-- North Star Distributors, Delhi: PostgreSQL. Separate receipt and dispatch tables; stock is a view.
CREATE TABLE IF NOT EXISTS receipts (
  receipt_id text PRIMARY KEY, from_org_id text NOT NULL, source_ref text NOT NULL, received_at timestamptz NOT NULL,
  received_by text);
CREATE TABLE IF NOT EXISTS receipt_items (
  receipt_id text NOT NULL REFERENCES receipts(receipt_id), gtin char(14) NOT NULL, serial char(11) NOT NULL,
  PRIMARY KEY (receipt_id, serial));
CREATE TABLE IF NOT EXISTS dispatches (
  dispatch_id text PRIMARY KEY, to_org_id text NOT NULL, dispatched_at timestamptz NOT NULL, vehicle_no text);
CREATE TABLE IF NOT EXISTS dispatch_items (
  dispatch_id text NOT NULL REFERENCES dispatches(dispatch_id), gtin char(14) NOT NULL, serial char(11) NOT NULL,
  PRIMARY KEY (dispatch_id, serial));
CREATE TABLE IF NOT EXISTS staff (
  username text PRIMARY KEY, password_hash text NOT NULL, role text NOT NULL, display_name text NOT NULL);
CREATE TABLE IF NOT EXISTS scan_corrections (
  id bigserial PRIMARY KEY, at timestamptz NOT NULL, raw text NOT NULL, field text NOT NULL, chosen text NOT NULL,
  cost numeric NOT NULL, confirmed_by text NOT NULL);
CREATE TABLE IF NOT EXISTS document_links (
  doc_id text NOT NULL, entity_type text NOT NULL, entity_key text NOT NULL, confidence numeric NOT NULL,
  linked_at timestamptz NOT NULL);
CREATE INDEX IF NOT EXISTS ix_receipt_items_serial ON receipt_items(serial);
CREATE INDEX IF NOT EXISTS ix_dispatch_items_serial ON dispatch_items(serial);
CREATE INDEX IF NOT EXISTS ix_document_links_key ON document_links(entity_key);
CREATE OR REPLACE VIEW stock_now AS
  SELECT ri.gtin, ri.serial, r.received_at AS since
  FROM receipt_items ri JOIN receipts r ON r.receipt_id = ri.receipt_id
  WHERE NOT EXISTS (
    SELECT 1 FROM dispatch_items di JOIN dispatches d ON d.dispatch_id = di.dispatch_id
    WHERE di.serial = ri.serial AND d.dispatched_at >= r.received_at)
