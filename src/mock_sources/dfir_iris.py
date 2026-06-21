"""Deterministic mock generator for DFIR-IRIS-like investigation cases.

Records are source-shaped but KPI-lean: the columns drive the overview
dashboard (case volume, open vs closed, severity mix, median time-to-close),
while ``payload`` carries a light DFIR-IRIS REST API v2 shape for realism.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ._common import (
    SEVERITIES,
    SEVERITY_TO_IRIS_ID,
    TENANT_CUSTOMER_IDS,
    case_id,
    spread_timestamp,
    tenant_for,
)

CASE_TITLES = (
    "Suspicious login",
    "Malware detection",
    "Data exfiltration",
    "Phishing report",
)
TEAMS = ("triage", "incident-response", "threat-hunting")
ANALYSTS = ("alice", "bob", "carol", "dave")

DEFAULT_CASE_COUNT = 60


@dataclass(frozen=True, slots=True)
class DfirIrisCase:
    """A mocked DFIR-IRIS-like case, source-shaped and tenant-scoped."""

    source_case_id: str
    tenant_id: str
    severity: str
    status: str
    opened_at: datetime
    closed_at: datetime | None
    assigned_team: str
    payload: dict[str, object]


def _build_case(index: int) -> DfirIrisCase:
    """Build one deterministic case from *index* (mixed-radix dimensions)."""
    tenant = tenant_for(index)
    severity = SEVERITIES[index % 4]
    is_closed = index % 10 < 7
    status = "closed" if is_closed else "open"
    opened_at = spread_timestamp(index)
    closed_at = opened_at + timedelta(hours=4 + (index % 12) * 6) if is_closed else None
    # Decorrelate each dimension off a different digit of the index so KPI
    # breakdowns are non-degenerate (see _common docstring): severity = index % 4,
    # team = (index // 4) % 3, analyst = (index // 12) % 4, title = (index // 3) % 4.
    team = TEAMS[(index // 4) % 3]
    analyst = ANALYSTS[(index // 12) % 4]
    title = CASE_TITLES[(index // 3) % 4]
    payload: dict[str, object] = {
        "case_id": index + 1,
        "case_name": f"#{index + 1} - {title}",
        "severity_id": SEVERITY_TO_IRIS_ID[severity],
        "state_id": 3 if status == "open" else 5,
        "case_customer_id": TENANT_CUSTOMER_IDS[tenant],
        "owner": analyst,
        "classification_id": (index % 5) + 1,
    }
    return DfirIrisCase(
        source_case_id=case_id(index),
        tenant_id=tenant,
        severity=severity,
        status=status,
        opened_at=opened_at,
        closed_at=closed_at,
        assigned_team=team,
        payload=payload,
    )


def generate_dfir_iris_cases(count: int = DEFAULT_CASE_COUNT) -> list[DfirIrisCase]:
    """Return *count* deterministic DFIR-IRIS-like cases in stable order."""
    return [_build_case(i) for i in range(count)]
