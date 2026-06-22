"""Bootstrap a local Metabase instance and register the warehouse connection."""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class BootstrapSettings(BaseSettings):
    """Configuration for Metabase first-run setup and warehouse registration."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    metabase_internal_url: str = Field(
        "http://metabase:3000", validation_alias="METABASE_INTERNAL_URL"
    )
    metabase_admin_email: str = Field(validation_alias="METABASE_ADMIN_EMAIL")
    metabase_admin_password: SecretStr = Field(
        validation_alias="METABASE_ADMIN_PASSWORD"
    )
    metabase_admin_first_name: str = Field(
        validation_alias="METABASE_ADMIN_FIRST_NAME"
    )
    metabase_admin_last_name: str = Field(validation_alias="METABASE_ADMIN_LAST_NAME")
    metabase_site_name: str = Field(
        "SOC Metrics Pipeline", validation_alias="METABASE_SITE_NAME"
    )
    postgres_host: str = Field("postgres", validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(5432, validation_alias="POSTGRES_PORT")
    warehouse_db_name: str = Field("warehouse", validation_alias="WAREHOUSE_DB_NAME")
    metabase_warehouse_user: str = Field(
        validation_alias="METABASE_WAREHOUSE_USER"
    )
    metabase_warehouse_password: SecretStr = Field(
        validation_alias="METABASE_WAREHOUSE_PASSWORD"
    )
    readiness_timeout_seconds: int = Field(
        300, validation_alias="METABASE_BOOTSTRAP_TIMEOUT_SECONDS"
    )


@dataclass(frozen=True)
class ExistingDatabaseMatch:
    """A single existing Metabase database record that should be updated."""

    database_id: int
    name: str


class MetabaseClient:
    """Small JSON client for the Metabase HTTP API."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.session_id: str | None = None

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        expected_statuses: tuple[int, ...] = (200,),
        include_session: bool = False,
    ) -> Any:
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if include_session and self.session_id:
            headers["X-Metabase-Session"] = self.session_id

        req = request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with request.urlopen(req, timeout=30) as response:
                body = response.read().decode("utf-8")
                if response.status not in expected_statuses:
                    raise RuntimeError(
                        f"{method} {path} returned {response.status}: {body}"
                    )
                if not body:
                    return None
                return json.loads(body)
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"{method} {path} returned {exc.code}: {detail}"
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(f"{method} {path} failed: {exc.reason}") from exc


def wait_for_metabase(client: MetabaseClient, timeout_seconds: int) -> dict[str, Any]:
    """Poll session properties until Metabase is ready to answer API requests."""

    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            response = client.request("GET", "/api/session/properties")
            if isinstance(response, dict):
                print("Metabase API is ready.")
                return response
        except RuntimeError as exc:
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"Timed out waiting for Metabase readiness after "
                    f"{timeout_seconds}s."
                ) from exc
            print(f"Waiting for Metabase API: {exc}")
            time.sleep(5)


def create_initial_admin(
    client: MetabaseClient, settings: BootstrapSettings, properties: dict[str, Any]
) -> None:
    """Create the initial Metabase admin user when the instance is uninitialized."""

    setup_token = properties.get("setup-token")
    if not setup_token:
        raise RuntimeError(
            "Metabase is uninitialized but did not return a setup token."
        )

    print("Metabase is uninitialized. Creating the initial admin user.")
    client.request(
        "POST",
        "/api/setup",
        {
            "token": setup_token,
            "user": {
                "email": settings.metabase_admin_email,
                "password": settings.metabase_admin_password.get_secret_value(),
                "first_name": settings.metabase_admin_first_name,
                "last_name": settings.metabase_admin_last_name,
            },
            "prefs": {"site_name": settings.metabase_site_name},
            "database": None,
        },
    )


