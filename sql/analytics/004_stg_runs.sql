-- Parse Shuffle workflow-execution payloads into typed columns.
--
-- started_at/completed_at are Unix epoch SECONDS; status FINISHED means success
-- (FAILED/ABORTED are failure); the triggering alert/case ids live inside the
-- stringified-JSON execution_argument and are unpacked with a nested ->> after
-- casting the string back to jsonb.

CREATE TABLE analytics.stg_runs AS
SELECT
    r.source_run_id,
    r.tenant_id,
    r.payload#>>'{workflow,name}' AS workflow_name,
    to_timestamp((r.payload->>'started_at')::bigint) AS started_at,
    to_timestamp((r.payload->>'completed_at')::bigint) AS ended_at,
    CASE WHEN r.payload->>'status' = 'FINISHED' THEN 'success' ELSE 'failure' END
        AS result_status,
    (r.payload->>'execution_argument')::jsonb->>'alert_id' AS alert_id,
    (r.payload->>'execution_argument')::jsonb->>'case_id' AS case_id
FROM raw.shuffle_runs AS r;
