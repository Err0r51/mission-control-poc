-- Correlate cases to their originating SIEM alert.
--
-- DFIR-IRIS carries the originating alert id on case_soc_id (a real SOC/ticket
-- ref), giving a clean 1:1 case<->alert link the ETL materializes here. Alerts
-- that appear on the right-hand side are the escalated ones downstream.

CREATE TABLE analytics.stg_case_alert_links AS
SELECT
    source_case_id,
    source_alert_ref AS source_alert_id
FROM analytics.stg_cases
WHERE source_alert_ref IS NOT NULL;
