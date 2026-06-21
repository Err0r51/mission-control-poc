CREATE TABLE analytics.alert_metrics AS
WITH alert_domain_input AS (
    SELECT
        event_at::date AS metric_date,
        tenant_id,
        detection_name AS alert_category,
        severity,
        triage_status
    FROM raw.siem_alerts
)
SELECT
    metric_date,
    tenant_id,
    alert_category,
    severity,
    COUNT(*)::bigint AS total_alert_count,
    COUNT(*) FILTER (WHERE triage_status = 'new')::bigint AS new_alert_count,
    COUNT(*) FILTER (WHERE triage_status = 'in_progress')::bigint
        AS in_progress_alert_count,
    COUNT(*) FILTER (WHERE triage_status = 'escalated')::bigint
        AS escalated_alert_count,
    COUNT(*) FILTER (WHERE triage_status = 'closed')::bigint AS closed_alert_count
FROM alert_domain_input
GROUP BY metric_date, tenant_id, alert_category, severity;
