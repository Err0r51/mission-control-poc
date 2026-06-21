CREATE TABLE analytics.soc_daily_summary AS
WITH case_opened_daily AS (
    SELECT
        (opened_at AT TIME ZONE 'UTC')::date AS metric_date,
        tenant_id,
        COUNT(*)::bigint AS opened_case_count
    FROM raw.dfir_iris_cases
    GROUP BY (opened_at AT TIME ZONE 'UTC')::date, tenant_id
),
case_closed_daily AS (
    SELECT
        (closed_at AT TIME ZONE 'UTC')::date AS metric_date,
        tenant_id,
        COUNT(*)::bigint AS closed_case_count,
        percentile_cont(0.5) WITHIN GROUP (
            ORDER BY EXTRACT(EPOCH FROM (closed_at - opened_at)) / 3600.0
        ) AS median_case_close_hours
    FROM raw.dfir_iris_cases
    WHERE closed_at IS NOT NULL
    GROUP BY (closed_at AT TIME ZONE 'UTC')::date, tenant_id
),
-- Roll up the already-built per-category alert_metrics (010-040 run in order)
-- so this daily total reconciles with analytics.alert_metrics by construction.
alert_daily AS (
    SELECT
        metric_date,
        tenant_id,
        SUM(total_alert_count)::bigint AS total_alert_count,
        SUM(escalated_alert_count)::bigint AS escalated_alert_count
    FROM analytics.alert_metrics
    GROUP BY metric_date, tenant_id
),
automation_daily AS (
    SELECT
        (started_at AT TIME ZONE 'UTC')::date AS metric_date,
        tenant_id,
        COUNT(*)::bigint AS total_automation_run_count,
        COUNT(*) FILTER (WHERE result_status = 'success')::bigint
            AS success_automation_run_count,
        COUNT(*) FILTER (WHERE result_status = 'failure')::bigint
            AS failure_automation_run_count,
        percentile_cont(0.5) WITHIN GROUP (
            ORDER BY EXTRACT(EPOCH FROM (ended_at - started_at))
        ) AS median_automation_runtime_seconds
    FROM raw.shuffle_runs
    GROUP BY (started_at AT TIME ZONE 'UTC')::date, tenant_id
),
soc_activity_keys AS (
    SELECT metric_date, tenant_id FROM case_opened_daily
    UNION
    SELECT metric_date, tenant_id FROM case_closed_daily
    UNION
    SELECT metric_date, tenant_id FROM alert_daily
    UNION
    SELECT metric_date, tenant_id FROM automation_daily
)
SELECT
    keys.metric_date,
    keys.tenant_id,
    COALESCE(opened.opened_case_count, 0) AS opened_case_count,
    COALESCE(closed.closed_case_count, 0) AS closed_case_count,
    closed.median_case_close_hours,
    COALESCE(alerts.total_alert_count, 0) AS total_alert_count,
    COALESCE(alerts.escalated_alert_count, 0) AS escalated_alert_count,
    COALESCE(automation.total_automation_run_count, 0) AS total_automation_run_count,
    COALESCE(automation.success_automation_run_count, 0)
        AS success_automation_run_count,
    COALESCE(automation.failure_automation_run_count, 0)
        AS failure_automation_run_count,
    automation.median_automation_runtime_seconds
FROM soc_activity_keys AS keys
LEFT JOIN case_opened_daily AS opened
    ON opened.metric_date = keys.metric_date
   AND opened.tenant_id = keys.tenant_id
LEFT JOIN case_closed_daily AS closed
    ON closed.metric_date = keys.metric_date
   AND closed.tenant_id = keys.tenant_id
LEFT JOIN alert_daily AS alerts
    ON alerts.metric_date = keys.metric_date
   AND alerts.tenant_id = keys.tenant_id
LEFT JOIN automation_daily AS automation
    ON automation.metric_date = keys.metric_date
   AND automation.tenant_id = keys.tenant_id;
