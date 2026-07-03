-- Parse DFIR-IRIS case payloads into typed columns.
--
-- Reverses the real (non-sequential) IRIS enums, derives the lifecycle status
-- from state_id, and reconstructs precise opened/closed timestamps and the
-- closing principal from the modification_history audit trail (open_date /
-- close_date are only date-granular in IRIS, so the history is what carries the
-- minute precision MTTR needs). occurred_at (the detection anchor for MTTD) and
-- the assigned team come from the SOC custom attributes.

CREATE TABLE analytics.stg_cases AS
SELECT
    c.source_case_id,
    c.tenant_id,
    CASE (c.payload->>'severity_id')::int
        WHEN 4 THEN 'low'
        WHEN 1 THEN 'medium'
        WHEN 5 THEN 'high'
        WHEN 6 THEN 'critical'
        ELSE 'medium'
    END AS severity,
    CASE WHEN (c.payload->>'state_id')::int = 9 THEN 'closed' ELSE 'open' END
        AS status,
    CASE
        WHEN (c.payload->>'state_id')::int <> 9 THEN NULL
        WHEN (c.payload->>'status_id')::int IN (2, 4) THEN 'true_positive'
        WHEN (c.payload->>'status_id')::int = 1 THEN 'false_positive'
        ELSE 'undetermined'
    END AS case_outcome,
    (c.payload#>>'{custom_attributes,soc,occurred_at}')::timestamptz AS occurred_at,
    hist.opened_at,
    hist.closed_at,
    c.payload#>>'{custom_attributes,soc,assigned_team}' AS assigned_team,
    c.payload#>>'{owner,user_name}' AS assigned_analyst,
    hist.close_principal,
    c.payload->>'case_soc_id' AS source_alert_ref
FROM raw.dfir_iris_cases AS c
LEFT JOIN LATERAL (
    SELECT
        to_timestamp(
            max((e.key)::double precision)
                FILTER (WHERE e.value->>'action' = 'case opened')
        ) AS opened_at,
        to_timestamp(
            max((e.key)::double precision)
                FILTER (WHERE e.value->>'action' = 'case closed')
        ) AS closed_at,
        max(e.value->>'user')
            FILTER (WHERE e.value->>'action' = 'case closed') AS close_principal
    FROM jsonb_each(c.payload->'modification_history') AS e
) AS hist ON true;
