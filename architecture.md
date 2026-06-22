# Architecture — SOC Metrics Pipeline

## Vision

This project is a local proof of concept for an internal SOC metrics pipeline.

It surfaces operational metrics from mocked DFIR-IRIS, SIEM, and Shuffle-like sources into Metabase dashboards.

The purpose is to validate:

- the local orchestration model
- the warehouse boundary
- the raw-to-analytics transformation path
- the Metabase serving path

Real source integrations are out of scope.

## Stack

- Orchestration: Prefect OSS, self-hosted
- Worker: Prefect process worker running inside Docker
- Transformation: plain SQL executed by Prefect
- Database: PostgreSQL
- BI: Metabase
- Deployment: Docker Compose
- Python dependency management: uv
- Runtime language: Python
- Transformation language: SQL

## Service layout

The local stack contains:

- `postgres`
- `prefect-server`
- `prefect-worker`
- `metabase`

Redis is not used.

The Prefect worker is a process worker running inside a Docker container. It does not launch a separate container per flow run.

## PostgreSQL layout

A single PostgreSQL instance is the only stateful infrastructure service.

It hosts three logical databases:

- `prefect`
- `metabase`
- `warehouse`

These are separate logical databases inside the same PostgreSQL instance, not separate database servers.

## Logical databases

### `prefect`

Stores Prefect server metadata:

- deployments
- schedules
- flow run state
- task run state
- retry state
- logs
- orchestration metadata

It does not contain SOC metrics data.

### `metabase`

Stores Metabase application state:

- users
- dashboards
- saved questions
- collections
- permissions
- Metabase internal metadata

It does not contain SOC metrics data.

### `warehouse`

Stores SOC metrics pipeline data.

It contains two schemas:

- `raw`
- `analytics`

No other warehouse schemas are part of the current architecture.

## Warehouse model

The warehouse uses a two-layer model.

### `raw`

The `raw` schema stores mocked source-shaped extracts and monitored-system inventory.

Raw should be minimal and source-shaped. It should not model the final SOC domain too early.

Typical raw records may include:

- source system
- tenant identifier
- source record identifier, where useful
- source timestamp, where useful
- explicit KPI-driving fields where the prototype contract needs them
- extraction timestamp
- JSON payload or simple source-shaped columns

The raw shape may evolve because the real source payloads are not yet known.

### `analytics`

The `analytics` schema stores BI-facing transformed outputs for the current KPI prototype.

Analytics objects are rebuilt from `raw`.

Metabase reads from `analytics`.

Analytics now contains lower-grain, BI-safe fact tables plus KPI rollups:

- incident facts
- alert facts
- automation-run facts
- monitored-system facts
- monthly KPI rollups
- alert-volume rollups by source
- alert-review rollups by shift

This is still a prototype contract. The goal is to make KPI-relevant detail queryable from
`analytics` so Metabase does not need `raw`, without claiming this is the final production
warehouse model.

## Data flow

The pipeline follows this path:

- mocked DFIR-IRIS-like data to `warehouse.raw`
- mocked SIEM-like data to `warehouse.raw`
- mocked Shuffle-like data to `warehouse.raw`
- mocked monitored-system inventory to `warehouse.raw`
- SQL transforms from `warehouse.raw` to `warehouse.analytics`
- Metabase dashboards from `warehouse.analytics`

## Prefect model

Prefect is the orchestration and observability plane.

The Prefect server provides:

- UI
- API
- scheduling
- run state
- task state
- retries
- logs
- operational visibility

The Prefect worker executes the pipeline code.

The server does not execute pipeline code.

## Prefect runtime contract

The local Prefect runtime uses one process work pool.

Required runtime shape:

- work pool type: `process`
- worker service: `prefect-worker`
- worker command: `prefect worker start --pool soc-metrics-process --type process`
- deployed flow: `soc_metrics_pipeline`
- child flows: `ingest_raw` and `build_analytics` are imported and called by the parent flow, not deployed separately
- flow code source: baked into the project-specific worker image
- SQL file source: baked into the project-specific worker image
- Prefect API URL: provided to the worker through `PREFECT_API_URL`
- schedule policy: manual by default until a schedule is explicitly needed

Startup order:

