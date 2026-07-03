-- Parse security-alert payloads into typed columns, dispatching on the product.
--
-- Each product returns a different native shape, so every normalized column is a
-- per-product CASE: FortiSIEM numeric severity (1-10) + epoch-ms timestamps;
-- FortiEDR text severity/classification + "yyyy-MM-dd HH:mm:ss" timestamps;
-- SentinelOne 2-level confidence + ISO-microsecond timestamps. Reviewer identity
-- is only available where the real API carries it (FortiSIEM clearing user, S1
-- activity-feed username); FortiEDR has none and is filled from the escalated
-- case owner later, in fact_alerts.
--
-- triage_status here is the base per-product state; fact_alerts overrides it to
-- 'escalated' when the alert is linked to a case.

CREATE TABLE analytics.stg_alerts AS
SELECT
    a.source_alert_id,
    a.tenant_id,
    a.source_product,
    CASE a.source_product
        WHEN 'FortiSIEM' THEN a.payload->>'incidentTitle'
        WHEN 'FortiEDR' THEN a.payload->>'process'
        ELSE a.payload#>>'{threatInfo,threatName}'
    END AS detection_name,
    CASE a.source_product
        WHEN 'FortiSIEM' THEN CASE
            WHEN (a.payload->>'eventSeverity')::int >= 10 THEN 'critical'
            WHEN (a.payload->>'eventSeverity')::int >= 7 THEN 'high'
            WHEN (a.payload->>'eventSeverity')::int >= 4 THEN 'medium'
            ELSE 'low'
        END
        WHEN 'FortiEDR' THEN lower(a.payload->>'severity')
        ELSE CASE a.payload#>>'{threatInfo,confidenceLevel}'
            WHEN 'malicious' THEN 'high'
            ELSE 'medium'
        END
    END AS severity,
    CASE a.source_product
        WHEN 'FortiSIEM'
            THEN to_timestamp((a.payload->>'incidentFirstSeen')::bigint / 1000.0)
        WHEN 'FortiEDR'
            THEN (a.payload->>'firstSeen')::timestamp AT TIME ZONE 'UTC'
        ELSE (a.payload->>'createdAt')::timestamptz
    END AS event_at,
    CASE a.source_product
        WHEN 'FortiSIEM' THEN
            CASE WHEN (a.payload->>'incidentStatus')::int <> 0
                 THEN 'closed' ELSE 'new' END
        WHEN 'FortiEDR' THEN
            CASE WHEN (a.payload->>'handled')::boolean
                 THEN 'closed' ELSE 'new' END
        ELSE CASE a.payload#>>'{threatInfo,incidentStatus}'
            WHEN 'resolved' THEN 'closed'
            WHEN 'in_progress' THEN 'in_progress'
            ELSE 'new'
        END
    END AS triage_status,
    CASE a.source_product
        WHEN 'FortiSIEM' THEN CASE (a.payload->>'incidentReso')::int
            WHEN 2 THEN 'true_positive'
            WHEN 3 THEN 'false_positive'
            ELSE 'undetermined'
        END
        WHEN 'FortiEDR' THEN CASE a.payload->>'classification'
            WHEN 'Malicious' THEN 'true_positive'
            WHEN 'Safe' THEN 'false_positive'
            WHEN 'Likely Safe' THEN 'false_positive'
            ELSE 'undetermined'
        END
        ELSE CASE a.payload#>>'{threatInfo,analystVerdict}'
            WHEN 'true_positive' THEN 'true_positive'
            WHEN 'false_positive' THEN 'false_positive'
            ELSE 'undetermined'
        END
    END AS resolution,
    CASE a.source_product
        WHEN 'FortiSIEM'
            THEN substring(a.payload->>'incidentTarget' FROM 'hostName:([^,]+)')
        WHEN 'FortiEDR' THEN a.payload->>'deviceName'
        ELSE a.payload#>>'{agentRealtimeInfo,agentComputerName}'
    END AS hostname,
    CASE a.source_product
        WHEN 'FortiSIEM' THEN CASE
            WHEN a.payload->>'incidentClearedTime' IS NOT NULL
            THEN to_timestamp((a.payload->>'incidentClearedTime')::bigint / 1000.0)
        END
        WHEN 'FortiEDR' THEN NULL::timestamptz
        ELSE CASE
            WHEN a.payload->'threatTimeline' IS NOT NULL
            THEN (a.payload#>>'{threatTimeline,updatedAt}')::timestamptz
        END
    END AS reviewed_at,
    CASE a.source_product
        WHEN 'FortiSIEM' THEN a.payload->>'incidentClearedUser'
        WHEN 'FortiEDR' THEN NULL
        ELSE a.payload#>>'{threatTimeline,username}'
    END AS reviewed_by
FROM raw.siem_alerts AS a;
