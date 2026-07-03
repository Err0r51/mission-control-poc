# Local Development

Deployment registration and pipeline operations run inside containers so the checked-in
`.env` values continue to work unchanged.

## Prerequisites

- A container runtime that provides `compose` (Podman or Docker). The commands below use
  `podman compose`; substitute `docker compose` if you use Docker.
- `uv` and Python 3.12 are only needed for host-side checks (`ruff`, `compileall`). The
  stack itself runs entirely in containers.

## Environment configuration

Copy the example environment file before starting the stack:

```bash
cp .env.example .env
```

Compose auto-loads `.env` and interpolates it into every service. The checked-in defaults
are local-only placeholders that work as-is; no other secrets are required.

## Build the worker image

`prefect-worker`, `prefect-deploy`, and `metabase-bootstrap` all build from the shared
uv-based `Dockerfile.worker` image, which bakes in the flow code and SQL files. Build it
explicitly with:

```bash
podman compose build prefect-worker
```

The `--build` flags in the steps below rebuild this image on demand, so an explicit build
is optional.

## Startup order

1. Start the shared infrastructure:

   ```bash
   podman compose up -d postgres prefect-server metabase
   ```

2. Register the work pool and the single parent deployment:

   ```bash
   podman compose up --build prefect-deploy
   ```

3. Start the Prefect process worker:

   ```bash
   podman compose up -d --build prefect-worker
   ```

4. Trigger the manual parent deployment and stream logs until completion:

   ```bash
   podman compose exec prefect-server prefect deployment run soc_metrics_pipeline/manual --watch
   ```

5. Bootstrap Metabase and register the read-only warehouse connection:

   ```bash
   podman compose up --build metabase-bootstrap
   ```

The `prefect-deploy` and `metabase-bootstrap` services are one-shot containers. After
changing `prefect.yaml`, flow code, or `src/metabase_bootstrap.py`, rerun the relevant
command with `--build` so the rebuilt image is what actually executes.

## Inspect the registered objects

Inspect the work pool from inside `prefect-server`:

```bash
podman compose exec prefect-server sh -lc 'prefect work-pool inspect "$PREFECT_WORK_POOL"'
```

List deployments and confirm only the parent deployment exists:

```bash
podman compose exec prefect-server prefect deployment ls
```

Expected deployment name:

```text
soc_metrics_pipeline/manual
```

No `ingest_raw/*` or `build_analytics/*` deployment should be present.

## Verify warehouse data with `psql`

After the parent flow has run, confirm the data landed. These commands exec into the
`postgres` container and use the in-container environment variables, so they need no
local secrets.

Raw row counts (all four tables should be non-zero):

```bash
podman compose exec postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$WAREHOUSE_DB_NAME" -c "
   SELECT '\''dfir_iris_cases'\'' AS table, count(*) FROM raw.dfir_iris_cases
   UNION ALL SELECT '\''siem_alerts'\'', count(*) FROM raw.siem_alerts
   UNION ALL SELECT '\''shuffle_runs'\'', count(*) FROM raw.shuffle_runs
   UNION ALL SELECT '\''customer_systems'\'', count(*) FROM raw.customer_systems;"'
```

Confirm raw is source-shaped: each row is thin routing columns plus the product-native
`payload`. Normalized and correlated fields (severity labels, resolution, reviewer, linked case,
resolved system) are **not** in raw — they are derived downstream in the analytics ETL. Inspect
a full DFIR-IRIS case payload (real IRIS field names, non-sequential `severity_id`, and the
`modification_history` audit trail):

```bash
podman compose exec postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$WAREHOUSE_DB_NAME" -c "
   SELECT source_case_id, tenant_id, source_event_time, jsonb_pretty(payload)
   FROM raw.dfir_iris_cases
   WHERE source_case_id = '\''IRIS-CASE-00003'\'';"'
```

Inspect one alert payload per product to confirm each is in its real API shape (FortiSIEM
numeric `eventSeverity` + epoch-ms; FortiEDR text `severity` + `yyyy-MM-dd HH:mm:ss`;
SentinelOne nested `threatInfo` + ISO-microsecond timestamps):

