"""Prefect flow for rebuilding ``warehouse.analytics`` from ``warehouse.raw``."""

from __future__ import annotations

from pathlib import Path

from prefect import flow, get_run_logger, task

from db.connection import warehouse_connection
from db.sql import run_sql_directory

ANALYTICS_SQL_DIR = Path(__file__).resolve().parents[1] / "sql" / "analytics"


@task
def execute_analytics_sql() -> list[Path]:
    """Run the analytics rebuild SQL directory as one database transaction."""
    with warehouse_connection() as conn:
        return run_sql_directory(conn, ANALYTICS_SQL_DIR)


@task
def log_analytics_summary(executed_files: list[Path]) -> None:
    """Log the deterministic analytics rebuild steps."""
    logger = get_run_logger()
    logger.info(
        "Executed analytics SQL files: %s",
        ", ".join(path.name for path in executed_files),
    )


@flow(name="build_analytics")
def build_analytics() -> None:
    """Rebuild all BI-facing analytics tables from the raw warehouse schema."""
    executed_files = execute_analytics_sql()
    log_analytics_summary(executed_files)
