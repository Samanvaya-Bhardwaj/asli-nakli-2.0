-- DB2: Distributor and Supplier Ledger
-- Tracks shipments from manufacturers to retail vendors.
-- Integration attribute: batch_serial
--
-- Phase 3: the distributor ERP now keeps 7 related tables. A shipment of a
-- medicine (distribution_batches, one row per shipment line) is described by
-- the distributor that carried it, the warehouse it left from (warehouses),
-- the cold-chain data logger packed with it (cold_chain_loggers) and every
-- reading that logger took (temperature_logs).
-- No existing table gained or lost a column; distribution_batches only gained
-- a composite foreign key on its existing (distributor_id, source_warehouse).

PRAGMA foreign_keys = ON;

-- 1. Distributors table: companies licensed to transport medicines
CREATE TABLE IF NOT EXISTS distributors (
    distributor_id    TEXT PRIMARY KEY,
    company_name      TEXT NOT NULL,
    license_no        TEXT UNIQUE NOT NULL,
    license_expiry    DATE NOT NULL,
    registration_date DATE NOT NULL,
    region            TEXT NOT NULL,
    hq_address        TEXT,
    contact_person    TEXT,
    contact_phone     TEXT,
    contact_email     TEXT,
    cold_chain_capable INTEGER NOT NULL DEFAULT 0,
    is_authorized     INTEGER NOT NULL DEFAULT 1,
    revocation_reason TEXT,
    CONSTRAINT chk_dist_id CHECK (distributor_id LIKE 'DIST-%')
);