def login(
    client: MetabaseClient,
    settings: BootstrapSettings,
    *,
    fail_on_mismatch: bool,
) -> None:
    """Authenticate as the configured admin user."""

    try:
        response = client.request(
            "POST",
            "/api/session",
            {
                "username": settings.metabase_admin_email,
                "password": settings.metabase_admin_password.get_secret_value(),
            },
        )
    except RuntimeError as exc:
        if fail_on_mismatch:
            raise RuntimeError(
                "Metabase is already initialized, but login with the configured "
                "METABASE_ADMIN_EMAIL and METABASE_ADMIN_PASSWORD failed. Refusing "
                "to mutate unknown Metabase state."
            ) from exc
        raise

    session_id = response.get("id") if isinstance(response, dict) else None
    if not isinstance(session_id, str) or not session_id:
        raise RuntimeError("Metabase login succeeded but no session ID was returned.")
    client.session_id = session_id
    print(f"Logged in to Metabase as {settings.metabase_admin_email}.")


def connection_payload(settings: BootstrapSettings) -> dict[str, Any]:
    """Build the warehouse database definition expected by Metabase."""

    return {
        "engine": "postgres",
        "name": "SOC Metrics Warehouse",
        "details": {
            "host": settings.postgres_host,
            "port": settings.postgres_port,
            "dbname": settings.warehouse_db_name,
            "user": settings.metabase_warehouse_user,
            "password": settings.metabase_warehouse_password.get_secret_value(),
            "ssl": False,
            "schema-filters-type": "inclusion",
            "schema-filters-patterns": "analytics",
        },
        "is_full_sync": True,
        "is_on_demand": False,
        "auto_run_queries": True,
    }


def matching_database(
    databases: list[dict[str, Any]], target: dict[str, Any]
) -> ExistingDatabaseMatch | None:
    """Find the existing warehouse connection that should be updated."""

    matches: dict[int, ExistingDatabaseMatch] = {}
    for database in databases:
        database_id = database.get("id")
        if not isinstance(database_id, int):
            continue

        details = database.get("details") or {}
        if not isinstance(details, dict):
            details = {}

        same_name = database.get("name") == target["name"]
        same_target = (
            database.get("engine") == target["engine"]
            and details.get("host") == target["details"]["host"]
            and str(details.get("port")) == str(target["details"]["port"])
            and details.get("dbname") == target["details"]["dbname"]
            and details.get("user") == target["details"]["user"]
        )
        if same_name or same_target:
            matches[database_id] = ExistingDatabaseMatch(
                database_id=database_id,
                name=str(database.get("name") or database_id),
            )

    if len(matches) > 1:
        raise RuntimeError(
            "Found multiple existing Metabase database entries that match the "
            "warehouse connection. Clean up duplicates in Metabase before rerunning "
            "the bootstrap."
        )
    return next(iter(matches.values()), None)


def upsert_database(client: MetabaseClient, settings: BootstrapSettings) -> int:
    """Create or update the warehouse database connection."""

    response = client.request("GET", "/api/database", include_session=True)
    databases = response.get("data", []) if isinstance(response, dict) else []
    if not isinstance(databases, list):
        raise RuntimeError("Metabase returned an unexpected database list payload.")

    payload = connection_payload(settings)
    existing = matching_database(databases, payload)
    if existing is None:
        print("Creating the Metabase warehouse database connection.")
        created = client.request(
            "POST",
            "/api/database",
            payload,
            include_session=True,
            expected_statuses=(200, 202),
        )
        database_id = created.get("id") if isinstance(created, dict) else None
        if not isinstance(database_id, int):
            raise RuntimeError("Metabase did not return a database ID after creation.")
        return database_id

    print(
        f"Updating the existing Metabase warehouse connection "
        f"'{existing.name}' (id={existing.database_id})."
    )
    updated = client.request(
        "PUT",
        f"/api/database/{existing.database_id}",
        payload,
        include_session=True,
        expected_statuses=(200, 202),
    )
    database_id = updated.get("id") if isinstance(updated, dict) else None
    if not isinstance(database_id, int):
        return existing.database_id
    return database_id


def main() -> int:
    """Run the full Metabase bootstrap flow."""

    settings = BootstrapSettings()
    client = MetabaseClient(settings.metabase_internal_url)

    properties = wait_for_metabase(client, settings.readiness_timeout_seconds)
    has_user_setup = bool(properties.get("has-user-setup"))

    if not has_user_setup:
        create_initial_admin(client, settings, properties)
        time.sleep(2)

    login(client, settings, fail_on_mismatch=has_user_setup)
    database_id = upsert_database(client, settings)
    print(f"Metabase warehouse connection is ready (id={database_id}).")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
