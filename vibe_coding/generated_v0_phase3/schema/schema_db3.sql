-- DB3: Manufacturer Product Registry
-- Authoritative catalog of genuine products registered by licensed manufacturers.
-- Integration attribute: product_uid
--
-- Phase 3: the registry now keeps 7 related tables. A registered medicine batch
-- (products, one row per serialised batch) is described by its molecule
-- (molecules), its maker (manufacturers), the plant that made it
-- (manufacturing_sites), the production run (production_records) and the
-- quality-control release certificate (batch_release_certs).
-- No existing table gained or lost a column; products only gained a foreign
-- key on its existing generic_name column.

PRAGMA foreign_keys = ON;

-- 1. Manufacturers table
CREATE TABLE IF NOT EXISTS manufacturers (
    manufacturer_id      TEXT PRIMARY KEY,
    company_name         TEXT NOT NULL,
    country              TEXT NOT NULL DEFAULT 'India',
    physical_address     TEXT,
    license_no           TEXT UNIQUE NOT NULL,
    license_expiry       DATE NOT NULL,
    gmp_certified        INTEGER NOT NULL DEFAULT 1,
    gmp_cert_number      TEXT,
    gmp_cert_expiry      DATE,
    iso_certified        INTEGER NOT NULL DEFAULT 0,
    iso_cert_number      TEXT,
    nairobi_stock_exchange_listed INTEGER DEFAULT 0,
    founded_year         INTEGER,
    ceo_name             TEXT,
    contact_email        TEXT,
    website              TEXT,
    CONSTRAINT chk_mfg_id CHECK (manufacturer_id LIKE 'MFG-%')
);

-- 5. (Phase 3) Molecules: the active ingredient a product is a brand of
CREATE TABLE IF NOT EXISTS molecules (
    molecule_id          TEXT PRIMARY KEY,
    generic_name         TEXT NOT NULL UNIQUE,
    atc_code             TEXT,
    therapeutic_class    TEXT,
    schedule_class       TEXT CHECK(schedule_class IN ('OTC','H','H1','X')),
    cold_chain_required  INTEGER NOT NULL DEFAULT 0 CHECK(cold_chain_required IN (0,1)),
    registration_status  TEXT NOT NULL DEFAULT 'registered'
                         CHECK(registration_status IN ('registered','auto_registered'))
);

-- 2. Products table: catalog of registered SKU items
CREATE TABLE IF NOT EXISTS products (
    product_uid          TEXT PRIMARY KEY,
    product_name         TEXT NOT NULL,
    generic_name         TEXT,
    manufacturer_id      TEXT NOT NULL,
    category             TEXT NOT NULL,
    dosage_form          TEXT NOT NULL,
    strength             TEXT NOT NULL,
    pack_size            TEXT,
    manufacture_date     DATE NOT NULL,
    expiry_date          DATE NOT NULL,
    batch_number         TEXT NOT NULL,
    registration_no      TEXT UNIQUE NOT NULL,
    atc_code             TEXT,
    barcode_type         TEXT CHECK(barcode_type IN ('EAN-13','QR','DataMatrix','Code128','GS1-128')),
    storage_temp_min     REAL,
    storage_temp_max     REAL,
    requires_cold_chain  INTEGER NOT NULL DEFAULT 0,
    controlled_substance INTEGER NOT NULL DEFAULT 0,
    is_recalled          INTEGER NOT NULL DEFAULT 0,
    recall_date          DATE,
    recall_reason        TEXT,
    recall_authority     TEXT,
    unit_cost_kes        REAL,
    msrp_kes             REAL,
    FOREIGN KEY (manufacturer_id) REFERENCES manufacturers(manufacturer_id),
    -- Phase 3: the molecule this product is a brand of
    FOREIGN KEY (generic_name) REFERENCES molecules(generic_name),
    CONSTRAINT chk_dates CHECK (manufacture_date < expiry_date)
);

-- 3. Authorized distributors whitelist
CREATE TABLE IF NOT EXISTS authorized_distributors (
    auth_id          TEXT PRIMARY KEY,
    manufacturer_id  TEXT NOT NULL,
    distributor_ref  TEXT NOT NULL,
    authorized_since DATE NOT NULL,
    authorized_until DATE,
    territory        TEXT,
    product_categories TEXT,
    active           INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (manufacturer_id) REFERENCES manufacturers(manufacturer_id)
);

