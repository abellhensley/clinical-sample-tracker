-- ============================================================
-- Clinical Trial Sample Operations Tracker
-- Database Schema
-- ============================================================

-- Studies table
CREATE TABLE IF NOT EXISTS studies (
    study_id        TEXT PRIMARY KEY,
    protocol_number TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    phase           TEXT CHECK(phase IN ('Phase 1', 'Phase 2', 'Phase 3', 'Phase 4')),
    therapeutic_area TEXT,
    status          TEXT CHECK(status IN ('Planning', 'Enrolling', 'Enrolled', 'Completed', 'On Hold')),
    enrollment_target INTEGER,
    start_date      DATE,
    primary_completion_date DATE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sites table (investigator sites per study)
CREATE TABLE IF NOT EXISTS sites (
    site_id         TEXT PRIMARY KEY,
    study_id        TEXT NOT NULL REFERENCES studies(study_id),
    site_name       TEXT NOT NULL,
    principal_investigator TEXT,
    country         TEXT,
    status          TEXT CHECK(status IN ('Active', 'Closed', 'On Hold', 'Pending')),
    enrollment_target INTEGER,
    enrolled_count  INTEGER DEFAULT 0,
    activated_date  DATE,
    UNIQUE(study_id, site_id)
);

-- Subjects table (enrolled patients)
CREATE TABLE IF NOT EXISTS subjects (
    subject_id      TEXT PRIMARY KEY,
    site_id         TEXT NOT NULL REFERENCES sites(site_id),
    study_id        TEXT NOT NULL REFERENCES studies(study_id),
    enrollment_date DATE,
    status          TEXT CHECK(status IN ('Screening', 'Enrolled', 'Completed', 'Withdrawn', 'Lost to Follow-up')),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sample types lookup
CREATE TABLE IF NOT EXISTS sample_types (
    sample_type_id  TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    container       TEXT,          -- e.g. 'K2-EDTA tube', 'SST', 'PAXgene'
    volume_ml       REAL,
    storage_temp_c  REAL,          -- e.g. -80, -20, 4
    stability_days  INTEGER        -- stability at storage temp
);

-- Samples table (individual biomarker samples)
CREATE TABLE IF NOT EXISTS samples (
    sample_id       TEXT PRIMARY KEY,
    subject_id      TEXT NOT NULL REFERENCES subjects(subject_id),
    study_id        TEXT NOT NULL REFERENCES studies(study_id),
    site_id         TEXT NOT NULL REFERENCES sites(site_id),
    kit_id          TEXT REFERENCES kits(kit_id),
    sample_type_id  TEXT REFERENCES sample_types(sample_type_id),
    visit           TEXT,          -- e.g. 'Baseline', 'Week 4', 'Week 12'
    timepoint       TEXT,
    collection_date DATE,
    collection_status TEXT CHECK(collection_status IN (
        'Planned', 'Collected', 'Missed', 'Not Required', 'Deviated'
    )),
    volume_collected_ml REAL,
    quality_flag    TEXT CHECK(quality_flag IN ('Pass', 'Fail', 'Pending', NULL)),
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Kits table (sample collection kit logistics)
CREATE TABLE IF NOT EXISTS kits (
    kit_id          TEXT PRIMARY KEY,
    study_id        TEXT NOT NULL REFERENCES studies(study_id),
    site_id         TEXT NOT NULL REFERENCES sites(site_id),
    kit_type        TEXT,
    status          TEXT CHECK(status IN (
        'Manufactured', 'Shipped to Site', 'Received at Site',
        'In Use', 'Used', 'Expired', 'Returned'
    )),
    shipped_to_site_date DATE,
    received_at_site_date DATE,
    expiry_date     DATE,
    lot_number      TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sample shipments (site to central/specialty lab)
CREATE TABLE IF NOT EXISTS shipments (
    shipment_id     TEXT PRIMARY KEY,
    study_id        TEXT NOT NULL REFERENCES studies(study_id),
    site_id         TEXT NOT NULL REFERENCES sites(site_id),
    lab_name        TEXT NOT NULL,
    lab_type        TEXT CHECK(lab_type IN ('Central', 'Specialty', 'Biomarker', 'PK')),
    shipped_date    DATE,
    expected_receipt_date DATE,
    actual_receipt_date DATE,
    status          TEXT CHECK(status IN (
        'Pending', 'In Transit', 'Received', 'Overdue', 'Lost', 'Damaged'
    )),
    temperature_excursion INTEGER DEFAULT 0,  -- 0=No, 1=Yes
    tracking_number TEXT,
    sample_count    INTEGER,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Lab results (data receipt and completeness)
CREATE TABLE IF NOT EXISTS lab_results (
    result_id       TEXT PRIMARY KEY,
    sample_id       TEXT NOT NULL REFERENCES samples(sample_id),
    shipment_id     TEXT REFERENCES shipments(shipment_id),
    lab_name        TEXT NOT NULL,
    assay_name      TEXT,
    result_status   TEXT CHECK(result_status IN (
        'Pending', 'Received', 'Queryable', 'Locked', 'Missing', 'Repeat Required'
    )),
    result_date     DATE,
    expected_result_date DATE,
    is_complete     INTEGER DEFAULT 0,   -- 0=No, 1=Yes
    query_count     INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Issues / deviations table
CREATE TABLE IF NOT EXISTS issues (
    issue_id        TEXT PRIMARY KEY,
    study_id        TEXT REFERENCES studies(study_id),
    site_id         TEXT REFERENCES sites(site_id),
    sample_id       TEXT REFERENCES samples(sample_id),
    shipment_id     TEXT REFERENCES shipments(shipment_id),
    category        TEXT CHECK(category IN (
        'Sample Quality', 'Shipment Delay', 'Temperature Excursion',
        'Missing Data', 'Kit Issue', 'Collection Deviation',
        'Lab Query', 'Documentation'
    )),
    severity        TEXT CHECK(severity IN ('Low', 'Medium', 'High', 'Critical')),
    description     TEXT,
    status          TEXT CHECK(status IN ('Open', 'In Progress', 'Resolved', 'Closed')),
    opened_date     DATE,
    resolved_date   DATE,
    assigned_to     TEXT,
    resolution_notes TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- Views for operational reporting
-- ============================================================

-- Sample collection rate by study and site
CREATE VIEW IF NOT EXISTS vw_sample_collection_rate AS
SELECT
    s.study_id,
    st.protocol_number,
    s.site_id,
    si.site_name,
    si.country,
    COUNT(*) AS total_planned,
    SUM(CASE WHEN s.collection_status = 'Collected' THEN 1 ELSE 0 END) AS collected,
    SUM(CASE WHEN s.collection_status = 'Missed' THEN 1 ELSE 0 END) AS missed,
    SUM(CASE WHEN s.collection_status = 'Deviated' THEN 1 ELSE 0 END) AS deviated,
    ROUND(
        100.0 * SUM(CASE WHEN s.collection_status = 'Collected' THEN 1 ELSE 0 END) / COUNT(*), 1
    ) AS collection_rate_pct
FROM samples s
JOIN studies st ON s.study_id = st.study_id
JOIN sites si ON s.site_id = si.site_id
GROUP BY s.study_id, st.protocol_number, s.site_id, si.site_name, si.country;

-- Data completeness by study
CREATE VIEW IF NOT EXISTS vw_data_completeness AS
SELECT
    s.study_id,
    st.protocol_number,
    lr.lab_name,
    COUNT(*) AS total_results_expected,
    SUM(lr.is_complete) AS results_complete,
    COUNT(*) - SUM(lr.is_complete) AS results_missing,
    ROUND(100.0 * SUM(lr.is_complete) / COUNT(*), 1) AS completeness_pct,
    SUM(lr.query_count) AS total_queries
FROM lab_results lr
JOIN samples s ON lr.sample_id = s.sample_id
JOIN studies st ON s.study_id = st.study_id
GROUP BY s.study_id, st.protocol_number, lr.lab_name;

-- Overdue shipments (shipped >72h without receipt)
CREATE VIEW IF NOT EXISTS vw_overdue_shipments AS
SELECT
    sh.shipment_id,
    sh.study_id,
    st.protocol_number,
    sh.site_id,
    si.site_name,
    sh.lab_name,
    sh.lab_type,
    sh.shipped_date,
    sh.expected_receipt_date,
    sh.sample_count,
    sh.tracking_number,
    CAST(julianday('now') - julianday(sh.shipped_date) AS INTEGER) AS days_in_transit
FROM shipments sh
JOIN studies st ON sh.study_id = st.study_id
JOIN sites si ON sh.site_id = si.site_id
WHERE sh.status IN ('In Transit', 'Overdue')
AND sh.actual_receipt_date IS NULL
AND julianday('now') - julianday(sh.shipped_date) > 3
ORDER BY days_in_transit DESC;

-- Open issues by study, site, and severity
DROP VIEW IF EXISTS vw_open_issues;
CREATE VIEW vw_open_issues AS
SELECT
    i.study_id,
    st.protocol_number,
    i.site_id,
    i.category,
    i.severity,
    COUNT(*) AS issue_count,
    ROUND(AVG(julianday('now') - julianday(i.opened_date)), 1) AS avg_age_days,
    MAX(julianday('now') - julianday(i.opened_date)) AS max_age_days
FROM issues i
JOIN studies st ON i.study_id = st.study_id
WHERE i.status IN ('Open', 'In Progress')
GROUP BY i.study_id, st.protocol_number, i.site_id, i.category, i.severity
ORDER BY
    CASE i.severity WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END,
    issue_count DESC;
