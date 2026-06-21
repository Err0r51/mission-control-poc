# Local Development

Step 7 keeps deployment registration and operations inside containers so the checked-in
`.env` values continue to work unchanged.

## Startup order

1. Start the shared infrastructure:

   ```bash
   podman compose up -d postgres prefect-server metabase
   ```

2. Register the work pool and the single parent deployment:

   ```bash
   podman compose up prefect-deploy
   ```

3. Start the Prefect process worker:

   ```bash
   podman compose up -d prefect-worker
   ```

The `prefect-deploy` service is a one-shot registration container. Re-run it after changes
to `prefect.yaml` or the parent deployment definition.

## Inspect the registered objects

Inspect the work pool from inside `prefect-server`:

```bash
podman compose exec prefect-server prefect work-pool inspect soc-metrics-process
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

## Trigger the pipeline

Trigger the manual parent deployment and stream logs until completion:

```bash
podman compose exec prefect-server prefect deployment run soc_metrics_pipeline/manual --watch
```

The parent run should execute `ingest_raw` first and `build_analytics` second.
