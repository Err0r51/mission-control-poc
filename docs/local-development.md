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

Raw row counts (all three tables should be non-zero):

```bash
podman compose exec postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$WAREHOUSE_DB_NAME" -c "
   SELECT '\''dfir_iris_cases'\'' AS table, count(*) FROM raw.dfir_iris_cases
   UNION ALL SELECT '\''siem_alerts'\'', count(*) FROM raw.siem_alerts
   UNION ALL SELECT '\''shuffle_runs'\'', count(*) FROM raw.shuffle_runs;"'
```

Confirm tenant IDs and timestamp columns are populated:

```bash
podman compose exec postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$WAREHOUSE_DB_NAME" -c "
   SELECT tenant_id, opened_at, extracted_at FROM raw.dfir_iris_cases LIMIT 5;"'
```

Analytics row counts and a sample metric:

```bash
podman compose exec postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$WAREHOUSE_DB_NAME" -c "
   SELECT count(*) FROM analytics.soc_daily_summary;"'

podman compose exec postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$WAREHOUSE_DB_NAME" -c "
   SELECT * FROM analytics.case_metrics LIMIT 5;"'
```

The four analytics objects are `analytics.case_metrics`, `analytics.alert_metrics`,
`analytics.automation_metrics`, and `analytics.soc_daily_summary`.

### Confirm the read-only role boundary

Metabase connects as `metabase_reader`, which has `USAGE` + `SELECT` on the `analytics`
schema only — no access to `raw` and no write privileges. Reads succeed:

```bash
podman compose exec postgres sh -lc \
  'PGPASSWORD="$METABASE_WAREHOUSE_PASSWORD" psql -U "$METABASE_WAREHOUSE_USER" \
   -d "$WAREHOUSE_DB_NAME" -c "SELECT count(*) FROM analytics.case_metrics;"'
```

Writes are denied (this command is expected to fail with `permission denied for schema
analytics`):

```bash
podman compose exec postgres sh -lc \
  'PGPASSWORD="$METABASE_WAREHOUSE_PASSWORD" psql -U "$METABASE_WAREHOUSE_USER" \
   -d "$WAREHOUSE_DB_NAME" -c "CREATE TABLE analytics._write_test (x int);"'
```

## Metabase

After the parent flow has created `warehouse.analytics` objects, run the bootstrap service
above and then follow [docs/metabase-setup.md](/Users/frederikjunge/Developer/mission-control-poc/docs/metabase-setup.md)
for the admin credentials, rerun behavior, and manual dashboard creation path.

The parent run should execute `ingest_raw` first and `build_analytics` second before
Metabase is pointed at the warehouse.
