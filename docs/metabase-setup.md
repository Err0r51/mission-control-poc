# Metabase Setup

Step 8 keeps Metabase setup containerized so first-run admin creation and the BI database
registration can be repeated without clicking through the initial UI wizard.

## Required environment

Add these values to `.env` before running the bootstrap service:

- `METABASE_ADMIN_EMAIL`
- `METABASE_ADMIN_PASSWORD`
- `METABASE_ADMIN_FIRST_NAME`
- `METABASE_ADMIN_LAST_NAME`
- `METABASE_SITE_NAME` (optional display name; `.env.example` includes a default)

The warehouse connection is always created against:

- host `postgres`
- port `5432`
- database `warehouse`
- username `metabase_reader`
- schema filter `analytics`

## Operator flow

1. Start the shared services:

   ```bash
   podman compose up -d postgres prefect-server metabase
   ```

2. Register the Prefect deployment and start the worker:

   ```bash
   podman compose up --build prefect-deploy
   podman compose up -d --build prefect-worker
   ```

3. Run the parent flow so `warehouse.analytics` objects exist:

   ```bash
   podman compose exec prefect-server prefect deployment run soc_metrics_pipeline/manual --watch
   ```

4. Bootstrap Metabase:

   ```bash
   podman compose up --build metabase-bootstrap
   ```

5. Open Metabase at `http://localhost:3000` or your overridden `METABASE_PORT`, sign in
   with the configured admin user, and create dashboards or saved questions manually.

## Rerun behavior

`metabase-bootstrap` is safe to rerun:

- If Metabase has not been initialized yet, it creates the initial admin user from `.env`.
- If Metabase is already initialized, it logs in with the configured admin credentials.
- If those credentials do not match the existing Metabase admin state, the bootstrap exits
  with a clear error instead of mutating unknown application state.
- If the warehouse database entry already exists and already points at the intended
  warehouse target, the bootstrap updates it in place instead of creating a duplicate.
- If a database named `SOC Metrics Warehouse` already exists but points somewhere else, the
  bootstrap fails clearly instead of overwriting it.
- On the first run, the bootstrap waits for Metabase admin login to become usable after
  setup instead of relying on a fixed sleep.

## What the bootstrap configures

The bootstrap script creates or updates a Metabase database named `SOC Metrics Warehouse`
with:

- engine `postgres`
- host `postgres`
- port `5432`
- database `warehouse`
- username `metabase_reader`
- schema inclusion filter restricted to `analytics`

Dashboards, saved questions, collections, and semantic-model tuning remain manual.
