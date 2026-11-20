-- DB1: Purchase and Scan Registry
-- Records scan and purchase events at point of sale.
-- Integration attribute: scan_code
--
-- Phase 3: the retail POS now keeps 7 related tables. A medicine sold at a
-- pharmacy is described by its item-master row (retail_medicines), the goods
-- received note that brought it in (stock_receipts), the shelf stock
-- (inventory), the checkout scans (purchase_events) and the terminal that read
-- it (pos_terminals), all hanging off the pharmacy (vendors).
-- No existing table gained or lost a column; purchase_events only gained the
-- foreign key on its existing device_id column.

PRAGMA foreign_keys = ON;

-- 1. Vendors table: stores retail vendor details
CREATE TABLE IF NOT EXISTS vendors (
    vendor_id        TEXT PRIMARY KEY,
    vendor_name      TEXT NOT NULL,
    vendor_type      TEXT CHECK(vendor_type IN ('pharmacy','supermarket','clinic','hospital','kiosk')),
    location_county  TEXT NOT NULL,
    location_street  TEXT,
    license_no       TEXT UNIQUE,
    license_expiry   DATE,
    phone            TEXT,
    email            TEXT,
    active           INTEGER NOT NULL DEFAULT 1,
    registered_on    DATE NOT NULL,
    CONSTRAINT chk_vendor_id CHECK (vendor_id LIKE 'VND-%')
);

-- 4. (Phase 3) POS terminals: the till or camera that read a pack
CREATE TABLE IF NOT EXISTS pos_terminals (
    device_id           TEXT PRIMARY KEY,
    vendor_id           TEXT,
    terminal_model      TEXT,
    scanner_type        TEXT CHECK(scanner_type IN ('laser','imager_2d','camera','nfc','keyboard')),
    firmware_version    TEXT,
    installed_on        DATE,
    registration_status TEXT NOT NULL DEFAULT 'registered'
                        CHECK(registration_status IN ('registered','auto_registered','decommissioned')),
    FOREIGN KEY (vendor_id) REFERENCES vendors(vendor_id)
);

-- 2. Purchase events table: point of sale scans
CREATE TABLE IF NOT EXISTS purchase_events (
    event_id         TEXT PRIMARY KEY,
    scan_code        TEXT NOT NULL,
    scan_timestamp   DATETIME NOT NULL DEFAULT (datetime('now')),
    vendor_id        TEXT NOT NULL,
    customer_age_group TEXT CHECK(customer_age_group IN ('child','youth','adult','senior')),
    quantity_bought  INTEGER NOT NULL DEFAULT 1,
    price_paid       REAL NOT NULL CHECK(price_paid >= 0),
    currency         TEXT NOT NULL DEFAULT 'INR',
    payment_method   TEXT CHECK(payment_method IN ('cash','upi','card','insurance','mpesa')),
    -- 'ocr': the code was read off the printed label by a phone or counter camera
    scan_method      TEXT CHECK(scan_method IN ('barcode','qrcode','manual','nfc','ocr')),
    device_id        TEXT,
    anomaly_flag     INTEGER NOT NULL DEFAULT 0,
    anomaly_reason   TEXT,
    notes            TEXT,
    -- Image data: raw OCR text of the photographed pack label, and the photo itself
    -- (path under dashboard/). Used as matching evidence for a damaged scan_code.
    label_text       TEXT,
    label_image      TEXT,
    FOREIGN KEY (vendor_id) REFERENCES vendors(vendor_id),
    -- Phase 3: the terminal that made the scan
    FOREIGN KEY (device_id) REFERENCES pos_terminals(device_id)
);

-- 3. Scan anomaly log: duplicate or impossible scan patterns
CREATE TABLE IF NOT EXISTS scan_anomaly_log (
    anomaly_id       TEXT PRIMARY KEY,
    scan_code        TEXT NOT NULL,
    detected_on      DATETIME NOT NULL DEFAULT (datetime('now')),
    anomaly_type     TEXT CHECK(anomaly_type IN ('multi_location','expired_scan','rapid_rescan','unregistered_vendor')),
    vendor_ids       TEXT,
    description      TEXT,
    resolved         INTEGER NOT NULL DEFAULT 0
);