-- 5. (Phase 3) Warehouses: the distributor's storage locations, as named on its
-- dispatch notes. A location written on a note but never licensed ('Unregistered
-- godown', '?') is kept with verification_status = 'unregistered': that is
-- evidence, not an error to clean away.
CREATE TABLE IF NOT EXISTS warehouses (
    warehouse_id            TEXT PRIMARY KEY,
    distributor_id          TEXT NOT NULL,
    warehouse_name          TEXT NOT NULL,
    city                    TEXT,
    drug_license_no         TEXT,
    cold_storage            INTEGER NOT NULL DEFAULT 0 CHECK(cold_storage IN (0,1)),
    cold_storage_capacity_l REAL,
    verification_status     TEXT NOT NULL DEFAULT 'registered'
                            CHECK(verification_status IN ('registered','unregistered','auto_registered')),
    UNIQUE (distributor_id, warehouse_name),
    FOREIGN KEY (distributor_id) REFERENCES distributors(distributor_id)
);

-- 2. Distribution batches: per-item shipment records
CREATE TABLE IF NOT EXISTS distribution_batches (
    batch_id              TEXT PRIMARY KEY,
    batch_serial          TEXT NOT NULL,
    distributor_id        TEXT NOT NULL,
    manufacturer_ref      TEXT NOT NULL,
    source_warehouse      TEXT,
    destination_vendor_id TEXT NOT NULL,
    quantity_shipped      INTEGER NOT NULL CHECK(quantity_shipped > 0),
    quantity_received     INTEGER,
    dispatch_date         DATE NOT NULL,
    expected_arrival_date DATE,
    actual_arrival_date   DATE,
    cold_chain_maintained INTEGER CHECK(cold_chain_maintained IN (0,1)),
    temperature_log_url   TEXT,
    transport_mode        TEXT CHECK(transport_mode IN ('road','air','rail','courier')),
    vehicle_reg           TEXT,
    status                TEXT NOT NULL DEFAULT 'dispatched'
                          CHECK(status IN ('dispatched','in_transit','delivered','returned','lost','damaged')),
    discrepancy_noted     INTEGER NOT NULL DEFAULT 0,
    discrepancy_details   TEXT,
    FOREIGN KEY (distributor_id) REFERENCES distributors(distributor_id),
    -- Phase 3: the warehouse the shipment left from (NULL source_warehouse = not recorded)
    FOREIGN KEY (distributor_id, source_warehouse) REFERENCES warehouses(distributor_id, warehouse_name)
);

-- 3. Distributor to vendor authorization contracts
CREATE TABLE IF NOT EXISTS distributor_vendor_contracts (
    contract_id    TEXT PRIMARY KEY,
    distributor_id TEXT NOT NULL,
    vendor_id      TEXT NOT NULL,
    contract_start DATE NOT NULL,
    contract_end   DATE,
    product_scope  TEXT,
    active         INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (distributor_id) REFERENCES distributors(distributor_id)
);

-- 4. Returns log: items returned to distributor
CREATE TABLE IF NOT EXISTS return_log (
    return_id       TEXT PRIMARY KEY,
    batch_serial    TEXT NOT NULL,
    returned_by     TEXT NOT NULL,
    return_date     DATE NOT NULL,
    return_reason   TEXT CHECK(return_reason IN ('expired','damaged','excess','suspected_fake','quality_issue')),
    quantity        INTEGER NOT NULL,
    accepted        INTEGER,
    notes           TEXT
);

-- 6. (Phase 3) Cold-chain data loggers: one logger travels with each shipment
-- that must be kept within a temperature band. The setpoints are the storage
-- band the distributor was instructed to hold for that medicine.
CREATE TABLE IF NOT EXISTS cold_chain_loggers (
    logger_id        TEXT PRIMARY KEY,
    batch_id         TEXT NOT NULL UNIQUE,
    logger_serial    TEXT NOT NULL,
    profile          TEXT NOT NULL CHECK(profile IN ('refrigerated_2_8C','frozen','ambient_controlled')),
    setpoint_min_c   REAL NOT NULL,
    setpoint_max_c   REAL NOT NULL,
    activated_at     DATETIME,
    deactivated_at   DATETIME,
    CHECK (setpoint_min_c < setpoint_max_c),
    FOREIGN KEY (batch_id) REFERENCES distribution_batches(batch_id)
);

-- 7. (Phase 3) Temperature readings taken by a logger during the journey
CREATE TABLE IF NOT EXISTS temperature_logs (
    reading_id     TEXT PRIMARY KEY,
    logger_id      TEXT NOT NULL,
    recorded_at    DATETIME NOT NULL,
    temperature_c  REAL NOT NULL,
    location_type  TEXT CHECK(location_type IN ('warehouse','in_transit','delivery')),
    excursion      INTEGER NOT NULL DEFAULT 0 CHECK(excursion IN (0,1)),
    FOREIGN KEY (logger_id) REFERENCES cold_chain_loggers(logger_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_db_batch_serial   ON distribution_batches(batch_serial);
CREATE INDEX IF NOT EXISTS idx_db_distributor    ON distribution_batches(distributor_id);
CREATE INDEX IF NOT EXISTS idx_db_vendor         ON distribution_batches(destination_vendor_id);
CREATE INDEX IF NOT EXISTS idx_db_status         ON distribution_batches(status);
CREATE INDEX IF NOT EXISTS idx_db_warehouse      ON distribution_batches(distributor_id, source_warehouse);
CREATE INDEX IF NOT EXISTS idx_tl_logger         ON temperature_logs(logger_id);

-- Phase 3 integrity trigger: a dispatch note naming a location the ERP has not
-- seen before records that location, so the foreign key never dangles.
CREATE TRIGGER IF NOT EXISTS trg_db_register_warehouse_ins
AFTER INSERT ON distribution_batches
WHEN NEW.source_warehouse IS NOT NULL
BEGIN
    INSERT OR IGNORE INTO warehouses (warehouse_id, distributor_id, warehouse_name, verification_status)
    VALUES ('WH-AUTO-' || upper(hex(randomblob(4))), NEW.distributor_id, NEW.source_warehouse, 'auto_registered');
END;

CREATE TRIGGER IF NOT EXISTS trg_db_register_warehouse_upd
AFTER UPDATE OF distributor_id, source_warehouse ON distribution_batches
WHEN NEW.source_warehouse IS NOT NULL
BEGIN
    INSERT OR IGNORE INTO warehouses (warehouse_id, distributor_id, warehouse_name, verification_status)
    VALUES ('WH-AUTO-' || upper(hex(randomblob(4))), NEW.distributor_id, NEW.source_warehouse, 'auto_registered');
END;
