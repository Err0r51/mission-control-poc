"""Shared constants and deterministic helpers for the mock source generators.

This module holds the values every generator needs (tenants, severities, the
time anchor, source cardinalities) plus pure, index-based helpers. It imports
nothing from the generator modules, so there is no import cycle -- the source
cardinalities live here precisely so the generators can reference each other's
sizes (e.g. an alert anchoring its host to a system) without importing one
another.

Determinism rule: derive each independent dimension from a different "digit" of
the record index using integer division (mixed-radix), never all from ``i % n``.
Keying several dimensions off the same residue locks them together and makes
multi-dimensional KPI breakdowns degenerate (e.g. constant true/false-positive
rate per product). No randomness and no wall-clock are used anywhere.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

TENANTS = ("tenant-alpha", "tenant-bravo", "tenant-charlie")
TENANT_CUSTOMER_IDS = {"tenant-alpha": 1, "tenant-bravo": 2, "tenant-charlie": 3}
SEVERITIES = ("low", "medium", "high", "critical")
PRODUCTS = ("FortiSIEM", "FortiEDR", "SentinelOne")
ANALYSTS = ("Tamara", "Elena", "Frederik", "Johannes")

# Source cardinalities. These live here (not in the generators) so any generator
# can size a cross-source relationship without importing a sibling module.
DEFAULT_CASE_COUNT = 60
DEFAULT_ALERT_COUNT = 240
DEFAULT_SHUFFLE_RUN_COUNT = 120
DEFAULT_CUSTOMER_SYSTEM_COUNT = 45

# Real DFIR-IRIS severity scale (non-sequential): 1=Medium, 2=Unspecified,
# 3=Informational, 4=Low, 5=High, 6=Critical. The mock must emit these real ids
# so the ETL reverse-map exercises the true enum (a plain 1..4 ramp would not).
IRIS_SEVERITY_ID = {"low": 4, "medium": 1, "high": 5, "critical": 6}

# Fixed UTC anchor so generated timestamps are byte-stable across runs/machines.
BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)
SPREAD_DAYS = 120


def tenant_for(index: int) -> str:
    """Return a tenant id derived from *index* (cycles over ``TENANTS``)."""
    return TENANTS[index % len(TENANTS)]


def severity_for(index: int) -> str:
    """Return a normalized severity label derived from *index*."""
    return SEVERITIES[index % len(SEVERITIES)]


def spread_timestamp(index: int, population_size: int | None = None) -> datetime:
    """Return a tz-aware UTC timestamp spread across ``SPREAD_DAYS`` from *index*."""
    if population_size is not None and population_size > 1:
        day_offset = (index * (SPREAD_DAYS - 1)) // (population_size - 1)
    else:
        day_offset = index % SPREAD_DAYS
    return BASE_TIME + timedelta(
        days=day_offset,
        hours=(index * 5) % 24,
        minutes=(index * 7) % 60,
    )


def case_id(index: int) -> str:
    """Return a stable DFIR-IRIS source case id for *index*."""
    return f"IRIS-CASE-{index:05d}"


def alert_id(index: int) -> str:
    """Return a stable security-alert source id for *index*."""
    return f"ALERT-{index:06d}"


def run_id(index: int) -> str:
    """Return a stable Shuffle run source id for *index*."""
    return f"SHFL-RUN-{index:05d}"


def system_id(index: int) -> str:
    """Return a stable monitored-system id for *index*."""
    return f"SYSTEM-{index:05d}"


def system_hostname(index: int) -> str:
    """Return the stable hostname for monitored-system *index*.

    Alerts anchor their native host field to this exact value so the ETL can
    resolve ``system_id`` by a hostname join (entity resolution) rather than a
    pre-baked foreign key. Both callers must agree, so the formula lives here.
    """
    tenant = TENANTS[index % len(TENANTS)].removeprefix("tenant-")
    return f"{tenant}-host-{index:03d}"


def epoch_ms(moment: datetime) -> int:
    """Return Unix epoch milliseconds for *moment* (FortiSIEM/S1 use ms)."""
    return int(moment.timestamp() * 1000)


def epoch_s(moment: datetime) -> int:
    """Return Unix epoch seconds for *moment* (Shuffle executions use seconds)."""
    return int(moment.timestamp())


def iso_micros(moment: datetime) -> str:
    """Return an ISO-8601 UTC string with microseconds and a ``Z`` suffix.

    Matches the SentinelOne / DFIR-IRIS datetime format (e.g. the analyst-verdict
    activity feed and IRIS ``modification_history`` / custom-attribute values).
    """
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def iso_date(moment: datetime) -> str:
    """Return a date-only ISO string (DFIR-IRIS ``open_date`` / ``close_date``)."""
    return moment.astimezone(UTC).strftime("%Y-%m-%d")


def fortiedr_timestamp(moment: datetime) -> str:
    """Return a ``yyyy-MM-dd HH:mm:ss`` string (FortiEDR event timestamps)."""
    return moment.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
