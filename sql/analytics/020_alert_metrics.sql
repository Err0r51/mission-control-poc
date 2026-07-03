-- Alert facts from the parsed alert, link, system, and case staging tables.
--
-- Correlation done here (not pre-baked): system_id is resolved by joining the
-- alert's native hostname to the system inventory; escalation is the existence
-- of a case link; triage_status is overridden to 'escalated' for linked alerts.
-- Reviewer attribution is product-faithful -- FortiSIEM/S1 carry their own
-- reviewer, and FortiEDR (which has no reviewer field) inherits the escalated
-- case owner as the effective reviewer, timestamped at case open.

CREATE TABLE analytics.fact_alerts AS
WITH enriched AS (
    SELECT
        alerts.source_alert_id,
        alerts.tenant_id,
        alerts.source_product,
        systems.system_id AS system_id,
        alerts.detection_name,
        alerts.severity,
        alerts.event_at,
        alerts.triage_status AS base_triage_status,
        alerts.resolution,
        links.source_case_id AS linked_case_id,
        COALESCE(
            alerts.reviewed_at,
            CASE
                WHEN alerts.source_product = 'FortiEDR'
                     AND links.source_case_id IS NOT NULL
                THEN cases.opened_at
            END
        ) AS reviewed_at,
        COALESCE(
            alerts.reviewed_by,
            CASE
                WHEN alerts.source_product = 'FortiEDR'
                     AND links.source_case_id IS NOT NULL
                THEN cases.assigned_analyst
            END
        ) AS reviewed_by_analyst
    FROM analytics.stg_alerts AS alerts
    LEFT JOIN analytics.stg_case_alert_links AS links
        ON links.source_alert_id = alerts.source_alert_id
    LEFT JOIN analytics.stg_systems AS systems
        ON systems.hostname = alerts.hostname
    LEFT JOIN analytics.stg_cases AS cases
        ON cases.source_case_id = links.source_case_id
)
SELECT
    source_alert_id,
    tenant_id,
    source_product,
    system_id,
    detection_name,
    severity,
    event_at,
    CASE WHEN linked_case_id IS NOT NULL THEN 'escalated'
         ELSE base_triage_status END AS triage_status,
    resolution,
    linked_case_id,
    reviewed_at,
    reviewed_by_analyst,
    CASE
        WHEN reviewed_at IS NULL THEN NULL
        WHEN EXTRACT(HOUR FROM reviewed_at AT TIME ZONE 'UTC') BETWEEN 6 AND 13
            THEN 'day'
        WHEN EXTRACT(HOUR FROM reviewed_at AT TIME ZONE 'UTC') BETWEEN 14 AND 21
            THEN 'evening'
        ELSE 'night'
    END AS review_shift_name,
    (reviewed_at AT TIME ZONE 'UTC')::date AS review_shift_date,
    (event_at AT TIME ZONE 'UTC')::date AS event_date_utc,
    date_trunc('month', event_at AT TIME ZONE 'UTC')::date AS metric_month,
    (linked_case_id IS NOT NULL) AS escalated_to_incident
FROM enriched;
