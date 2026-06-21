CREATE TABLE analytics.case_metrics AS
WITH case_domain_input AS (
    SELECT
        tenant_id,
        severity,
        status,
        opened_at,
        closed_at
    FROM raw.dfir_iris_cases
)
SELECT
    tenant_id,
    severity,
    COUNT(*)::bigint AS total_case_count,
    COUNT(*) FILTER (WHERE status = 'open')::bigint AS open_case_count,
    COUNT(*) FILTER (WHERE status = 'closed')::bigint AS closed_case_count,
    percentile_cont(0.5) WITHIN GROUP (
        ORDER BY EXTRACT(EPOCH FROM (closed_at - opened_at)) / 3600.0
    ) FILTER (WHERE status = 'closed' AND closed_at IS NOT NULL)
        AS median_time_to_close_hours
FROM case_domain_input
GROUP BY tenant_id, severity;
