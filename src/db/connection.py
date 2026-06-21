"""Environment-based PostgreSQL connection helpers for the warehouse database."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WarehouseSettings(BaseSettings):
    """Warehouse connection settings, read from the environment or .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    host: str = Field("localhost", validation_alias="POSTGRES_HOST")
    port: int = Field(5432, validation_alias="POSTGRES_PORT")
    dbname: str = Field("warehouse", validation_alias="WAREHOUSE_DB_NAME")
    user: str = Field(validation_alias="WAREHOUSE_DB_USER")
    password: str = Field(validation_alias="WAREHOUSE_DB_PASSWORD")

    def conninfo(self) -> str:
        """Build a libpq conninfo string for the warehouse database."""
        return psycopg.conninfo.make_conninfo(
            host=self.host,
            port=self.port,
            dbname=self.dbname,
            user=self.user,
            password=self.password,
        )


def warehouse_settings() -> WarehouseSettings:
    """Construct warehouse settings from the current environment / .env."""
    return WarehouseSettings()


@contextmanager
def warehouse_connection() -> Iterator[psycopg.Connection]:
    """Yield a fresh warehouse connection, closed on exit.

    The caller is responsible for commit/rollback. No connection state is held
    at module level, so each call opens an independent connection.
    """
    conn = psycopg.connect(warehouse_settings().conninfo())
    try:
        yield conn
    finally:
        conn.close()
