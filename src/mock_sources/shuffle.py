"""Deterministic mock generator for Shuffle-like automation runs.

Columns drive the KPI dashboard (run volume by workflow, success rate, median
runtime); ``payload`` carries a light Shuffle execution shape for realism.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ._common import (
    alert_id,
    case_id,
    epoch_ms,
    run_id,
    spread_timestamp,
    tenant_for,
)
from .dfir_iris import DEFAULT_CASE_COUNT
from .siem import DEFAULT_ALERT_COUNT

WORKFLOWS = (
    "enrich-ip",
    "auto-contain-host",
    "notify-analyst",
    "auto-close-incident",
)


@dataclass(frozen=True, slots=True)
class ShuffleRun:
    """A mocked Shuffle-like automation run, tenant-scoped."""

    source_run_id: str
    tenant_id: str
    workflow_name: str
    started_at: datetime
    ended_at: datetime
    result_status: str
    related_alert_id: str | None
    related_case_id: str | None
    payload: dict[str, object]


def _build_run(
    index: int, run_count: int, alert_count: int, case_count: int
) -> ShuffleRun:
    """Build one deterministic automation run from *index*."""
    tenant = tenant_for(index)
    workflow = WORKFLOWS[index % 4]
    started_at = spread_timestamp(index, run_count)
    ended_at = started_at + timedelta(seconds=30 + (index % 20) * 45)
    is_success = index % 5 != 0
    result_status = "success" if is_success else "failure"
    related_alert_id = alert_id(index % alert_count) if alert_count > 0 else None
    related_case_id = (
        case_id(index % case_count)
        if case_count > 0 and workflow in {"notify-analyst", "auto-close-incident"}
        else None
    )
    payload: dict[str, object] = {
        "execution_id": f"exec-{index:012d}",
        "workflow": {"name": workflow},
        "status": "FINISHED" if is_success else "ABORTED",
        "started_at": epoch_ms(started_at),
        "completed_at": epoch_ms(ended_at),
        "result_count": 2 + (index % 4),
        "related_case_id": related_case_id,
    }
    return ShuffleRun(
        source_run_id=run_id(index),
        tenant_id=tenant,
        workflow_name=workflow,
        started_at=started_at,
        ended_at=ended_at,
        result_status=result_status,
        related_alert_id=related_alert_id,
        related_case_id=related_case_id,
        payload=payload,
    )


def generate_shuffle_runs(
    count: int = 120,
    alert_count: int = DEFAULT_ALERT_COUNT,
    case_count: int = DEFAULT_CASE_COUNT,
) -> list[ShuffleRun]:
    """Return *count* deterministic Shuffle-like automation runs in stable order."""
    return [_build_run(i, count, alert_count, case_count) for i in range(count)]
