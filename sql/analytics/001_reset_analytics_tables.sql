-- The analytics schema itself is provisioned by the Postgres init script
-- (docker/postgres/init/00-init-databases.sh). This file owns only table
-- lifecycle: it resets the analytics tables before the rebuild steps recreate
-- them (010-040).
DROP TABLE IF EXISTS analytics.soc_daily_summary;
DROP TABLE IF EXISTS analytics.automation_metrics;
DROP TABLE IF EXISTS analytics.alert_metrics;
DROP TABLE IF EXISTS analytics.case_metrics;
