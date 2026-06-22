CREATE TABLE analytics.alert_reviews_by_shift AS
SELECT
    review_shift_date AS shift_date,
    review_shift_name AS shift_name,
    tenant_id,
    reviewed_by_analyst AS analyst,
    COUNT(*)::bigint AS reviewed_alert_count
FROM analytics.fact_alerts
WHERE reviewed_at IS NOT NULL
GROUP BY review_shift_date, review_shift_name, tenant_id, reviewed_by_analyst;
