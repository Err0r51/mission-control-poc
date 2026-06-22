CREATE TABLE IF NOT EXISTS raw.dfir_iris_cases (
    source_case_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    severity text NOT NULL,
    status text NOT NULL,
    occurred_at timestamptz,
    opened_at timestamptz NOT NULL,
    closed_at timestamptz,
    case_outcome text,
    assigned_team text NOT NULL,
    assigned_analyst text,
    closed_by text,
    auto_closed_by_run_id text,
    extracted_at timestamptz NOT NULL,
    payload jsonb NOT NULL
);

ALTER TABLE raw.dfir_iris_cases
    ADD COLUMN IF NOT EXISTS occurred_at timestamptz,
    ADD COLUMN IF NOT EXISTS case_outcome text,
    ADD COLUMN IF NOT EXISTS assigned_analyst text,
    ADD COLUMN IF NOT EXISTS closed_by text,
    ADD COLUMN IF NOT EXISTS auto_closed_by_run_id text;

CREATE TABLE IF NOT EXISTS raw.siem_alerts (
    source_alert_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    source_product text NOT NULL,
    system_id text,
    detection_name text NOT NULL,
    severity text NOT NULL,
    event_at timestamptz NOT NULL,
    triage_status text NOT NULL,
    resolution text NOT NULL,
    linked_case_id text,
    reviewed_at timestamptz,
    reviewed_by_analyst text,
    extracted_at timestamptz NOT NULL,
    payload jsonb NOT NULL
);

ALTER TABLE raw.siem_alerts
    ADD COLUMN IF NOT EXISTS system_id text,
    ADD COLUMN IF NOT EXISTS reviewed_at timestamptz,
    ADD COLUMN IF NOT EXISTS reviewed_by_analyst text;

CREATE TABLE IF NOT EXISTS raw.shuffle_runs (
    source_run_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workflow_name text NOT NULL,
    started_at timestamptz NOT NULL,
    ended_at timestamptz NOT NULL,
    result_status text NOT NULL,
    related_alert_id text,
    related_case_id text,
    extracted_at timestamptz NOT NULL,
    payload jsonb NOT NULL
);

ALTER TABLE raw.shuffle_runs
    ADD COLUMN IF NOT EXISTS related_case_id text;

CREATE TABLE IF NOT EXISTS raw.customer_systems (
    system_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    source_product text NOT NULL,
    hostname text NOT NULL,
    monitored_from timestamptz NOT NULL,
    monitored_to timestamptz,
    extracted_at timestamptz NOT NULL,
    payload jsonb NOT NULL
);
