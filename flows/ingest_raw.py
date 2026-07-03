"""Prefect flow for deterministic raw ingestion into ``warehouse.raw``."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from prefect import flow, get_run_logger, task
from psycopg.types.json import Jsonb

from db.connection import warehouse_connection
from db.sql import execute_sql_file
from mock_sources.customer_systems import (
    CustomerSystem,
)
from mock_sources.customer_systems import (
    generate_customer_systems as build_customer_systems,
)
from mock_sources.dfir_iris import DfirIrisCase, generate_dfir_iris_cases
from mock_sources.shuffle import (
    ShuffleRun,
)
from mock_sources.shuffle import (
    generate_shuffle_runs as build_shuffle_runs,
)
from mock_sources.siem import (
    SecurityAlert,
)
from mock_sources.siem import (
    generate_security_alerts as build_security_alerts,
)

RAW_SQL_PATH = (
    Path(__file__).resolve().parents[1] / "sql" / "raw" / "001_create_raw_tables.sql"
)

INSERT_DFIR_CASES_SQL = """
INSERT INTO raw.dfir_iris_cases (
    source_case_id,
    tenant_id,
    source_event_time,
    extracted_at,
    payload
) VALUES (%s, %s, %s, %s, %s)
"""

INSERT_SIEM_ALERTS_SQL = """
INSERT INTO raw.siem_alerts (
    source_alert_id,
    tenant_id,
    source_product,
    source_event_time,
    extracted_at,
    payload
) VALUES (%s, %s, %s, %s, %s, %s)
"""

INSERT_SHUFFLE_RUNS_SQL = """
INSERT INTO raw.shuffle_runs (
    source_run_id,
    tenant_id,
    source_event_time,
    extracted_at,
    payload
) VALUES (%s, %s, %s, %s, %s)
"""

INSERT_CUSTOMER_SYSTEMS_SQL = """
INSERT INTO raw.customer_systems (
    system_id,
    tenant_id,
    source_product,
    source_event_time,
    extracted_at,
    payload
) VALUES (%s, %s, %s, %s, %s, %s)
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
        case.source_event_time,
        extracted_at,
        Jsonb(case.payload),
    )


def _security_alert_row(
    alert: SecurityAlert, extracted_at: datetime
) -> tuple[object, ...]:
    return (
        alert.source_alert_id,
        alert.tenant_id,
        alert.source_product,
        alert.source_event_time,
        extracted_at,
        Jsonb(alert.payload),
    )


def _shuffle_run_row(run: ShuffleRun, extracted_at: datetime) -> tuple[object, ...]:
    return (
        run.source_run_id,
        run.tenant_id,
        run.source_event_time,
        extracted_at,
        Jsonb(run.payload),
    )


def _customer_system_row(
    customer_system: CustomerSystem, extracted_at: datetime
) -> tuple[object, ...]:
    return (
        customer_system.system_id,
        customer_system.tenant_id,
        customer_system.source_product,
        customer_system.source_event_time,
        extracted_at,
        Jsonb(customer_system.payload),
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
def generate_customer_system_records(count: int) -> list[CustomerSystem]:
    """Generate deterministic monitored-system inventory."""
    return build_customer_systems(count=_validate_count("customer_system_count", count))


@task
def generate_dfir_cases(count: int, shuffle_run_count: int) -> list[DfirIrisCase]:
    """Generate deterministic DFIR-IRIS-like cases."""
    return generate_dfir_iris_cases(
        count=_validate_count("dfir_case_count", count),
        shuffle_run_count=_validate_count("shuffle_run_count", shuffle_run_count),
    )


@task
def generate_security_alert_records(
    count: int, case_count: int, customer_system_count: int
) -> list[SecurityAlert]:
    """Generate deterministic SIEM-like alerts."""
    return build_security_alerts(
        count=_validate_count("security_alert_count", count),
        case_count=_validate_count("dfir_case_count", case_count),
        customer_system_count=_validate_count(
            "customer_system_count", customer_system_count
        ),
    )


@task
def generate_shuffle_run_records(
    count: int, alert_count: int, case_count: int
) -> list[ShuffleRun]:
    """Generate deterministic Shuffle-like runs."""
    return build_shuffle_runs(
        count=_validate_count("shuffle_run_count", count),
        alert_count=_validate_count("security_alert_count", alert_count),
        case_count=_validate_count("dfir_case_count", case_count),
    )


@task
def load_raw_tables(
    dfir_cases: list[DfirIrisCase],
    security_alerts: list[SecurityAlert],
    shuffle_runs: list[ShuffleRun],
    customer_systems: list[CustomerSystem],
    extracted_at: datetime,
) -> dict[str, int]:
    """Load the generated data into the freshly (re)created raw tables.

    ``ensure_raw_schema`` drop-and-recreates the raw tables on every run, so they
    are already empty here; this task only inserts.
    """
    with warehouse_connection() as conn:
        try:
            with conn.cursor() as cur:
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
                cur.executemany(
                    INSERT_CUSTOMER_SYSTEMS_SQL,
                    [
                        _customer_system_row(customer_system, extracted_at)
                        for customer_system in customer_systems
                    ],
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return {
        "dfir_iris_cases": len(dfir_cases),
        "siem_alerts": len(security_alerts),
        "shuffle_runs": len(shuffle_runs),
        "customer_systems": len(customer_systems),
    }


@task
def log_ingestion_summary(
    inserted_counts: dict[str, int], extracted_at: datetime
) -> None:
    """Emit a stable ingestion summary to the Prefect run logs."""
    logger = get_run_logger()
    logger.info(
        (
            "Ingested raw tables at %s: dfir_iris_cases=%d siem_alerts=%d "
            "shuffle_runs=%d customer_systems=%d"
        ),
        extracted_at.isoformat(),
        inserted_counts["dfir_iris_cases"],
        inserted_counts["siem_alerts"],
        inserted_counts["shuffle_runs"],
        inserted_counts["customer_systems"],
    )


@flow(name="ingest_raw")
def ingest_raw(
    dfir_case_count: int = 60,
    security_alert_count: int = 240,
    shuffle_run_count: int = 120,
    customer_system_count: int = 45,
) -> None:
    """Generate deterministic mock data and reload ``warehouse.raw`` atomically."""
    ensure_raw_schema()
    extracted_at = datetime.now(UTC)
    customer_systems = generate_customer_system_records(customer_system_count)
    dfir_cases = generate_dfir_cases(dfir_case_count, shuffle_run_count)
    security_alerts = generate_security_alert_records(
        security_alert_count,
        _validate_count("dfir_case_count", dfir_case_count),
        _validate_count("customer_system_count", customer_system_count),
    )
    shuffle_runs = generate_shuffle_run_records(
        shuffle_run_count,
        _validate_count("security_alert_count", security_alert_count),
        _validate_count("dfir_case_count", dfir_case_count),
    )
    inserted_counts = load_raw_tables(
        dfir_cases,
        security_alerts,
        shuffle_runs,
        customer_systems,
        extracted_at,
    )
    log_ingestion_summary(inserted_counts, extracted_at)
