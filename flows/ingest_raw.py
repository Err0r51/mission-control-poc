"""Prefect flow for deterministic raw ingestion into ``warehouse.raw``."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from prefect import flow, get_run_logger, task
from psycopg.types.json import Jsonb

from db.connection import warehouse_connection
from db.sql import execute_sql_file
from mock_sources.dfir_iris import DfirIrisCase, generate_dfir_iris_cases
from mock_sources.shuffle import ShuffleRun, generate_shuffle_runs as build_shuffle_runs
from mock_sources.siem import (
    SecurityAlert,
    generate_security_alerts as build_security_alerts,
)

RAW_SQL_PATH = Path(__file__).resolve().parents[1] / "sql" / "raw" / "001_create_raw_tables.sql"

TRUNCATE_RAW_TABLES_SQL = """
TRUNCATE TABLE
    raw.shuffle_runs,
    raw.siem_alerts,
    raw.dfir_iris_cases
"""

INSERT_DFIR_CASES_SQL = """
INSERT INTO raw.dfir_iris_cases (
    source_case_id,
    tenant_id,
    severity,
    status,
    opened_at,
    closed_at,
    assigned_team,
    extracted_at,
    payload
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

INSERT_SIEM_ALERTS_SQL = """
INSERT INTO raw.siem_alerts (
    source_alert_id,
    tenant_id,
    source_product,
    detection_name,
    severity,
    event_at,
    triage_status,
    resolution,
    linked_case_id,
    extracted_at,
    payload
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

INSERT_SHUFFLE_RUNS_SQL = """
INSERT INTO raw.shuffle_runs (
    source_run_id,
    tenant_id,
    workflow_name,
    started_at,
    ended_at,
    result_status,
    related_alert_id,
    extracted_at,
    payload
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def _validate_count(name: str, count: int) -> int:
    """Reject negative row counts so Prefect runs fail explicitly."""
    if count < 0:
        raise ValueError(f"{name} must be >= 0, got {count}")
    return count


def _dfir_case_row(case: DfirIrisCase, extracted_at: datetime) -> tuple[object, ...]:
    return (
        case.source_case_id,
        case.tenant_id,
        case.severity,
        case.status,
        case.opened_at,
        case.closed_at,
        case.assigned_team,
        extracted_at,
        Jsonb(case.payload),
    )


def _security_alert_row(alert: SecurityAlert, extracted_at: datetime) -> tuple[object, ...]:
    return (
        alert.source_alert_id,
        alert.tenant_id,
        alert.source_product,
        alert.detection_name,
        alert.severity,
        alert.event_at,
        alert.triage_status,
        alert.resolution,
        alert.linked_case_id,
        extracted_at,
        Jsonb(alert.payload),
    )


def _shuffle_run_row(run: ShuffleRun, extracted_at: datetime) -> tuple[object, ...]:
    return (
        run.source_run_id,
        run.tenant_id,
        run.workflow_name,
        run.started_at,
        run.ended_at,
        run.result_status,
        run.related_alert_id,
        extracted_at,
        Jsonb(run.payload),
    )


@task
def ensure_raw_schema() -> None:
    """Create the raw schema and source-shaped tables if they do not exist."""
    with warehouse_connection() as conn:
        try:
            execute_sql_file(conn, RAW_SQL_PATH)
            conn.commit()
        except Exception:
            conn.rollback()
            raise


@task
def generate_dfir_cases(count: int) -> list[DfirIrisCase]:
    """Generate deterministic DFIR-IRIS-like cases."""
    return generate_dfir_iris_cases(count=_validate_count("dfir_case_count", count))


@task
def generate_security_alerts(count: int) -> list[SecurityAlert]:
    """Generate deterministic SIEM-like alerts."""
    return build_security_alerts(count=_validate_count("security_alert_count", count))


@task
def generate_shuffle_runs(count: int) -> list[ShuffleRun]:
    """Generate deterministic Shuffle-like runs."""
    return build_shuffle_runs(count=_validate_count("shuffle_run_count", count))


@task
def load_raw_tables(
    dfir_cases: list[DfirIrisCase],
    security_alerts: list[SecurityAlert],
    shuffle_runs: list[ShuffleRun],
    extracted_at: datetime,
) -> dict[str, int]:
    """Atomically replace the current raw tables with the generated data."""
    with warehouse_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(TRUNCATE_RAW_TABLES_SQL)
                cur.executemany(
                    INSERT_DFIR_CASES_SQL,
                    [_dfir_case_row(case, extracted_at) for case in dfir_cases],
                )
                cur.executemany(
                    INSERT_SIEM_ALERTS_SQL,
                    [
                        _security_alert_row(alert, extracted_at)
                        for alert in security_alerts
                    ],
                )
                cur.executemany(
                    INSERT_SHUFFLE_RUNS_SQL,
                    [_shuffle_run_row(run, extracted_at) for run in shuffle_runs],
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return {
        "dfir_iris_cases": len(dfir_cases),
        "siem_alerts": len(security_alerts),
        "shuffle_runs": len(shuffle_runs),
    }


@task
def log_ingestion_summary(inserted_counts: dict[str, int], extracted_at: datetime) -> None:
    """Emit a stable ingestion summary to the Prefect run logs."""
    logger = get_run_logger()
    logger.info(
        "Ingested raw tables at %s: dfir_iris_cases=%d siem_alerts=%d shuffle_runs=%d",
        extracted_at.isoformat(),
        inserted_counts["dfir_iris_cases"],
        inserted_counts["siem_alerts"],
        inserted_counts["shuffle_runs"],
    )


@flow(name="ingest_raw")
def ingest_raw(
    dfir_case_count: int = 60,
    security_alert_count: int = 240,
    shuffle_run_count: int = 120,
) -> None:
    """Generate deterministic mock data and reload ``warehouse.raw`` atomically."""
    ensure_raw_schema()
    extracted_at = datetime.now(timezone.utc)
    dfir_cases = generate_dfir_cases(dfir_case_count)
    security_alerts = generate_security_alerts(security_alert_count)
    shuffle_runs = generate_shuffle_runs(shuffle_run_count)
    inserted_counts = load_raw_tables(
        dfir_cases,
        security_alerts,
        shuffle_runs,
        extracted_at,
    )
    log_ingestion_summary(inserted_counts, extracted_at)
