-- ============================================================
-- sample_status.sql
-- Sample collection rate queries for operational reporting
-- ============================================================

-- 1. Portfolio-level collection summary
SELECT
    study_id,
    protocol_number,
    SUM(total_planned)    AS portfolio_planned,
    SUM(collected)        AS portfolio_collected,
    SUM(missed)           AS portfolio_missed,
    ROUND(100.0 * SUM(collected) / SUM(total_planned), 1) AS portfolio_collection_rate_pct
FROM vw_sample_collection_rate
GROUP BY study_id, protocol_number
ORDER BY portfolio_collection_rate_pct ASC;


-- 2. Sites below 80% collection threshold (flag for follow-up)
SELECT
    protocol_number,
    site_id,
    site_name,
    country,
    total_planned,
    collected,
    missed,
    collection_rate_pct
FROM vw_sample_collection_rate
WHERE collection_rate_pct < 80
ORDER BY collection_rate_pct ASC;


-- 3. Sample status breakdown by visit timepoint
SELECT
    s.study_id,
    s.visit,
    s.collection_status,
    COUNT(*) AS sample_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (
        PARTITION BY s.study_id, s.visit
    ), 1) AS pct_of_visit
FROM samples s
GROUP BY s.study_id, s.visit, s.collection_status
ORDER BY s.study_id, s.visit, sample_count DESC;


-- 4. Samples collected this week (recent activity)
SELECT
    s.sample_id,
    s.study_id,
    s.site_id,
    si.site_name,
    s.visit,
    s.sample_type_id,
    s.collection_date,
    s.quality_flag
FROM samples s
JOIN sites si ON s.site_id = si.site_id
WHERE s.collection_status = 'Collected'
AND s.collection_date >= date('now', '-7 days')
ORDER BY s.collection_date DESC;


-- 5. Quality fail rate by sample type
SELECT
    st.name AS sample_type,
    COUNT(*) AS total_collected,
    SUM(CASE WHEN s.quality_flag = 'Fail' THEN 1 ELSE 0 END) AS quality_fails,
    ROUND(100.0 * SUM(CASE WHEN s.quality_flag = 'Fail' THEN 1 ELSE 0 END) / COUNT(*), 1) AS fail_rate_pct
FROM samples s
JOIN sample_types st ON s.sample_type_id = st.sample_type_id
WHERE s.collection_status = 'Collected'
GROUP BY st.name
ORDER BY fail_rate_pct DESC;


-- ============================================================
-- data_completeness.sql
-- Data completeness and lab results queries
-- ============================================================

-- 6. Data completeness by study and lab
SELECT
    study_id,
    protocol_number,
    lab_name,
    total_results_expected,
    results_complete,
    results_missing,
    completeness_pct,
    total_queries
FROM vw_data_completeness
ORDER BY completeness_pct ASC;


-- 7. Results with outstanding queries (oldest first)
SELECT
    lr.result_id,
    lr.sample_id,
    s.study_id,
    s.site_id,
    lr.lab_name,
    lr.assay_name,
    lr.result_status,
    lr.query_count,
    lr.expected_result_date,
    CAST(julianday('now') - julianday(lr.expected_result_date) AS INTEGER) AS days_overdue
FROM lab_results lr
JOIN samples s ON lr.sample_id = s.sample_id
WHERE lr.result_status IN ('Queryable', 'Missing', 'Repeat Required')
ORDER BY days_overdue DESC;


-- 8. Database lock readiness by study
-- Checks % complete results as proxy for lock readiness
SELECT
    s.study_id,
    st.protocol_number,
    COUNT(lr.result_id) AS total_results,
    SUM(lr.is_complete) AS locked_results,
    COUNT(lr.result_id) - SUM(lr.is_complete) AS outstanding,
    ROUND(100.0 * SUM(lr.is_complete) / COUNT(lr.result_id), 1) AS lock_readiness_pct,
    SUM(CASE WHEN lr.result_status = 'Queryable' THEN 1 ELSE 0 END) AS open_queries
FROM lab_results lr
JOIN samples s ON lr.sample_id = s.sample_id
JOIN studies st ON s.study_id = st.study_id
GROUP BY s.study_id, st.protocol_number
ORDER BY lock_readiness_pct ASC;


-- ============================================================
-- overdue_shipments.sql
-- Shipment tracking and overdue flagging
-- ============================================================

-- 9. All overdue shipments
SELECT
    shipment_id,
    protocol_number,
    site_name,
    lab_name,
    lab_type,
    shipped_date,
    expected_receipt_date,
    sample_count,
    days_in_transit,
    tracking_number
FROM vw_overdue_shipments;


-- 10. Temperature excursion summary
SELECT
    sh.study_id,
    st.protocol_number,
    sh.lab_name,
    COUNT(*) AS total_shipments,
    SUM(sh.temperature_excursion) AS excursions,
    ROUND(100.0 * SUM(sh.temperature_excursion) / COUNT(*), 1) AS excursion_rate_pct
FROM shipments sh
JOIN studies st ON sh.study_id = st.study_id
GROUP BY sh.study_id, st.protocol_number, sh.lab_name
ORDER BY excursion_rate_pct DESC;


-- ============================================================
-- issue_summary.sql
-- Operational issue tracking and aging
-- ============================================================

-- 11. Open issues by severity
SELECT * FROM vw_open_issues
ORDER BY
    CASE severity WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END;


-- 12. Issue resolution time by category
SELECT
    category,
    COUNT(*) AS total_resolved,
    ROUND(AVG(julianday(resolved_date) - julianday(opened_date)), 1) AS avg_resolution_days,
    MAX(julianday(resolved_date) - julianday(opened_date)) AS max_resolution_days,
    MIN(julianday(resolved_date) - julianday(opened_date)) AS min_resolution_days
FROM issues
WHERE status IN ('Resolved', 'Closed')
AND resolved_date IS NOT NULL
GROUP BY category
ORDER BY avg_resolution_days DESC;


-- 13. Site risk ranking (composite score)
-- Combines collection rate, open issues, overdue shipments
SELECT
    cr.study_id,
    cr.protocol_number,
    cr.site_id,
    cr.site_name,
    cr.country,
    cr.collection_rate_pct,
    COALESCE(oi.critical_issues, 0) AS critical_issues,
    COALESCE(oi.high_issues, 0) AS high_issues,
    -- Risk score: lower collection rate and more issues = higher risk
    ROUND(
        (100 - cr.collection_rate_pct) +
        (COALESCE(oi.critical_issues, 0) * 10) +
        (COALESCE(oi.high_issues, 0) * 5), 1
    ) AS risk_score
FROM vw_sample_collection_rate cr
LEFT JOIN (
    SELECT
        site_id,
        SUM(CASE WHEN severity = 'Critical' THEN issue_count ELSE 0 END) AS critical_issues,
        SUM(CASE WHEN severity = 'High' THEN issue_count ELSE 0 END) AS high_issues
    FROM vw_open_issues
    GROUP BY site_id
) oi ON cr.site_id = oi.site_id
ORDER BY risk_score DESC;