```bash
podman compose exec postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$WAREHOUSE_DB_NAME" -c "
   SELECT source_product, jsonb_pretty(payload)
   FROM raw.siem_alerts
   WHERE source_alert_id IN ('\''ALERT-000000'\'','\''ALERT-000003'\'','\''ALERT-000006'\'');"'
```

Confirm the ETL parsed the payloads and materialized the correlations in the `analytics.stg_*`
tables (parse per source, plus the derived alert↔case link):

```bash
podman compose exec postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$WAREHOUSE_DB_NAME" -c "
   SELECT '\''stg_cases'\'' AS object_name, count(*) FROM analytics.stg_cases
   UNION ALL SELECT '\''stg_alerts'\'', count(*) FROM analytics.stg_alerts
   UNION ALL SELECT '\''stg_runs'\'', count(*) FROM analytics.stg_runs
   UNION ALL SELECT '\''stg_systems'\'', count(*) FROM analytics.stg_systems
   UNION ALL SELECT '\''stg_case_alert_links'\'', count(*) FROM analytics.stg_case_alert_links;"'
```

Spot-check that `system_id` was resolved by the hostname join (no unresolved rows) and that
detection latency (MTTD) is well-defined and positive for every incident:

```bash
podman compose exec postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$WAREHOUSE_DB_NAME" -c "
   SELECT count(*) AS alerts,
          count(*) FILTER (WHERE system_id IS NULL) AS unresolved_system_id
   FROM analytics.fact_alerts;
   SELECT count(*) FILTER (WHERE mttd_minutes IS NOT NULL) AS mttd_defined,
          round(min(mttd_minutes), 1) AS mttd_min,
          round(max(mttd_minutes), 1) AS mttd_max
   FROM analytics.fact_incidents;"'
```

Analytics row counts and representative KPI queries:

```bash
podman compose exec postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$WAREHOUSE_DB_NAME" -c "
   SELECT '\''fact_incidents'\'' AS object_name, count(*) FROM analytics.fact_incidents
   UNION ALL SELECT '\''fact_alerts'\'', count(*) FROM analytics.fact_alerts
   UNION ALL SELECT '\''fact_automation_runs'\'', count(*) FROM analytics.fact_automation_runs
   UNION ALL SELECT '\''fact_customer_systems'\'', count(*) FROM analytics.fact_customer_systems
   UNION ALL SELECT '\''kpi_monthly'\'', count(*) FROM analytics.kpi_monthly
   UNION ALL SELECT '\''alert_volume_by_source_monthly'\'', count(*) FROM analytics.alert_volume_by_source_monthly
   UNION ALL SELECT '\''alert_reviews_by_shift'\'', count(*) FROM analytics.alert_reviews_by_shift;"'
```

```bash
podman compose exec postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$WAREHOUSE_DB_NAME" -c "
   SELECT tenant_id, metric_month, incidents_per_month, true_positive_incidents,
          false_positive_rate, incident_escalation_rate, systems_under_monitoring
   FROM analytics.kpi_monthly
   ORDER BY tenant_id, metric_month;"'
```

```bash
podman compose exec postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$WAREHOUSE_DB_NAME" -c "
   SELECT shift_date, shift_name, tenant_id, analyst, reviewed_alert_count
   FROM analytics.alert_reviews_by_shift
   ORDER BY shift_date, shift_name, tenant_id, analyst
   LIMIT 12;"'
```

KPI reconciliation checks (all mismatch counts should be zero):

```bash
podman compose exec postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$WAREHOUSE_DB_NAME" -c "
   WITH rollup AS (
     SELECT metric_month, tenant_id, SUM(alert_count)::bigint AS alert_count
     FROM analytics.alert_volume_by_source_monthly
     GROUP BY 1, 2
   )
   SELECT COUNT(*)::bigint AS mismatched_alert_volume_months
   FROM analytics.kpi_monthly AS k
   LEFT JOIN rollup AS r
     ON r.metric_month = k.metric_month
    AND r.tenant_id = k.tenant_id
   WHERE COALESCE(r.alert_count, 0) <> k.total_alert_volume;"'
```

