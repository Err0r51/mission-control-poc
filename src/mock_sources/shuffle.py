"""Deterministic mock generator for Shuffle automation runs.

Emits Shuffle ``WorkflowExecution`` objects into a ``payload`` that is the sole
source of truth; the row carries only thin routing columns. Faithful to the real
struct: ``started_at``/``completed_at`` are int64 Unix epoch **seconds**, the
``status`` enum is ``FINISHED``/``FAILED``/``ABORTED``, the workflow name lives on
the embedded ``workflow`` object, and the triggering alert/case ids live inside
``execution_argument`` as a **stringified JSON** blob. The ETL parses all of it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta

from ._common import (
    DEFAULT_ALERT_COUNT,
    DEFAULT_CASE_COUNT,
    DEFAULT_SHUFFLE_RUN_COUNT,
    alert_id,
    case_id,
    epoch_s,
    run_id,
    spread_timestamp,
    tenant_for,
)

WORKFLOWS = (
    "enrich-ip",
    "auto-contain-host",
    "notify-analyst",
    "auto-close-incident",
)
# Workflows that operate on an open case carry a case id in the trigger payload.
_CASE_BOUND_WORKFLOWS = {"notify-analyst", "auto-close-incident"}


@dataclass(frozen=True, slots=True)
class ShuffleRun:
    """A mocked Shuffle run: thin routing fields plus the native payload."""

    source_run_id: str
    tenant_id: str
    source_event_time: datetime
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
    status = "FINISHED" if is_success else ("FAILED", "ABORTED")[(index // 5) % 2]

    related_alert = alert_id(index % alert_count) if alert_count > 0 else None
    related_case = (
        case_id(index % case_count)
        if case_count > 0 and workflow in _CASE_BOUND_WORKFLOWS
        else None
    )
    execution_argument = json.dumps(
        {
            "alert_id": related_alert,
            "case_id": related_case,
            "tenant": tenant,
        }
    )

    payload: dict[str, object] = {
        "execution_id": f"exec-{index:012d}",
        "workflow": {"id": f"wf-{index % 4}", "name": workflow},
        "status": status,
        "started_at": epoch_s(started_at),
        "completed_at": epoch_s(ended_at),
        "execution_argument": execution_argument,
        "execution_source": "trigger",
        "org_id": tenant,
        "priority": 1 + index % 3,
        "result_count": 2 + (index % 4),
    }
    return ShuffleRun(
        source_run_id=run_id(index),
        tenant_id=tenant,
        source_event_time=started_at,
        payload=payload,
    )


def generate_shuffle_runs(
    count: int = DEFAULT_SHUFFLE_RUN_COUNT,
    alert_count: int = DEFAULT_ALERT_COUNT,
    case_count: int = DEFAULT_CASE_COUNT,
) -> list[ShuffleRun]:
    """Return *count* deterministic Shuffle automation runs in stable order."""
    return [_build_run(i, count, alert_count, case_count) for i in range(count)]
