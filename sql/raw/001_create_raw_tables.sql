-- Source-shaped raw landing tables.
--
-- Each table holds only thin routing columns a collector genuinely knows at
-- ingest time (the source id, the tenant it polled, the product connector where
-- applicable, the source event time, and the extraction time) plus the full
-- product-native ``payload`` as the single source of truth. All normalization
-- and cross-source correlation happens downstream in ``analytics`` (the stg_*
-- parse tables), never here. Rebuilt drop-and-recreate so the shape is
-- authoritative on every run. The ``raw`` schema itself is provisioned by the
-- database init script (with the right grants), so it is not (re)created here.

DROP TABLE IF EXISTS raw.dfir_iris_cases;
DROP TABLE IF EXISTS raw.siem_alerts;
DROP TABLE IF EXISTS raw.shuffle_runs;
DROP TABLE IF EXISTS raw.customer_systems;

CREATE TABLE raw.dfir_iris_cases (
    source_case_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    source_event_time timestamptz NOT NULL,
    extracted_at timestamptz NOT NULL,
    payload jsonb NOT NULL
);

CREATE TABLE raw.siem_alerts (
    source_alert_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    source_product text NOT NULL,
    source_event_time timestamptz NOT NULL,
    extracted_at timestamptz NOT NULL,
    payload jsonb NOT NULL
);

CREATE TABLE raw.shuffle_runs (
    source_run_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    source_event_time timestamptz NOT NULL,
    extracted_at timestamptz NOT NULL,
    payload jsonb NOT NULL
);

CREATE TABLE raw.customer_systems (
    system_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    source_product text NOT NULL,
    source_event_time timestamptz NOT NULL,
    extracted_at timestamptz NOT NULL,
    payload jsonb NOT NULL
);
