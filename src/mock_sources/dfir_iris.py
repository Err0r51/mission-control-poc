"""Deterministic mock generator for DFIR-IRIS-like investigation cases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ._common import (
    ANALYSTS,
    SEVERITIES,
    SEVERITY_TO_IRIS_ID,
    TENANT_CUSTOMER_IDS,
    case_id,
    run_id,
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
CASE_OUTCOMES = ("true_positive", "false_positive", "undetermined")

DEFAULT_CASE_COUNT = 60


@dataclass(frozen=True, slots=True)
class DfirIrisCase:
    """A mocked DFIR-IRIS-like case, source-shaped and tenant-scoped."""

    source_case_id: str
    tenant_id: str
    severity: str
    status: str
    occurred_at: datetime
    opened_at: datetime
    closed_at: datetime | None
    case_outcome: str | None
    assigned_team: str
    assigned_analyst: str
    closed_by: str | None
    auto_closed_by_run_id: str | None
    payload: dict[str, object]


def _build_case(index: int, case_count: int, shuffle_run_count: int) -> DfirIrisCase:
    """Build one deterministic case from *index* (mixed-radix dimensions)."""
    tenant = tenant_for(index)
    severity = SEVERITIES[index % 4]
    is_closed = index % 10 < 7
    status = "closed" if is_closed else "open"
    first_alert_at = spread_timestamp(index, case_count)
    occurred_at = first_alert_at - timedelta(hours=2 + (index % 6) * 2)
    opened_at = first_alert_at + timedelta(minutes=30 + (index % 5) * 20)
    team = TEAMS[(index // 4) % 3]
    analyst = ANALYSTS[(index // 12) % 4]
    title = CASE_TITLES[(index // 3) % 4]
    auto_closed = (
        is_closed
        and index < shuffle_run_count
        and index % 20 == 3
    )
    case_outcome = None
    if is_closed:
        case_outcome = (
            "true_positive" if auto_closed else CASE_OUTCOMES[(index // 4) % 3]
        )
    closed_at = (
        opened_at + timedelta(hours=4 + (index % 12) * 6)
        if is_closed
        else None
    )
    closed_by = None if not is_closed else ("shuffle-bot" if auto_closed else analyst)
    auto_closed_by_run_id = run_id(index) if auto_closed else None
    payload: dict[str, object] = {
        "case_id": index + 1,
        "case_name": f"#{index + 1} - {title}",
        "severity_id": SEVERITY_TO_IRIS_ID[severity],
        "state_id": 3 if status == "open" else 5,
        "case_customer_id": TENANT_CUSTOMER_IDS[tenant],
        "owner": analyst,
        "classification_id": (index % 5) + 1,
        "occurred_at": occurred_at.isoformat(),
        "case_outcome": case_outcome,
        "closed_by": closed_by,
        "auto_closed_by_run_id": auto_closed_by_run_id,
    }
    return DfirIrisCase(
        source_case_id=case_id(index),
        tenant_id=tenant,
        severity=severity,
        status=status,
        occurred_at=occurred_at,
        opened_at=opened_at,
        closed_at=closed_at,
        case_outcome=case_outcome,
        assigned_team=team,
        assigned_analyst=analyst,
        closed_by=closed_by,
        auto_closed_by_run_id=auto_closed_by_run_id,
        payload=payload,
    )


def generate_dfir_iris_cases(
    count: int = DEFAULT_CASE_COUNT,
    shuffle_run_count: int = 120,
) -> list[DfirIrisCase]:
    """Return *count* deterministic DFIR-IRIS-like cases in stable order."""
    return [_build_case(i, count, shuffle_run_count) for i in range(count)]
