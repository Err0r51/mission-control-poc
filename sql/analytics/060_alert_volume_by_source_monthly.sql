CREATE TABLE analytics.alert_volume_by_source_monthly AS
SELECT
    metric_month,
    tenant_id,
    source_product,
    COUNT(*)::bigint AS alert_count
FROM analytics.fact_alerts
GROUP BY metric_month, tenant_id, source_product;