```bash
podman compose exec postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$WAREHOUSE_DB_NAME" -c "
   WITH expected AS (
     SELECT review_shift_date AS shift_date,
            review_shift_name AS shift_name,
            tenant_id,
            reviewed_by_analyst AS analyst,
            COUNT(*)::bigint AS reviewed_alert_count
     FROM analytics.fact_alerts
     WHERE reviewed_at IS NOT NULL
     GROUP BY 1, 2, 3, 4
   )
   SELECT COUNT(*)::bigint AS mismatched_shift_rows
   FROM (
     SELECT COALESCE(a.shift_date, e.shift_date) AS shift_date,
            COALESCE(a.shift_name, e.shift_name) AS shift_name,
            COALESCE(a.tenant_id, e.tenant_id) AS tenant_id,
            COALESCE(a.analyst, e.analyst) AS analyst,
            COALESCE(a.reviewed_alert_count, 0) AS actual_count,
            COALESCE(e.reviewed_alert_count, 0) AS expected_count
     FROM analytics.alert_reviews_by_shift AS a
     FULL OUTER JOIN expected AS e
       USING (shift_date, shift_name, tenant_id, analyst)
   ) AS comparison
   WHERE actual_count <> expected_count;"'
```

```bash
podman compose exec postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$WAREHOUSE_DB_NAME" -c "
   WITH expected AS (
     SELECT k.metric_month,
            k.tenant_id,
            COUNT(*) FILTER (
              WHERE s.monitored_from <= (k.metric_month + INTERVAL '\''1 month'\'' - INTERVAL '\''1 second'\'')
                AND (s.monitored_to IS NULL OR s.monitored_to >= (k.metric_month + INTERVAL '\''1 month'\'' - INTERVAL '\''1 second'\''))
            )::bigint AS expected_systems
     FROM analytics.kpi_monthly AS k
     JOIN analytics.fact_customer_systems AS s
       ON s.tenant_id = k.tenant_id
     GROUP BY 1, 2
   )
   SELECT COUNT(*)::bigint AS mismatched_system_months
   FROM expected AS e
   JOIN analytics.kpi_monthly AS k
     USING (metric_month, tenant_id)
   WHERE e.expected_systems <> k.systems_under_monitoring;"'
```

The prototype analytics contract is:

- `analytics.fact_incidents`
- `analytics.fact_alerts`
- `analytics.fact_automation_runs`
- `analytics.fact_customer_systems`
- `analytics.kpi_monthly`
- `analytics.alert_volume_by_source_monthly`
- `analytics.alert_reviews_by_shift`

### Confirm the read-only role boundary

Metabase connects as `metabase_reader`, which has `USAGE` + `SELECT` on the `analytics`
schema only — no access to `raw` and no write privileges. Reads succeed:

```bash
podman compose exec postgres sh -lc \
  'PGPASSWORD="$METABASE_WAREHOUSE_PASSWORD" psql -U "$METABASE_WAREHOUSE_USER" \
   -d "$WAREHOUSE_DB_NAME" -c "SELECT count(*) FROM analytics.kpi_monthly;"'
```

Raw reads are denied (this command is expected to fail with `permission denied for schema raw`):

```bash
podman compose exec postgres sh -lc \
  'PGPASSWORD="$METABASE_WAREHOUSE_PASSWORD" psql -U "$METABASE_WAREHOUSE_USER" \
   -d "$WAREHOUSE_DB_NAME" -c "SELECT count(*) FROM raw.dfir_iris_cases;"'
```

Writes are denied (this command is expected to fail with `permission denied for schema analytics`):

```bash
podman compose exec postgres sh -lc \
  'PGPASSWORD="$METABASE_WAREHOUSE_PASSWORD" psql -U "$METABASE_WAREHOUSE_USER" \
   -d "$WAREHOUSE_DB_NAME" -c "CREATE TABLE analytics._write_test (x int);"'
```

## Metabase

After the parent flow has created `warehouse.analytics` objects, run the bootstrap service
above and then follow [metabase-setup.md](metabase-setup.md)
for the admin credentials, rerun behavior, and manual dashboard creation path. Use
[metabase-dashboard-playbook.md](metabase-dashboard-playbook.md) for the KPI contract,
canonical table mapping, dashboard filter choices, and query-builder chart definitions.

The parent run should execute `ingest_raw` first and `build_analytics` second before
Metabase is pointed at the warehouse.
