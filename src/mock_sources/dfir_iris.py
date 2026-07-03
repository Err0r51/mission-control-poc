"""Deterministic mock generator for DFIR-IRIS investigation cases.

Emits product-native DFIR-IRIS case objects (real field names and the real,
non-sequential ``severity_id`` / ``status_id`` / ``state_id`` enums) into a
``payload`` that is the sole source of truth; the row itself carries only thin
routing columns. All KPI-relevant normalization and cross-source correlation is
done later in the analytics ETL, not here.

Determinism is mixed-radix on the case index (see ``_common``). The originating
SIEM alert is carried on ``case_soc_id`` (a real IRIS SOC/ticket ref), giving a
clean 1:1 case<->alert bijection the ETL reconstructs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ._common import (
    ANALYSTS,
    DEFAULT_ALERT_COUNT,
    DEFAULT_CASE_COUNT,
    DEFAULT_SHUFFLE_RUN_COUNT,
    IRIS_SEVERITY_ID,
    SEVERITIES,
    TENANT_CUSTOMER_IDS,
    alert_id,
    case_id,
    iso_date,
    iso_micros,
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

# Real IRIS status_id (case resolution): 1=false positive, 2=true positive with
# impact, 3=not applicable, 4=true positive without impact, 5=legitimate. Encode
# the intended analyst outcome so the ETL can reverse it.
OUTCOME_TO_STATUS_ID = {"true_positive": 2, "false_positive": 1, "undetermined": 3}


@dataclass(frozen=True, slots=True)
class DfirIrisCase:
    """A mocked DFIR-IRIS case: thin routing fields plus the native payload."""

    source_case_id: str
    tenant_id: str
    source_event_time: datetime
    payload: dict[str, object]


def _detect_lag(index: int) -> timedelta:
    """Minutes the SIEM took to fire after the incident began (MTTD driver)."""
    return timedelta(minutes=15 + (index % 6) * 10)


def _modification_entry(user: str, user_id: int, action: str) -> dict[str, object]:
    return {"user": user, "user_id": user_id, "action": action}


def _build_case(index: int, case_count: int, shuffle_run_count: int) -> DfirIrisCase:
    """Build one deterministic case from *index* (mixed-radix dimensions)."""
    tenant = tenant_for(index)
    severity = SEVERITIES[index % 4]
    is_closed = index % 10 < 7
    state_id = 9 if is_closed else 2  # 9=Closed, 2=In progress

    # Re-anchor detection time to the constituent alert so MTTD is well-defined:
    # the originating alert (index-aligned) fired _detect_lag after occurrence.
    constituent_alert_at = spread_timestamp(index, DEFAULT_ALERT_COUNT)
    occurred_at = constituent_alert_at - _detect_lag(index)

    # Lifecycle times stay index-derived so MTTR and month bucketing are stable.
    opened_at = spread_timestamp(index, case_count) + timedelta(
        minutes=30 + (index % 5) * 20
    )
    team = TEAMS[(index // 4) % 3]
    owner_id = (index // 12) % 4 + 1
    analyst = ANALYSTS[owner_id - 1]
    title = CASE_TITLES[(index // 3) % 4]

    auto_closed = is_closed and index < shuffle_run_count and index % 20 == 3
    closed_at = (
        opened_at + timedelta(hours=4 + (index % 12) * 6) if is_closed else None
    )
    closer = "shuffle-bot" if auto_closed else analyst

    intended_outcome = None
    if is_closed:
        intended_outcome = (
            "true_positive" if auto_closed else CASE_OUTCOMES[(index // 4) % 3]
        )
    status_id = OUTCOME_TO_STATUS_ID[intended_outcome] if is_closed else 0

    modification_history: dict[str, object] = {
        f"{opened_at.timestamp():.6f}": _modification_entry(
            analyst, owner_id, "case opened"
        )
    }
    if is_closed and closed_at is not None:
        closer_id = 99 if auto_closed else owner_id
        modification_history[f"{closed_at.timestamp():.6f}"] = _modification_entry(
            closer, closer_id, "case closed"
        )

    payload: dict[str, object] = {
        "case_id": index + 1,
        "case_uuid": f"00000000-0000-4000-8000-{index:012d}",
        "case_name": f"#{index + 1} - {title}",
        "case_description": f"{title} reported for {tenant}.",
        "case_customer_id": TENANT_CUSTOMER_IDS[tenant],
        "case_soc_id": alert_id(index),
        "severity_id": IRIS_SEVERITY_ID[severity],
        "status_id": status_id,
        "state_id": state_id,
        "owner_id": owner_id,
        "owner": {
            "id": owner_id,
            "user_name": analyst,
            "user_login": analyst.lower(),
        },
        "classification_id": (index % 5) + 1,
        "open_date": iso_date(opened_at),
        "close_date": iso_date(closed_at) if closed_at is not None else None,
        "case_tags": f"tenant:{tenant},sev:{severity}",
        "custom_attributes": {
            "soc": {
                "occurred_at": iso_micros(occurred_at),
                "assigned_team": team,
            }
        },
        "modification_history": modification_history,
    }
    return DfirIrisCase(
        source_case_id=case_id(index),
        tenant_id=tenant,
        source_event_time=opened_at,
        payload=payload,
    )


def generate_dfir_iris_cases(
    count: int = DEFAULT_CASE_COUNT,
    shuffle_run_count: int = DEFAULT_SHUFFLE_RUN_COUNT,
) -> list[DfirIrisCase]:
    """Return *count* deterministic DFIR-IRIS cases in stable order."""
    return [_build_case(i, count, shuffle_run_count) for i in range(count)]