-- 4. Batch release certificates: QC verification
CREATE TABLE IF NOT EXISTS batch_release_certs (
    cert_id          TEXT PRIMARY KEY,
    product_uid      TEXT NOT NULL,
    batch_number     TEXT NOT NULL,
    qc_passed        INTEGER NOT NULL,
    release_date     DATE NOT NULL,
    qc_officer       TEXT,
    test_parameters  TEXT,
    certificate_hash TEXT UNIQUE,
    FOREIGN KEY (product_uid) REFERENCES products(product_uid)
);

-- 6. (Phase 3) Manufacturing sites: licensed plants of each manufacturer
CREATE TABLE IF NOT EXISTS manufacturing_sites (
    site_id              TEXT PRIMARY KEY,
    manufacturer_id      TEXT NOT NULL,
    site_name            TEXT NOT NULL,
    city                 TEXT,
    state                TEXT,
    site_license_no      TEXT UNIQUE,
    gmp_status           TEXT CHECK(gmp_status IN ('compliant','under_review','non_compliant')),
    last_gmp_inspection  DATE,
    FOREIGN KEY (manufacturer_id) REFERENCES manufacturers(manufacturer_id)
);

-- 7. (Phase 3) Production records: the manufacturing run behind a registered batch
CREATE TABLE IF NOT EXISTS production_records (
    production_id     TEXT PRIMARY KEY,
    product_uid       TEXT NOT NULL UNIQUE,
    site_id           TEXT NOT NULL,
    batch_number      TEXT NOT NULL,
    production_line   TEXT,
    started_on        DATE,
    completed_on      DATE,
    batch_size_units  INTEGER CHECK(batch_size_units IS NULL OR batch_size_units > 0),
    yield_percent     REAL CHECK(yield_percent IS NULL OR (yield_percent >= 0 AND yield_percent <= 100)),
    api_lot_no        TEXT,
    FOREIGN KEY (product_uid) REFERENCES products(product_uid),
    FOREIGN KEY (site_id) REFERENCES manufacturing_sites(site_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_prod_uid        ON products(product_uid);
CREATE INDEX IF NOT EXISTS idx_prod_mfg        ON products(manufacturer_id);
CREATE INDEX IF NOT EXISTS idx_prod_category   ON products(category);
CREATE INDEX IF NOT EXISTS idx_prod_expiry     ON products(expiry_date);
CREATE INDEX IF NOT EXISTS idx_prod_recalled   ON products(is_recalled);
CREATE INDEX IF NOT EXISTS idx_prod_reg        ON products(registration_no);
CREATE INDEX IF NOT EXISTS idx_prod_generic    ON products(generic_name);
CREATE INDEX IF NOT EXISTS idx_cert_product    ON batch_release_certs(product_uid);
CREATE INDEX IF NOT EXISTS idx_site_mfg        ON manufacturing_sites(manufacturer_id);
CREATE INDEX IF NOT EXISTS idx_prodrec_site    ON production_records(site_id);

-- Phase 3 integrity triggers: registering a product with a molecule the
-- registry has not catalogued yet catalogues it, so the foreign key never dangles.
CREATE TRIGGER IF NOT EXISTS trg_prod_register_molecule_ins
AFTER INSERT ON products
WHEN NEW.generic_name IS NOT NULL
BEGIN
    INSERT OR IGNORE INTO molecules (molecule_id, generic_name, atc_code, therapeutic_class,
                                     cold_chain_required, registration_status)
    VALUES ('MOL-AUTO-' || upper(hex(randomblob(4))), NEW.generic_name, NEW.atc_code, NEW.category,
            CASE WHEN NEW.requires_cold_chain = 1 THEN 1 ELSE 0 END, 'auto_registered');
END;

CREATE TRIGGER IF NOT EXISTS trg_prod_register_molecule_upd
AFTER UPDATE OF generic_name ON products
WHEN NEW.generic_name IS NOT NULL
BEGIN
    INSERT OR IGNORE INTO molecules (molecule_id, generic_name, atc_code, therapeutic_class,
                                     cold_chain_required, registration_status)
    VALUES ('MOL-AUTO-' || upper(hex(randomblob(4))), NEW.generic_name, NEW.atc_code, NEW.category,
            CASE WHEN NEW.requires_cold_chain = 1 THEN 1 ELSE 0 END, 'auto_registered');
END;