1. `postgres` becomes healthy.
2. `prefect-server` starts and connects to the `prefect` database.
3. `prefect-worker` starts after the Prefect API is reachable.
4. the parent deployment is registered against the process work pool.
5. flow runs are scheduled by the server and executed by the worker process.

The Prefect server must use only the `prefect` logical database.

The Prefect worker must connect to `warehouse` for pipeline reads and writes.

The Prefect worker must not connect to `metabase` for pipeline data.

The deployment registration mechanism may be a Compose one-shot service or an explicit documented command, but it must register only `soc_metrics_pipeline`.

## Flow structure

The code is organized as two logical flows:

- `ingest_raw`
- `build_analytics`

A parent flow coordinates both:

- `soc_metrics_pipeline`

Execution order:

1. `ingest_raw`
2. `build_analytics`

Only the parent flow is deployed.

This keeps runtime orchestration simple while preserving clean code boundaries between ingestion and transformation.

## Ingest flow

The `ingest_raw` flow is responsible for:

- generating mocked DFIR-IRIS-like records
- generating mocked SIEM-like records
- generating mocked Shuffle-like records
- generating mocked monitored-system inventory
- loading those records into `warehouse.raw`
- logging record counts through Prefect

It does not build BI-facing outputs.

## Analytics flow

The `build_analytics` flow is responsible for:

- executing SQL transform files
- rebuilding `warehouse.analytics` from `warehouse.raw`
- logging executed SQL files through Prefect

It does not generate or pull source data.

## Worker image

The Prefect worker uses a project-specific Docker image.

The image contains:

- Prefect runtime
- project Python code
- SQL files
- Python dependencies
- database client libraries

Dependencies are managed with uv.

The worker image must use pinned base images and committed dependency lock files.

## Transformation model

Transformations are plain SQL files executed by a Prefect task.

The transformation path is:

`warehouse.raw` to `warehouse.analytics`

Transformations should remain simple:

- read from `raw`
- write or replace facts and rollups in `analytics`
- keep analytics rebuildable
- keep `raw` private to pipeline operators
- avoid premature final production modeling

dbt is not used.

## Metabase model

Metabase is the presentation layer.

Metabase uses the `metabase` database for application state.

Metabase connects to `warehouse` as a BI client.

Metabase should read from `warehouse.analytics`.

Metabase should not read from `warehouse.raw` except for explicit debugging.

Exploratory calculations may happen in Metabase. Reused or canonical metric definitions should be promoted into SQL in the warehouse.

## Responsibility boundaries

Prefect owns:

- scheduling
- retries
- flow state
- task state
- logs
- operational observability

The warehouse owns:

- mocked raw source data
- analytics outputs
- SQL-based metric transformations

Metabase owns:

- dashboards
- saved questions
- chart configuration
- visualization state
- application users and permissions

## Data model principles

- Keep the model minimal.
- Do not finalize the production fact and dimension model during the proof of concept.
- Use `raw` for mocked source-shaped data.
- Use `analytics` for BI-facing outputs.
- Make analytics rebuildable from raw.
- Carry tenant information through the model.
- Use UTC timestamps.
- Use real timestamp types instead of string timestamps.
- Use medians or percentiles for time-based SOC metrics where applicable.
### Relevant KPIs
  - `true positive incidents`
  - `false positives`
  - `false positive rate`
  - `true positive rate`
  - `incident escalation rate`
  - `MTTD`
  - `MTTR`
  - `customer systems under monitoring`
  - `alerts reviewed per analyst per shift`
  - `automatically closed incidents`
  - `total alert volume`
  - `alert volume by source`

## Security and configuration principles

- Do not store secrets in code.
- Use `.env` for local secrets and runtime configuration.
- Keep `.env` out of version control.
- Provide `.env.example`.
- Use least-privilege roles where practical.
- Metabase should use a read-only warehouse connection where practical.

## Out of scope

The current architecture does not include:

- real DFIR-IRIS integration
- real SIEM integration
- real Shuffle integration
- Redis
- dbt
- staging schema
- ETL metadata schema
- Prefect Docker worker
- multiple deployed pipelines
- event-triggered orchestration between deployments
- cloud deployment
- customer-facing dashboards
- multi-tenant RBAC
- SSO
- compliance control implementation
- production backup or disaster recovery automation
