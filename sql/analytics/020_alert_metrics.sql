CREATE TABLE analytics.fact_alerts AS
SELECT
    alerts.source_alert_id,
    alerts.tenant_id,
    alerts.source_product,
    alerts.system_id,
    alerts.detection_name,
    alerts.severity,
    alerts.event_at,
    alerts.triage_status,
    alerts.resolution,
    alerts.linked_case_id,
    alerts.reviewed_at,
    alerts.reviewed_by_analyst,
    CASE
        WHEN alerts.reviewed_at IS NULL THEN NULL
        WHEN EXTRACT(HOUR FROM alerts.reviewed_at AT TIME ZONE 'UTC') BETWEEN 6 AND 13
            THEN 'day'
        WHEN EXTRACT(HOUR FROM alerts.reviewed_at AT TIME ZONE 'UTC') BETWEEN 14 AND 21
            THEN 'evening'
        ELSE 'night'
    END AS review_shift_name,
    (alerts.reviewed_at AT TIME ZONE 'UTC')::date AS review_shift_date,
    (alerts.event_at AT TIME ZONE 'UTC')::date AS event_date_utc,
    date_trunc('month', alerts.event_at AT TIME ZONE 'UTC')::date AS metric_month,
    (alerts.triage_status = 'escalated') AS escalated_to_incident
FROM raw.siem_alerts AS alerts;
