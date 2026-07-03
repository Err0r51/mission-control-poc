-- Monitored-system facts from the parsed system staging table.

CREATE TABLE analytics.fact_customer_systems AS
SELECT
    system_id,
    tenant_id,
    source_product,
    hostname,
    monitored_from,
    monitored_to,
    (monitored_to IS NULL) AS still_monitored
FROM analytics.stg_systems;
