CREATE TABLE analytics.kpi_monthly AS
WITH incident_monthly AS (
    SELECT
        date_trunc('month', opened_at AT TIME ZONE 'UTC')::date AS metric_month,
        tenant_id,
        COUNT(*)::bigint AS incidents_per_month,
        COUNT(*) FILTER (WHERE case_outcome = 'true_positive')::bigint
            AS true_positive_incidents,
        COUNT(*) FILTER (WHERE mttd_minutes IS NOT NULL)::bigint AS mttd_incident_count,
        SUM(mttd_minutes) FILTER (WHERE mttd_minutes IS NOT NULL) AS total_mttd_minutes,
        AVG(mttd_minutes) FILTER (WHERE mttd_minutes IS NOT NULL) AS mean_mttd_minutes,
        COUNT(*) FILTER (WHERE mttr_minutes IS NOT NULL)::bigint AS mttr_incident_count,
        SUM(mttr_minutes) FILTER (WHERE mttr_minutes IS NOT NULL) AS total_mttr_minutes,
        AVG(mttr_minutes) FILTER (WHERE mttr_minutes IS NOT NULL) AS mean_mttr_minutes,
        COUNT(*) FILTER (WHERE closure_mode = 'automation')::bigint
            AS automatically_closed_incidents
    FROM analytics.fact_incidents
    GROUP BY 1, 2
),
alert_monthly AS (
    SELECT
        metric_month,
        tenant_id,
        COUNT(*)::bigint AS total_alert_volume,
        COUNT(*) FILTER (WHERE resolution = 'false_positive')::bigint
            AS false_positives,
        COUNT(*) FILTER (WHERE resolution = 'true_positive')::bigint
            AS true_positive_alerts,
        COUNT(*) FILTER (
            WHERE resolution IN ('true_positive', 'false_positive')
        )::bigint AS resolved_tp_fp_alerts,
        COUNT(*) FILTER (WHERE escalated_to_incident)::bigint
            AS escalated_alerts
    FROM analytics.fact_alerts
    GROUP BY 1, 2
),
activity_month_seeds AS (
    SELECT metric_month, tenant_id FROM incident_monthly
    UNION
    SELECT metric_month, tenant_id FROM alert_monthly
    UNION
    SELECT
        date_trunc('month', monitored_from AT TIME ZONE 'UTC')::date AS metric_month,
        tenant_id
    FROM analytics.fact_customer_systems
    UNION
    SELECT
        date_trunc('month', monitored_to AT TIME ZONE 'UTC')::date AS metric_month,
        tenant_id
    FROM analytics.fact_customer_systems
    WHERE monitored_to IS NOT NULL
),
activity_month_bounds AS (
    SELECT
        MIN(metric_month) AS min_month,
        MAX(metric_month) AS max_month
    FROM activity_month_seeds
),
activity_tenants AS (
    SELECT DISTINCT tenant_id
    FROM activity_month_seeds
),
activity_months AS (
    SELECT
        tenants.tenant_id,
        generate_series(bounds.min_month, bounds.max_month, INTERVAL '1 month')::date
            AS metric_month
    FROM activity_month_bounds AS bounds
    CROSS JOIN activity_tenants AS tenants
),
system_monthly AS (
    SELECT
        month_keys.metric_month,
        systems.tenant_id,
        COUNT(*) FILTER (
            WHERE systems.monitored_from
                    <= (
                        month_keys.metric_month + INTERVAL '1 month' - INTERVAL '1 second'
                    )
              AND (
                    systems.monitored_to IS NULL
                    OR systems.monitored_to
                        >= (
                            month_keys.metric_month
                            + INTERVAL '1 month'
                            - INTERVAL '1 second'
                        )
                  )
        )::bigint AS systems_under_monitoring
    FROM activity_months AS month_keys
    JOIN analytics.fact_customer_systems AS systems
        ON systems.tenant_id = month_keys.tenant_id
    GROUP BY 1, 2
),
all_months AS (
    SELECT metric_month, tenant_id FROM activity_months
)
SELECT
    months.metric_month,
    months.tenant_id,
    COALESCE(incidents.incidents_per_month, 0) AS incidents_per_month,
    COALESCE(incidents.true_positive_incidents, 0) AS true_positive_incidents,
    COALESCE(alerts.false_positives, 0) AS false_positives,
    COALESCE(alerts.true_positive_alerts, 0) AS true_positive_alerts,
    COALESCE(alerts.resolved_tp_fp_alerts, 0) AS resolved_tp_fp_alerts,
    COALESCE(alerts.escalated_alerts, 0) AS escalated_alerts,
    CASE
        WHEN COALESCE(alerts.resolved_tp_fp_alerts, 0) = 0 THEN NULL
        ELSE alerts.false_positives::numeric / alerts.resolved_tp_fp_alerts::numeric
    END AS false_positive_rate,
    CASE
        WHEN COALESCE(alerts.resolved_tp_fp_alerts, 0) = 0 THEN NULL
        ELSE alerts.true_positive_alerts::numeric
            / alerts.resolved_tp_fp_alerts::numeric
    END AS true_positive_rate,
    CASE
        WHEN COALESCE(alerts.total_alert_volume, 0) = 0 THEN NULL
        ELSE alerts.escalated_alerts::numeric / alerts.total_alert_volume::numeric
    END AS incident_escalation_rate,
    COALESCE(incidents.mttd_incident_count, 0) AS mttd_incident_count,
    COALESCE(incidents.total_mttd_minutes, 0) AS total_mttd_minutes,
    incidents.mean_mttd_minutes,
    COALESCE(incidents.mttr_incident_count, 0) AS mttr_incident_count,
    COALESCE(incidents.total_mttr_minutes, 0) AS total_mttr_minutes,
    incidents.mean_mttr_minutes,
    COALESCE(systems.systems_under_monitoring, 0) AS systems_under_monitoring,
    COALESCE(incidents.automatically_closed_incidents, 0)
        AS automatically_closed_incidents,
    COALESCE(alerts.total_alert_volume, 0) AS total_alert_volume
FROM all_months AS months
LEFT JOIN incident_monthly AS incidents
    ON incidents.metric_month = months.metric_month
   AND incidents.tenant_id = months.tenant_id
LEFT JOIN alert_monthly AS alerts
    ON alerts.metric_month = months.metric_month
   AND alerts.tenant_id = months.tenant_id
LEFT JOIN system_monthly AS systems
    ON systems.metric_month = months.metric_month
   AND systems.tenant_id = months.tenant_id;
