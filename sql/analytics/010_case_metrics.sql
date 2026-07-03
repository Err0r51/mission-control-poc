-- Incident facts from the parsed case, link, alert, and run staging tables.
--
-- MTTD = first linked-alert event time minus the case's detection anchor
-- (occurred_at). Both live in the same alert time space now (occurred_at is
-- re-anchored to the constituent alert), so MTTD is well-defined and positive
-- for every incident. MTTR = closed_at - opened_at from the precise history
-- timestamps. A case is auto-closed only when its closing principal is the
-- shuffle-bot; the closing run is then the earliest successful auto-close-
-- incident run whose execution_argument targeted this case.

CREATE TABLE analytics.fact_incidents AS
WITH first_alerts AS (
    SELECT
        links.source_case_id,
        MIN(alerts.event_at) FILTER (WHERE alerts.event_at >= cases.occurred_at)
            AS first_alert_at
    FROM analytics.stg_case_alert_links AS links
    JOIN analytics.stg_alerts AS alerts
        ON alerts.source_alert_id = links.source_alert_id
    JOIN analytics.stg_cases AS cases
        ON cases.source_case_id = links.source_case_id
    GROUP BY links.source_case_id
),
auto_close_runs AS (
    SELECT
        runs.case_id AS source_case_id,
        MIN(runs.source_run_id) AS auto_closed_by_run_id
    FROM analytics.stg_runs AS runs
    WHERE runs.workflow_name = 'auto-close-incident'
      AND runs.result_status = 'success'
      AND runs.case_id IS NOT NULL
    GROUP BY runs.case_id
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
    cases.close_principal AS closed_by,
    CASE WHEN cases.close_principal = 'shuffle-bot'
         THEN auto_close_runs.auto_closed_by_run_id END AS auto_closed_by_run_id,
    CASE
        WHEN cases.close_principal = 'shuffle-bot' THEN 'automation'
        WHEN cases.closed_at IS NOT NULL THEN 'analyst'
        ELSE 'open'
    END AS closure_mode,
    first_alerts.first_alert_at,
    EXTRACT(EPOCH FROM (first_alerts.first_alert_at - cases.occurred_at)) / 60.0
        AS mttd_minutes,
    EXTRACT(EPOCH FROM (cases.closed_at - cases.opened_at)) / 60.0 AS mttr_minutes
FROM analytics.stg_cases AS cases
LEFT JOIN first_alerts
    ON first_alerts.source_case_id = cases.source_case_id
LEFT JOIN auto_close_runs
    ON auto_close_runs.source_case_id = cases.source_case_id;
