CREATE TABLE analytics.alert_metrics AS
SELECT
    (event_at AT TIME ZONE 'UTC')::date AS metric_date,
    tenant_id,
    detection_name AS alert_category,
    severity,
    COUNT(*)::bigint AS total_alert_count,
    COUNT(*) FILTER (WHERE triage_status = 'new')::bigint AS new_alert_count,
    COUNT(*) FILTER (WHERE triage_status = 'in_progress')::bigint
        AS in_progress_alert_count,
    COUNT(*) FILTER (WHERE triage_status = 'escalated')::bigint
        AS escalated_alert_count,
    COUNT(*) FILTER (WHERE triage_status = 'closed')::bigint AS closed_alert_count
FROM raw.siem_alerts
GROUP BY (event_at AT TIME ZONE 'UTC')::date, tenant_id, detection_name, severity;
