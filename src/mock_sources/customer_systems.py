"""Deterministic mock generator for monitored customer-system inventory.

Emits a monitored-system record into a ``payload`` that is the sole source of
truth; the row carries only thin routing columns. The ``hostname`` matches the
value alerts put in their native host field, so the ETL resolves ``system_id``
by a hostname join rather than a pre-baked foreign key.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ._common import (
    DEFAULT_CUSTOMER_SYSTEM_COUNT,
    PRODUCTS,
    TENANTS,
    iso_micros,
    spread_timestamp,
    system_hostname,
    system_id,
)


@dataclass(frozen=True, slots=True)
class CustomerSystem:
    """A monitored customer system: thin routing fields plus the native payload."""

    system_id: str
    tenant_id: str
    source_product: str
    source_event_time: datetime
    payload: dict[str, object]


def _build_customer_system(index: int, system_count: int) -> CustomerSystem:
    tenant = TENANTS[index % len(TENANTS)]
    product = PRODUCTS[(index // len(TENANTS)) % len(PRODUCTS)]
    monitored_from = spread_timestamp(index, system_count) - timedelta(
        days=18 + (index % 10),
        hours=(index * 3) % 6,
    )
    monitored_to = (
        monitored_from + timedelta(days=35 + (index % 28))
        if index % 6 == 0
        else None
    )
    hostname = system_hostname(index)
    payload: dict[str, object] = {
        "hostname": hostname,
        "tenant": tenant,
        "sensor": product,
        "enrolled_at": iso_micros(monitored_from),
        "retired_at": iso_micros(monitored_to) if monitored_to is not None else None,
        "monitoring_state": "retired" if monitored_to is not None else "active",
    }
    return CustomerSystem(
        system_id=system_id(index),
        tenant_id=tenant,
        source_product=product,
        source_event_time=monitored_from,
        payload=payload,
    )


def generate_customer_systems(
    count: int = DEFAULT_CUSTOMER_SYSTEM_COUNT,
) -> list[CustomerSystem]:
    """Return *count* deterministic monitored-system intervals."""
    return [_build_customer_system(i, count) for i in range(count)]
