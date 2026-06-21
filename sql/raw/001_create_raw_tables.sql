CREATE TABLE IF NOT EXISTS raw.dfir_iris_cases (
    source_case_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    severity text NOT NULL,
    status text NOT NULL,
    opened_at timestamptz NOT NULL,
    closed_at timestamptz,
    assigned_team text NOT NULL,
    extracted_at timestamptz NOT NULL,
    payload jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS raw.siem_alerts (
    source_alert_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    source_product text NOT NULL,
    detection_name text NOT NULL,
    severity text NOT NULL,
    event_at timestamptz NOT NULL,
    triage_status text NOT NULL,
    resolution text NOT NULL,
    linked_case_id text,
    extracted_at timestamptz NOT NULL,
    payload jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS raw.shuffle_runs (
    source_run_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workflow_name text NOT NULL,
    started_at timestamptz NOT NULL,
    ended_at timestamptz NOT NULL,
    result_status text NOT NULL,
    related_alert_id text,
    extracted_at timestamptz NOT NULL,
    payload jsonb NOT NULL
);