-- 5. (Phase 3) Retail item master: the medicines this pharmacy network stocks,
-- as keyed in by the pharmacy when the item was first received.
-- item_code is the serialised medicine id printed on the pack: the same business
-- identifier DB2 calls batch_serial, DB3 product_uid and DB4 complaint_item_ref.
-- Sales are not tied to this table by a foreign key on purchase_events.scan_code,
-- on purpose: a scanned code can be damaged (Phase 2), and a counterfeit code has
-- no master row at all. Sales join it on scan_code = item_code.
CREATE TABLE IF NOT EXISTS retail_medicines (
    item_code        TEXT PRIMARY KEY,
    brand_name       TEXT NOT NULL,
    generic_name     TEXT,
    strength         TEXT,
    pack_size        TEXT,
    batch_number     TEXT,
    expiry_date      DATE,
    mrp_inr          REAL CHECK(mrp_inr IS NULL OR mrp_inr >= 0),
    schedule_class   TEXT CHECK(schedule_class IN ('OTC','H','H1','X')),
    manufacturer_id  TEXT,     -- business id of the maker (DB3 manufacturers.manufacturer_id)
    added_on         DATE
);

-- 6. (Phase 3) Goods received notes: stock arriving at a pharmacy from a distributor
CREATE TABLE IF NOT EXISTS stock_receipts (
    receipt_id              TEXT PRIMARY KEY,
    vendor_id               TEXT NOT NULL,
    item_code               TEXT NOT NULL,
    supplier_distributor_id TEXT,     -- business id (DB2 distributors.distributor_id)
    supplier_dispatch_ref   TEXT,     -- business id (DB2 distribution_batches.batch_id)
    invoice_no              TEXT,
    received_on             DATE NOT NULL,
    quantity_received       INTEGER NOT NULL CHECK(quantity_received >= 0),
    FOREIGN KEY (vendor_id) REFERENCES vendors(vendor_id),
    FOREIGN KEY (item_code) REFERENCES retail_medicines(item_code)
);

-- 7. (Phase 3) Inventory: stock on hand per pharmacy and medicine
CREATE TABLE IF NOT EXISTS inventory (
    inventory_id      TEXT PRIMARY KEY,
    vendor_id         TEXT NOT NULL,
    item_code         TEXT NOT NULL,
    quantity_on_hand  INTEGER NOT NULL DEFAULT 0 CHECK(quantity_on_hand >= 0),
    reorder_level     INTEGER NOT NULL DEFAULT 0,
    shelf_location    TEXT,
    last_receipt_id   TEXT,
    last_stock_take   DATE,
    UNIQUE (vendor_id, item_code),
    FOREIGN KEY (vendor_id) REFERENCES vendors(vendor_id),
    FOREIGN KEY (item_code) REFERENCES retail_medicines(item_code),
    FOREIGN KEY (last_receipt_id) REFERENCES stock_receipts(receipt_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_pe_scan_code   ON purchase_events(scan_code);
CREATE INDEX IF NOT EXISTS idx_pe_vendor_id   ON purchase_events(vendor_id);
CREATE INDEX IF NOT EXISTS idx_pe_timestamp   ON purchase_events(scan_timestamp);
CREATE INDEX IF NOT EXISTS idx_pe_anomaly     ON purchase_events(anomaly_flag);
CREATE INDEX IF NOT EXISTS idx_pe_device      ON purchase_events(device_id);
CREATE INDEX IF NOT EXISTS idx_term_vendor    ON pos_terminals(vendor_id);
CREATE INDEX IF NOT EXISTS idx_sr_vendor      ON stock_receipts(vendor_id);
CREATE INDEX IF NOT EXISTS idx_sr_item        ON stock_receipts(item_code);
CREATE INDEX IF NOT EXISTS idx_inv_item       ON inventory(item_code);

-- Phase 3 integrity triggers. FK enforcement is off for the Phase 1/2 code paths
-- (they deliberately store noisy references), so a scan from a terminal nobody
-- registered yet registers it instead of leaving a dangling reference.
CREATE TRIGGER IF NOT EXISTS trg_pe_register_terminal_ins
AFTER INSERT ON purchase_events
WHEN NEW.device_id IS NOT NULL
BEGIN
    INSERT OR IGNORE INTO pos_terminals (device_id, vendor_id, registration_status, installed_on)
    VALUES (NEW.device_id, (SELECT vendor_id FROM vendors WHERE vendor_id = NEW.vendor_id),
            'auto_registered', date('now'));
END;

CREATE TRIGGER IF NOT EXISTS trg_pe_register_terminal_upd
AFTER UPDATE OF device_id ON purchase_events
WHEN NEW.device_id IS NOT NULL
BEGIN
    INSERT OR IGNORE INTO pos_terminals (device_id, vendor_id, registration_status, installed_on)
    VALUES (NEW.device_id, (SELECT vendor_id FROM vendors WHERE vendor_id = NEW.vendor_id),
            'auto_registered', date('now'));
END;
