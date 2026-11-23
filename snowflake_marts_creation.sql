-- =============================================================================
-- OPENFDA PHARMACOVIGILANCE PIPELINE: ANALYTICS DATA MARTS
-- =============================================================================

USE ROLE FDA_ROLE;
USE WAREHOUSE FDA_WH;
USE DATABASE FDA_DB;

CREATE SCHEMA IF NOT EXISTS FDA_DB.MART;

-- 1. Category & Severity Summary Mart
CREATE OR REPLACE VIEW FDA_DB.MART.MART_PHARMACOVIGILANCE_SUMMARY AS
SELECT
    event_category,
    clinical_severity,
    COUNT(safety_report_id) AS total_incidents,
    ROUND(AVG(risk_score), 2) AS avg_risk_score,
    COUNT(CASE WHEN risk_score >= 4 THEN 1 END) AS high_risk_incidents,
    ROUND(
        100.0 * COUNT(CASE WHEN risk_score >= 4 THEN 1 END) / NULLIF(COUNT(safety_report_id), 0),
        1
    ) AS pct_high_risk
FROM FDA_DB.ENRICHED.ADVERSE_EVENTS_ENRICHED
GROUP BY 1, 2
ORDER BY avg_risk_score DESC, total_incidents DESC;

-- 2. Drug-Level Safety Signals Mart (Normalizes comma-separated drug lists)
CREATE OR REPLACE VIEW FDA_DB.MART.MART_DRUG_SAFETY_SIGNALS AS
WITH parsed_drugs AS (
    SELECT
        safety_report_id,
        TRIM(value::STRING) AS drug_name,
        clinical_severity,
        risk_score,
        summary
    FROM FDA_DB.ENRICHED.ADVERSE_EVENTS_ENRICHED,
    LATERAL SPLIT_TO_TABLE(reported_drugs, ',')
    WHERE drug_name IS NOT NULL AND drug_name != ''
)
SELECT
    UPPER(drug_name) AS drug_name,
    COUNT(safety_report_id) AS reported_events_count,
    ROUND(AVG(risk_score), 2) AS avg_drug_risk_score,
    MAX(risk_score) AS max_risk_score,
    COUNT(CASE WHEN clinical_severity IN ('Severe', 'Critical / Fatal') THEN 1 END) AS critical_event_count
FROM parsed_drugs
GROUP BY 1
HAVING COUNT(safety_report_id) >= 1
ORDER BY avg_drug_risk_score DESC, critical_event_count DESC;

-- 3. High-Priority Clinical Triage Queue (Risk Score >= 4)
CREATE OR REPLACE VIEW FDA_DB.MART.MART_HIGH_PRIORITY_TRIAGE_QUEUE AS
SELECT
    safety_report_id,
    risk_score,
    clinical_severity,
    event_category,
    reported_drugs,
    adverse_reactions,
    summary AS clinical_summary,
    enriched_at
FROM FDA_DB.ENRICHED.ADVERSE_EVENTS_ENRICHED
WHERE risk_score >= 4
ORDER BY risk_score DESC, enriched_at DESC;
