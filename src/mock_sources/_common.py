"""Shared constants and deterministic helpers for the mock source generators.

This module holds the values every generator needs (tenants, severities, the
time anchor) plus pure, index-based helpers. It imports nothing from the
generator modules, so there is no import cycle.

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

# DFIR-IRIS severity scale is 1..6; map our normalized labels onto it.
SEVERITY_TO_IRIS_ID = {"low": 2, "medium": 3, "high": 4, "critical": 5}

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


def epoch_ms(moment: datetime) -> int:
    """Return Unix epoch milliseconds for *moment* (Fortinet/SentinelOne use ms)."""
    return int(moment.timestamp() * 1000)
