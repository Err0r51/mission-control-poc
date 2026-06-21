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

## Verification

```bash
uv sync
uv run ruff check .
uv run python -m compileall flows src
```

Docker Compose wiring for PostgreSQL, Prefect, the worker image, and Metabase is now part
of the repository. SQL transforms and deployment registration are still added in later
implementation phases.
