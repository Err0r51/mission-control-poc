CREATE TABLE analytics.fact_incidents AS
WITH first_alerts AS (
    SELECT
        cases.source_case_id,
        MIN(alerts.event_at) FILTER (WHERE alerts.event_at >= cases.occurred_at)
            AS first_alert_at
    FROM raw.dfir_iris_cases AS cases
    LEFT JOIN raw.siem_alerts AS alerts
        ON alerts.linked_case_id = cases.source_case_id
       AND alerts.tenant_id = cases.tenant_id
    GROUP BY cases.source_case_id
)
SELECT
    cases.source_case_id,
    cases.tenant_id,
    cases.severity,
    cases.status,
    cases.occurred_at,
    cases.opened_at,
    cases.closed_at,
    cases.case_outcome,
    cases.assigned_team,
    cases.assigned_analyst,
    cases.closed_by,
    cases.auto_closed_by_run_id,
    CASE
        WHEN cases.auto_closed_by_run_id IS NOT NULL THEN 'automation'
        WHEN cases.closed_at IS NOT NULL THEN 'analyst'
        ELSE 'open'
    END AS closure_mode,
    first_alerts.first_alert_at,
    EXTRACT(EPOCH FROM (first_alerts.first_alert_at - cases.occurred_at)) / 60.0
        AS mttd_minutes,
    EXTRACT(EPOCH FROM (cases.closed_at - cases.opened_at)) / 60.0 AS mttr_minutes
FROM raw.dfir_iris_cases AS cases
LEFT JOIN first_alerts
    ON first_alerts.source_case_id = cases.source_case_id;
