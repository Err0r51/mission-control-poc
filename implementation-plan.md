# Implementation Plan - SOC Metrics Pipeline

## Goal

Build the local SOC metrics pipeline described in `architecture.md` with a minimal, reviewable implementation:

- Docker Compose local stack with `postgres`, `prefect-server`, `prefect-worker`, and `metabase`
- one PostgreSQL instance with logical databases `prefect`, `metabase`, and `warehouse`
- warehouse schemas limited to `raw` and `analytics`
- deterministic mocked DFIR-IRIS-like, SIEM-like, and Shuffle-like source data
- one deployed parent Prefect flow: `soc_metrics_pipeline`
- plain SQL transformations from `warehouse.raw` to `warehouse.analytics`
- Metabase reading BI-facing objects from `warehouse.analytics`

## Constraints To Preserve

- Do not add Redis, dbt, a staging schema, metadata schemas, cloud deployment files, or real source integrations.
- Do not deploy `ingest_raw` or `build_analytics` separately.
- Do not use a Prefect Docker worker that launches one container per flow run.
- Use uv for Python dependency management and commit both `pyproject.toml` and `uv.lock`.
- Pin Docker image versions and avoid floating tags such as `latest`.
- Keep secrets in `.env`; document required values in `.env.example`.
- Use UTC timestamps and real timestamp types.
- Carry tenant identifiers through raw and analytics layers.

## Current Repository State

The repository already contains the end-to-end local stack and a first-pass raw and
analytics pipeline.

The current implementation focus is expanding that prototype KPI contract:

- extend the deterministic mock sources and raw tables with explicit KPI-driving fields
- add monitored-system inventory to `warehouse.raw`
- replace the coarse aggregate analytics tables with fact tables plus KPI rollups
- keep Metabase on `warehouse.analytics` only

## Target Repository Layout

Create the expected layout:

```text
.
|-- AGENTS.md
|-- README.md
|-- architecture.md
|-- .env.example
|-- docker-compose.yml
|-- Dockerfile.worker
|-- pyproject.toml
|-- uv.lock
|-- flows/
|   |-- ingest_raw.py
|   |-- build_analytics.py
|   `-- soc_metrics_pipeline.py
|-- src/
|   |-- db/
|   |   |-- __init__.py
|   |   |-- connection.py
|   |   `-- sql.py
|   `-- mock_sources/
|       |-- __init__.py
|       |-- customer_systems.py
|       |-- dfir_iris.py
|       |-- shuffle.py
|       `-- siem.py
|-- sql/
|   |-- raw/
|   |   `-- 001_create_raw_tables.sql
|   `-- analytics/
|       |-- 001_reset_analytics_tables.sql
|       |-- 010_case_metrics.sql
|       |-- 020_alert_metrics.sql
|       |-- 030_automation_metrics.sql
|       |-- 040_soc_daily_summary.sql
|       |-- 050_kpi_monthly.sql
|       |-- 060_alert_volume_by_source_monthly.sql
|       `-- 070_alert_reviews_by_shift.sql
`-- docs/
    |-- local-development.md
    `-- metabase-setup.md
