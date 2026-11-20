-- DB4: Ministry of Consumer Affairs Report Database
-- Tracks complaints, regulatory blacklists, and forensic lab tests.
-- Integration attribute: complaint_item_ref
--
-- Phase 3: the ministry now keeps 7 related tables. What the regulator knows
-- about a medicine is spread over complaints, laboratory reports, the blacklist,
-- public alerts and recall notices, each tied to the authority and officer that
-- acted on it (regulatory_authorities, ministry_officers).
-- The ministry keeps no medicine master of its own: it refers to medicines by the
-- item reference written on the complaint or order (often noisy, Phase 2), and
-- DB3 is the register of record. No existing table gained or lost a column;
-- ministry_officers and public_alerts only gained foreign keys on existing columns.

PRAGMA foreign_keys = ON;

-- 6. (Phase 3) Regulatory authorities: the bodies officers belong to and that
-- issue alerts and recalls, with their place in the government hierarchy
CREATE TABLE IF NOT EXISTS regulatory_authorities (
    authority_id         TEXT PRIMARY KEY,
    authority_name       TEXT NOT NULL UNIQUE,
    short_name           TEXT,
    authority_type       TEXT CHECK(authority_type IN ('ministry','drug_regulator','laboratory',
                                                       'consumer_protection','quasi_judicial','helpline')),
    jurisdiction         TEXT,
    parent_authority_id  TEXT,
    registration_status  TEXT NOT NULL DEFAULT 'registered'
                         CHECK(registration_status IN ('registered','auto_registered')),
    FOREIGN KEY (parent_authority_id) REFERENCES regulatory_authorities(authority_id)
);

-- 1. Ministry officers table
CREATE TABLE IF NOT EXISTS ministry_officers (
    officer_id   TEXT PRIMARY KEY,
    full_name    TEXT NOT NULL,
    department   TEXT NOT NULL,
    rank         TEXT,
    email        TEXT UNIQUE,
    phone        TEXT,
    active       INTEGER NOT NULL DEFAULT 1,
    -- Phase 3: the department is the authority the officer serves
    FOREIGN KEY (department) REFERENCES regulatory_authorities(authority_name)
);

-- 2. Complaints table: reports of suspected fake or substandard items
CREATE TABLE IF NOT EXISTS complaints (
    complaint_id        TEXT PRIMARY KEY,
    complaint_item_ref  TEXT NOT NULL,
    complaint_date      DATETIME NOT NULL DEFAULT (datetime('now')),
    complainant_type    TEXT NOT NULL CHECK(complainant_type IN ('consumer','vendor','manufacturer','ngo','authority','auto_system')),
    complainant_name    TEXT,
    complainant_contact TEXT,
    purchase_location   TEXT,
    complaint_category  TEXT NOT NULL CHECK(complaint_category IN (
                            'counterfeit','substandard','expired','mislabeled',
                            'tampered_packaging','adverse_reaction','price_gouging','other')),
    description         TEXT,
    severity_level      TEXT NOT NULL DEFAULT 'medium'
                        CHECK(severity_level IN ('low','medium','high','critical')),
    status              TEXT NOT NULL DEFAULT 'open'
                        CHECK(status IN ('open','under_investigation','lab_testing','resolved','escalated','closed')),
    assigned_officer_id TEXT,
    date_assigned       DATE,
    resolution_date     DATE,
    resolution_notes    TEXT,
    action_taken        TEXT CHECK(action_taken IN (
                            'warning_issued','product_recalled','distributor_suspended',
                            'manufacturer_fined','criminal_referral','case_dismissed','monitoring')),
    auto_generated      INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (assigned_officer_id) REFERENCES ministry_officers(officer_id)
);

-- 3. Ministry blacklist: confirmed counterfeit or dangerous items
CREATE TABLE IF NOT EXISTS ministry_blacklist (
    blacklist_id        TEXT PRIMARY KEY,
    item_ref            TEXT NOT NULL UNIQUE,
    complaint_id        TEXT,
    blacklisted_on      DATE NOT NULL,
    blacklisted_by      TEXT NOT NULL,
    reason              TEXT NOT NULL,
    severity            TEXT NOT NULL CHECK(severity IN ('low','medium','high','critical')),
    health_risk         TEXT,
    public_alert_issued INTEGER NOT NULL DEFAULT 0,
    alert_date          DATE,
    active              INTEGER NOT NULL DEFAULT 1,
    removed_on          DATE,
    removal_reason      TEXT,
    FOREIGN KEY (complaint_id) REFERENCES complaints(complaint_id)
);

-- 4. Lab reports: forensic analysis of tested items
CREATE TABLE IF NOT EXISTS lab_reports (
    lab_report_id       TEXT PRIMARY KEY,
    complaint_id        TEXT NOT NULL,
    item_ref            TEXT NOT NULL,
    lab_name            TEXT NOT NULL,
    lab_accreditation   TEXT,
    sample_received_on  DATE NOT NULL,
    test_completed_on   DATE,
    parameters_tested   TEXT NOT NULL,
    result              TEXT NOT NULL DEFAULT 'pending'
                        CHECK(result IN ('pass','fail','inconclusive','pending')),
    active_ingredient_match   INTEGER,
    contaminants_found  TEXT,
    findings_summary    TEXT,
    recommendation      TEXT,
    FOREIGN KEY (complaint_id) REFERENCES complaints(complaint_id)
);

