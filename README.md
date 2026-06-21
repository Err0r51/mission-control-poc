# SOC Metrics Pipeline

This repository scaffolds a local proof of concept for an SOC metrics pipeline that will
eventually ingest deterministic mocked DFIR-IRIS-like, SIEM-like, and Shuffle-like data,
transform it in PostgreSQL, and serve BI-facing outputs to Metabase.

## Prerequisites

- Python 3.12
- `uv`

## Setup

```bash
uv sync
```

The repository uses `src/` as a Python source root. Runtime imports stay `db` and
`mock_sources`; there is no `src.*` package namespace.

## Bootstrap Caveat

The Postgres bootstrap scripts under `docker/postgres/init/` run only when the
`postgres-data` volume is initialized for the first time. If you change logical
database roles, role passwords, or connection wiring, existing local volumes do
not automatically pick that up.

For changes in that category, either ship an explicit migration path for an
already-initialized cluster or reinitialize the local database with:

```bash
podman compose down -v
podman compose up -d
```

## Verification

```bash
uv sync
uv run ruff check .
uv run python -m compileall flows src
```

Docker Compose wiring for PostgreSQL, Prefect, the worker image, and Metabase is now part
of the repository.

Step 7 adds a real parent flow, `soc_metrics_pipeline`, and a single manual Prefect
deployment, `soc_metrics_pipeline/manual`. Deployment registration is containerized via
the Compose one-shot service `prefect-deploy` so the repo can keep using the in-network
`PREFECT_API_URL` and `POSTGRES_HOST` values from `.env`.

For the exact local operator workflow, including registration, inspection, and triggering
the deployment from inside the Prefect container, see [docs/local-development.md](/Users/frederikjunge/Developer/mission-control-poc/docs/local-development.md).
