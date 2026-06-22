CREATE TABLE analytics.fact_automation_runs AS
SELECT
    runs.source_run_id,
    runs.tenant_id,
    runs.workflow_name,
    runs.started_at,
    runs.ended_at,
    runs.result_status,
    runs.related_alert_id,
    runs.related_case_id,
    (runs.ended_at - runs.started_at) AS runtime_interval,
    EXTRACT(EPOCH FROM (runs.ended_at - runs.started_at)) AS runtime_seconds,
    EXISTS (
        SELECT 1
        FROM raw.dfir_iris_cases AS cases
        WHERE cases.auto_closed_by_run_id = runs.source_run_id
    ) AS auto_closed_incident
FROM raw.shuffle_runs AS runs;