```

## Phase 1 - Dependency And Project Scaffolding

Add the Python project skeleton using uv.

Deliverables:

- `pyproject.toml` with runtime dependencies for Prefect, PostgreSQL access, and environment loading
- `uv.lock`
- package directories under `src/`
- flow files under `flows/`
- initial `README.md` with local usage commands
- `.env.example` documenting Postgres, Prefect, and Metabase configuration

Implementation notes:

- Verify current package versions before pinning dependencies.
- Keep the dependency set narrow.
- Prefer one PostgreSQL client library consistently across flows and helper modules.
- Add Ruff configuration in `pyproject.toml`.

Verification:

- `uv sync`
- `uv run ruff check .`
- `uv run python -m compileall flows src`

## Phase 2 - Docker Compose Infrastructure

Create the local service stack.

Deliverables:

- `docker-compose.yml`
- `Dockerfile.worker`
- Postgres initialization SQL or scripts mounted into the Postgres container

Service design:

- `postgres`: one pinned PostgreSQL image
- `prefect-server`: pinned Prefect image, connected to the `prefect` logical database
- `prefect-worker`: project-specific uv-based image, running a Prefect process worker
- `metabase`: pinned Metabase image, connected to the `metabase` logical database

Database initialization:

- create logical databases `prefect`, `metabase`, and `warehouse`
- create warehouse schemas `raw` and `analytics`
- create least-privilege roles where practical:
  - pipeline role with write access to `warehouse.raw` and `warehouse.analytics`
  - Metabase role with read-only access to `warehouse.analytics`

Implementation notes:

- Use pinned base images only.
- Use a uv-based Python image for `Dockerfile.worker`; do not use `python:*-slim`.
- Install dependencies from `pyproject.toml` and `uv.lock`; do not use ad-hoc `pip install`.
- The worker command should run a process worker, not a Docker worker.

Verification:

- `docker compose config`
- `docker compose build prefect-worker`
- `docker compose up -d postgres`
- use `psql` to confirm the three logical databases and two warehouse schemas exist

## Phase 3 - Database Utilities

Add small, explicit database helpers.

Deliverables:

- environment-based warehouse connection helper in `src/db/connection.py`
- SQL file loader/executor in `src/db/sql.py`
- transaction handling for raw ingestion and analytics rebuilds

Implementation notes:

- Keep `/utils` out of scope; this is a Python project, not a Nuxt app.
- Read configuration from environment variables.
- Avoid global connection state.
- Execute SQL files in deterministic filename order.

Verification:
- Ruff checks

## Phase 4 - Deterministic Mock Sources

Implement source-shaped mock data generators.

Deliverables:

- `src/mock_sources/customer_systems.py`
- `src/mock_sources/dfir_iris.py`
- `src/mock_sources/siem.py`
- `src/mock_sources/shuffle.py`

Data principles:

- deterministic fixture generation
- UTC-aware timestamps
- tenant identifier on every record
- stable source record IDs
- realistic enough payloads to support basic SOC metrics
- no real external API clients

Example source shapes:

- DFIR-IRIS-like cases:
  - source case ID
  - tenant ID
  - severity
  - status
  - occurred timestamp
  - opened timestamp
  - closed timestamp where applicable
  - explicit case outcome
  - assigned team and analyst label
  - closure ownership / automation linkage where applicable
  - payload JSON
- SIEM-like alerts:
  - source alert ID
  - tenant ID
  - monitored system ID
  - alert rule
  - severity
  - event timestamp
  - triage status
  - explicit resolution
  - linked case ID for incident lineage
  - review timestamp and analyst where reviewed
  - payload JSON
- Shuffle-like automation runs:
  - source run ID
  - tenant ID
  - workflow name
  - start timestamp
  - end timestamp
  - result status
  - related alert or case ID where useful
  - payload JSON
- monitored customer systems:
  - stable system ID
  - tenant ID
  - source product
  - hostname
  - monitored-from / monitored-to timestamps
  - payload JSON

Verification:

- generator functions return stable record counts
- timestamps are timezone-aware UTC values
- no randomness unless explicitly seeded and documented

## Phase 5 - Raw Schema And Ingestion Flow

Implement `ingest_raw`.

Deliverables:

- `sql/raw/001_create_raw_tables.sql`
- `flows/ingest_raw.py`

Raw table design:

- keep tables source-shaped and minimal
- include `tenant_id`
- include `source_record_id` where useful
- include source timestamps as timestamp types
- include `extracted_at`
- include `payload` as JSONB for flexible source-shaped data

Likely raw tables:

- `raw.dfir_iris_cases`
- `raw.siem_alerts`
- `raw.shuffle_runs`
- `raw.customer_systems`

Flow behavior:

- create raw schema/tables if needed
- generate deterministic mocked records
- load raw tables in a repeatable way
- log inserted record counts through Prefect

Implementation notes:

- For the POC, prefer truncate-and-reload semantics over incremental cursor logic.
- Do not create lineage, cursor, audit, or metadata schemas.
- Do not write any pipeline data to `prefect` or `metabase`.

Verification:

- run `ingest_raw` locally against `warehouse`
- confirm raw row counts with `psql`
- confirm `occurred_at <= opened_at <= closed_at` when closed
- confirm reviewed alerts have both reviewer and review timestamp
- confirm auto-closed incidents have automation linkage
- confirm monitored-system intervals are valid

## Phase 6 - Analytics SQL And Build Flow

Implement `build_analytics`.

Deliverables:

- analytics SQL files in `sql/analytics/`
- `flows/build_analytics.py`

The `raw` and `analytics` schemas are provisioned by the Postgres init script
(`docker/postgres/init/00-init-databases.sh`), so the `sql/analytics/` files own
only table lifecycle: `001_reset_analytics_tables.sql` drops both the old aggregate
tables and the new prototype KPI outputs, and `010`-`070` rebuild the analytics
surface. There is no separate schema-creation SQL file.

Analytics outputs:

- BI-facing fact tables rebuilt from raw
- tenant-aware KPI rollups derived from those facts
- row-level timestamps preserved in facts, with monthly averages exposed in KPI tables

Prototype analytics objects:

- `analytics.fact_incidents`
  - one row per case with severity, analyst, outcome, closure mode, first-alert lineage,
    MTTD, and MTTR
- `analytics.fact_alerts`
  - one row per alert with source product, system, resolution, reviewer, shift bucket,
    and linked case
- `analytics.fact_automation_runs`
  - one row per automation run with alert/case linkage and auto-close support
- `analytics.fact_customer_systems`
  - one row per monitored-system interval for inventory counts
- `analytics.kpi_monthly`
  - monthly per-tenant KPI rollup for incidents, TP/FP metrics, escalation, MTTD, MTTR,
    systems under monitoring, auto-closed incidents, and total alert volume
- `analytics.alert_volume_by_source_monthly`
  - monthly per-tenant per-product alert counts
- `analytics.alert_reviews_by_shift`
  - shift-date / shift-name / tenant / analyst reviewed-alert counts

Flow behavior:

- execute analytics SQL files in deterministic order
- rebuild analytics objects from raw
- log executed SQL files through Prefect

Implementation notes:

- Keep analytics rebuildable and BI-safe.
- Treat this as a prototype KPI contract, not a final production warehouse model.
- Do not let Metabase depend on raw tables for normal dashboards.
- Derive shifts in SQL using fixed UTC buckets: day 06:00-13:59, evening 14:00-21:59,
  night 22:00-05:59.

Verification:

- run `build_analytics` locally after `ingest_raw`
- confirm analytics objects exist in `warehouse.analytics`
- confirm the old aggregate tables are no longer the intended contract
- reconcile `kpi_monthly` against the fact tables
- confirm `metabase_reader` can query `analytics` but not `raw`

## Phase 7 - Parent Flow And Prefect Deployment

Implement the orchestration boundary.

Deliverables:

- `flows/soc_metrics_pipeline.py`
- deployment setup for only `soc_metrics_pipeline`
- worker startup documentation

Flow behavior:

1. call `ingest_raw`
2. call `build_analytics`

Deployment behavior:

- deploy only the parent flow
- keep `ingest_raw` and `build_analytics` as code boundaries, not separate deployments
- run through a Prefect process worker inside Docker

Runtime contract:

- create one process work pool named `soc-metrics-process`
- start the worker with `prefect worker start --pool soc-metrics-process --type process`
- set `PREFECT_API_URL` in the worker container so it targets the Prefect server API
- bake flow code and SQL files into the project-specific worker image
- register only `soc_metrics_pipeline` as a deployment
- import and call `ingest_raw` and `build_analytics` from the parent flow
- keep the default run policy manual until a schedule is explicitly required
- ensure the Prefect server uses only the `prefect` logical database
- ensure the worker uses `warehouse` for pipeline data and never writes pipeline data to `prefect` or `metabase`

Startup sequencing:

1. wait for `postgres` health before starting Prefect services
2. start `prefect-server` against the `prefect` database
3. create the `soc-metrics-process` work pool if it does not exist
4. register the `soc_metrics_pipeline` deployment against that work pool
5. start `prefect-worker` after the Prefect API is reachable

Implementation notes:

- Keep the Prefect server as orchestration and observability only.
- The server should not execute pipeline code.
- The worker image should contain both Python code and SQL files.
- Prefer a Compose one-shot service or documented explicit command for deployment registration.

Verification:

- start Prefect server and worker with Docker Compose
- confirm the work pool and worker are visible
- run the parent deployment
- confirm one parent flow run executes ingestion and analytics in order

## Phase 8 - Metabase Connection And Dashboard Path

Document and validate the BI serving path.

Deliverables:

- `docs/metabase-setup.md`
- read-only Metabase warehouse connection guidance
- create Metabase admin user
- connect warehouse database
- minimal dashboard/query setup instructions

Metabase behavior:

- use `metabase` database only for Metabase application state
- connect to `warehouse` as a BI client
- read from `warehouse.analytics`
- avoid `warehouse.raw` except explicit debugging


Verification:

- confirm Metabase can connect to `warehouse`
- confirm Metabase can see `analytics` objects
- confirm the read-only role cannot write to analytics tables

## Phase 9 - Documentation And Developer Workflow

Add enough documentation to run the POC locally without hidden steps.

Deliverables:

- `README.md`
- `docs/local-development.md`
- `.env.example`

Documentation should cover:

- prerequisites
- environment configuration
- building the worker image
- starting the stack
- running the parent Prefect flow
- verifying raw and analytics data with `psql`
- connecting Metabase to `warehouse.analytics`
- known limitations and out-of-scope items

Verification:

- follow README commands from a clean checkout
- confirm commands do not require undocumented secrets

## Phase 10 - End-To-End Verification

Run final verification after implementation.

Required checks:

- `uv run ruff check .`
- `uv run python -m compileall flows src`
- `docker compose config`
- `docker compose build prefect-worker`
- `docker compose up -d`
- run the `soc_metrics_pipeline` parent flow
- query `warehouse.raw` row counts with `psql`
- query `warehouse.analytics` row counts and sample metrics with `psql`
- confirm Prefect shows one parent deployment and successful flow run state
- confirm Metabase reads from `warehouse.analytics`

Expected acceptance criteria:

- one Docker Compose stack starts locally
- one PostgreSQL container hosts `prefect`, `metabase`, and `warehouse`
- warehouse contains only `raw` and `analytics` schemas for pipeline data
- mocked source data loads into `warehouse.raw`
- analytics objects rebuild from raw using plain SQL
- only `soc_metrics_pipeline` is deployed in Prefect
- Metabase reads dashboard-ready objects from `warehouse.analytics`
- Ruff passes

## Suggested Implementation Order

1. Scaffold Python project, directories, `.env.example`, and README shell.
2. Add Docker Compose and worker image.
3. Add Postgres initialization for logical databases, schemas, and roles.
4. Add DB helpers.
5. Add deterministic mock generators.
6. Add raw DDL and `ingest_raw`.
7. Add analytics SQL and `build_analytics`.
8. Add parent flow and parent-only Prefect deployment.
9. Add Metabase setup docs.
10. Run end-to-end verification and tighten documentation based on real commands.

## Main Risks

- Prefect startup ordering may need health checks or retry-tolerant commands.
- Metabase database initialization can take time before it accepts connections.
- Database role permissions need to be strict enough to prove boundaries but simple enough for the POC.
- Docker image tags and Python package versions must be verified before pinning during implementation.
- Parent deployment setup should avoid accidentally registering child flows as separate deployments.