-- 5. Public alerts: safety notices issued to consumers
CREATE TABLE IF NOT EXISTS public_alerts (
    alert_id     TEXT PRIMARY KEY,
    item_ref     TEXT NOT NULL,
    issued_on    DATETIME NOT NULL,
    channel      TEXT,
    message      TEXT NOT NULL,
    issued_by    TEXT,
    active       INTEGER NOT NULL DEFAULT 1,
    -- Phase 3: the authority that issued the alert
    FOREIGN KEY (issued_by) REFERENCES regulatory_authorities(authority_name)
);

-- 7. (Phase 3) Recall notices: statutory recall orders for a medicine batch,
-- tied to the complaint and laboratory report that justified them and the
-- public alert that announced them
CREATE TABLE IF NOT EXISTS recall_notices (
    recall_id           TEXT PRIMARY KEY,
    authority_id        TEXT NOT NULL,
    issuing_officer_id  TEXT,
    item_ref            TEXT NOT NULL,     -- medicine id as gazetted (business id, DB3 product_uid)
    batch_ref           TEXT,              -- manufacturer batch number as gazetted
    manufacturer_ref    TEXT,              -- business id (DB3 manufacturers.manufacturer_id)
    recall_class        TEXT NOT NULL CHECK(recall_class IN ('I','II','III')),
    reason              TEXT NOT NULL,
    issued_on           DATE NOT NULL,
    status              TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','completed','withdrawn')),
    complaint_id        TEXT,
    lab_report_id       TEXT,
    alert_id            TEXT,
    FOREIGN KEY (authority_id) REFERENCES regulatory_authorities(authority_id),
    FOREIGN KEY (issuing_officer_id) REFERENCES ministry_officers(officer_id),
    FOREIGN KEY (complaint_id) REFERENCES complaints(complaint_id),
    FOREIGN KEY (lab_report_id) REFERENCES lab_reports(lab_report_id),
    FOREIGN KEY (alert_id) REFERENCES public_alerts(alert_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_comp_item_ref  ON complaints(complaint_item_ref);
CREATE INDEX IF NOT EXISTS idx_comp_status    ON complaints(status);
CREATE INDEX IF NOT EXISTS idx_comp_severity  ON complaints(severity_level);
CREATE INDEX IF NOT EXISTS idx_comp_date      ON complaints(complaint_date);
CREATE INDEX IF NOT EXISTS idx_bl_item_ref    ON ministry_blacklist(item_ref);
CREATE INDEX IF NOT EXISTS idx_bl_active      ON ministry_blacklist(active);
CREATE INDEX IF NOT EXISTS idx_lab_item_ref   ON lab_reports(item_ref);
CREATE INDEX IF NOT EXISTS idx_recall_item    ON recall_notices(item_ref);
CREATE INDEX IF NOT EXISTS idx_officer_dept   ON ministry_officers(department);

-- Phase 3 integrity triggers: an officer posted to, or an alert issued by, an
-- authority not yet on file records that authority, so the foreign key never dangles.
CREATE TRIGGER IF NOT EXISTS trg_officer_register_authority_ins
AFTER INSERT ON ministry_officers
BEGIN
    INSERT OR IGNORE INTO regulatory_authorities (authority_id, authority_name, registration_status)
    VALUES ('AUTH-AUTO-' || upper(hex(randomblob(4))), NEW.department, 'auto_registered');
END;

CREATE TRIGGER IF NOT EXISTS trg_officer_register_authority_upd
AFTER UPDATE OF department ON ministry_officers
BEGIN
    INSERT OR IGNORE INTO regulatory_authorities (authority_id, authority_name, registration_status)
    VALUES ('AUTH-AUTO-' || upper(hex(randomblob(4))), NEW.department, 'auto_registered');
END;

CREATE TRIGGER IF NOT EXISTS trg_alert_register_authority_ins
AFTER INSERT ON public_alerts
WHEN NEW.issued_by IS NOT NULL
BEGIN
    INSERT OR IGNORE INTO regulatory_authorities (authority_id, authority_name, registration_status)
    VALUES ('AUTH-AUTO-' || upper(hex(randomblob(4))), NEW.issued_by, 'auto_registered');
END;

CREATE TRIGGER IF NOT EXISTS trg_alert_register_authority_upd
AFTER UPDATE OF issued_by ON public_alerts
WHEN NEW.issued_by IS NOT NULL
BEGIN
    INSERT OR IGNORE INTO regulatory_authorities (authority_id, authority_name, registration_status)
    VALUES ('AUTH-AUTO-' || upper(hex(randomblob(4))), NEW.issued_by, 'auto_registered');
END;
