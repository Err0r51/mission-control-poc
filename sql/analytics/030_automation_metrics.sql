CREATE TABLE analytics.automation_metrics AS
SELECT
    tenant_id,
    workflow_name AS automation_name,
    COUNT(*)::bigint AS total_run_count,
    COUNT(*) FILTER (WHERE result_status = 'success')::bigint AS success_run_count,
    COUNT(*) FILTER (WHERE result_status = 'failure')::bigint AS failure_run_count,
    percentile_cont(0.5) WITHIN GROUP (
        ORDER BY EXTRACT(EPOCH FROM (ended_at - started_at))
    ) AS median_runtime_seconds
FROM raw.shuffle_runs
GROUP BY tenant_id, workflow_name;
