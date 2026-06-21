CREATE TABLE analytics.automation_metrics AS
WITH automation_domain_input AS (
    SELECT
        tenant_id,
        workflow_name AS automation_name,
        result_status,
        EXTRACT(EPOCH FROM (ended_at - started_at)) AS runtime_seconds
    FROM raw.shuffle_runs
)
SELECT
    tenant_id,
    automation_name,
    COUNT(*)::bigint AS total_run_count,
    COUNT(*) FILTER (WHERE result_status = 'success')::bigint AS success_run_count,
    COUNT(*) FILTER (WHERE result_status = 'failure')::bigint AS failure_run_count,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY runtime_seconds)
        AS median_runtime_seconds
FROM automation_domain_input
GROUP BY tenant_id, automation_name;
