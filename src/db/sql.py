"""Load and execute SQL files in deterministic filename order."""

from __future__ import annotations

from pathlib import Path

import psycopg


def list_sql_files(directory: Path) -> list[Path]:
    """Return ``.sql`` files in *directory* sorted by filename (deterministic order)."""
    return sorted(p for p in Path(directory).glob("*.sql") if p.is_file())


def execute_sql_file(conn: psycopg.Connection, path: Path) -> None:
    """Execute every statement in a single ``.sql`` file.

    Transaction management is left to the caller. psycopg 3 runs multiple
    ``;``-separated statements in one ``execute`` when no parameters are passed,
    which is the case for our DDL and transform files.
    """
    sql = Path(path).read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)


def run_sql_directory(conn: psycopg.Connection, directory: Path) -> list[Path]:
    """Execute all ``.sql`` files in *directory*, in order, as one transaction.

    Commits on success; rolls back and re-raises on any failure so an analytics
    rebuild is atomic. Returns the executed file paths for logging.
    """
    files = list_sql_files(directory)
    try:
        for path in files:
            execute_sql_file(conn, path)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return files
