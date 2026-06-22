"""Deterministic mock generator for monitored customer-system inventory."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ._common import PRODUCTS, TENANTS, spread_timestamp, system_id

DEFAULT_CUSTOMER_SYSTEM_COUNT = 45


@dataclass(frozen=True, slots=True)
class CustomerSystem:
    """A monitored customer system interval, tenant-scoped and deterministic."""

    system_id: str
    tenant_id: str
    source_product: str
    hostname: str
    monitored_from: datetime
    monitored_to: datetime | None
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
    hostname = f"{tenant.removeprefix('tenant-')}-host-{index:03d}"
    payload: dict[str, object] = {
        "hostname": hostname,
        "tenant": tenant,
        "sensor": product,
        "monitoring_state": "retired" if monitored_to is not None else "active",
    }
    return CustomerSystem(
        system_id=system_id(index),
        tenant_id=tenant,
        source_product=product,
        hostname=hostname,
        monitored_from=monitored_from,
        monitored_to=monitored_to,
        payload=payload,
    )


def generate_customer_systems(
    count: int = DEFAULT_CUSTOMER_SYSTEM_COUNT,
) -> list[CustomerSystem]:
    """Return *count* deterministic monitored-system intervals."""
    return [_build_customer_system(i, count) for i in range(count)]
