-- Parse monitored customer-system payloads into typed columns.

CREATE TABLE analytics.stg_systems AS
SELECT
    s.system_id,
    s.tenant_id,
    s.payload->>'sensor' AS source_product,
    s.payload->>'hostname' AS hostname,
    (s.payload->>'enrolled_at')::timestamptz AS monitored_from,
    (s.payload->>'retired_at')::timestamptz AS monitored_to
FROM raw.customer_systems AS s;
