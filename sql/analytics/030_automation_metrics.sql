-- Automation-run facts from the parsed run staging table.
--
-- auto_closed_incident is the reverse of the incident auto-close derivation:
-- a run counts as having auto-closed an incident when some incident names it as
-- its auto_closed_by_run_id.

CREATE TABLE analytics.fact_automation_runs AS
SELECT
    runs.source_run_id,
    runs.tenant_id,
    runs.workflow_name,
    runs.started_at,
    runs.ended_at,
    runs.result_status,
    runs.alert_id AS related_alert_id,
    runs.case_id AS related_case_id,
    (runs.ended_at - runs.started_at) AS runtime_interval,
    EXTRACT(EPOCH FROM (runs.ended_at - runs.started_at)) AS runtime_seconds,
    EXISTS (
        SELECT 1
        FROM analytics.fact_incidents AS incidents
        WHERE incidents.auto_closed_by_run_id = runs.source_run_id
    ) AS auto_closed_incident
FROM analytics.stg_runs AS runs;
