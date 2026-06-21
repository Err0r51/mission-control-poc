# AGENTS.md — SOC Metrics Pipeline

## Purpose

This repository implements a local proof of concept for an SOC metrics pipeline.

The pipeline uses mocked source data for:

- DFIR-IRIS-like cases
- SIEM-like alerts
- Shuffle-like automation runs

The goal is to validate the pipeline shape, orchestration model, warehouse boundary, and Metabase serving path. Do not finalize the production data model prematurely.

## Architecture constraints

Use:

- Docker Compose
- one PostgreSQL instance
- three logical PostgreSQL databases:
  - `prefect`
  - `metabase`
  - `warehouse`
- two warehouse schemas:
  - `raw`
  - `analytics`
- Prefect OSS, self-hosted
- one Prefect server
- one Prefect process worker running inside Docker
- Metabase for dashboards
- plain SQL for transformations
- uv for Python dependency management
- podman instead of plain docker

Do not add:

- Redis
- dbt
- a `staging` schema
- an `etl`, `metadata`, lineage, cursor, or audit schema in the warehouse
- a Prefect Docker worker that launches one container per flow run
- multiple deployed pipelines
- real DFIR-IRIS, SIEM, or Shuffle integrations
- cloud deployment files
- customer-facing dashboard features
- multi-tenant RBAC or SSO

## Database boundaries

The `prefect` database is only for Prefect server metadata.

The `metabase` database is only for Metabase application state.

The `warehouse` database is only for SOC metrics pipeline data.

Metabase must read pipeline data from `warehouse.analytics`.

Do not store pipeline data in the `prefect` or `metabase` databases.

Do not make Metabase read from `warehouse.raw` except for explicit debugging.

## Flow model

Code is organized as two logical flows:

- `ingest_raw`
- `build_analytics`

Deploy one parent flow:

- `soc_metrics_pipeline`

The parent flow calls `ingest_raw` and then `build_analytics`.

Do not deploy `ingest_raw` and `build_analytics` separately unless the architecture is changed.

## Worker and dependency rules

Use a project-specific worker image.

The worker image must:

- use a uv-based Python image
- contain the project Python code
- contain the SQL files
- install dependencies from `pyproject.toml` and `uv.lock`
- run the Prefect process worker

Do not use `python:*-slim` for the worker.

Do not use ad-hoc `pip install` commands in Dockerfiles.

Commit:

- `pyproject.toml`
- `uv.lock`

Pin Docker image versions. Do not use floating tags such as `latest`.

## Repository layout

Expected layout:

- `AGENTS.md`
- `README.md`
- `.env.example`
- `docker-compose.yml`
- `Dockerfile.worker`
- `pyproject.toml`
- `uv.lock`
- `flows/`
- `src/`
- `sql/`
- `docs/`

Expected flow files:

- `flows/ingest_raw.py`
- `flows/build_analytics.py`
- `flows/soc_metrics_pipeline.py`

Expected source directories:

- `src/mock_sources/`
- `src/db/`

Expected SQL directories:

- `sql/raw/`
- `sql/analytics/`

## Development rules

Before editing, inspect the existing repository.

Implement one step at a time.

Commit all changes after each completed implementation step.

Keep mock data deterministic unless randomness is explicitly required.

Keep the raw model source-shaped and minimal.

Keep analytics BI-facing and rebuildable from raw.

Use UTC timestamps and real timestamp types.

Carry tenant information through raw and analytics.

Keep secrets in `.env`.

Document configuration in `.env.example`.

Postgres bootstrap scripts in `docker/postgres/init/` only run on first cluster initialization.

When changing logical databases, roles, or database credentials, provide an explicit migration path for existing `postgres-data` volumes or document that a clean reset such as `podman compose down -v` is required.

Do not modify unrelated files.

Do not rewrite architecture constraints unless explicitly asked.

## Verification

Run relevant ruff checks before finishing changes.
For database changes, verify with `psql` against the relevant logical database.
