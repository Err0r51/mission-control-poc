"""Deterministic mock generator for security alerts across three products.

The security-alert feed spans the three real products in use -- FortiSIEM,
FortiEDR, and SentinelOne -- discriminated by ``source_product``. Each alert is
emitted as a **product-native payload** matching the real API response shape
(field names, enums, and timestamp formats differ per product); the row carries
only thin routing columns. All normalization (severity, resolution, triage,
reviewer, host resolution) is done later in the analytics ETL.

Dimensions are decorrelated via mixed-radix so KPI breakdowns are non-degenerate:
tenant = i%3, product = (i//3)%3, severity = i%4, triage = (i//4)%4,
resolution = (i//9)%3 -- independent of one another.

Reviewer attribution is deliberately product-faithful: FortiSIEM exposes the
clearing user only once an incident is cleared; SentinelOne exposes the verdict
author in its activity feed once a verdict is set; FortiEDR's events API has no
reviewer field at all (the ETL falls back to the escalated case owner).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ._common import (
    ANALYSTS,
    DEFAULT_ALERT_COUNT,
    DEFAULT_CASE_COUNT,
    DEFAULT_CUSTOMER_SYSTEM_COUNT,
    PRODUCTS,
    SEVERITIES,
    TENANT_CUSTOMER_IDS,
    alert_id,
    epoch_ms,
    fortiedr_timestamp,
    iso_micros,
    spread_timestamp,
    system_hostname,
    tenant_for,
)

TRIAGE_STATUSES = ("new", "in_progress", "escalated", "closed")
RESOLUTIONS = ("true_positive", "false_positive", "undetermined")

# Per-product detection labels.
FORTISIEM_RULES = (
    "Brute force authentication failure",
    "Suspicious outbound connection",
    "Privilege escalation detected",
    "Malware beacon detected",
    "Impossible travel login",
)
FORTIEDR_PROCESSES = (
    "powershell.exe",
    "svchost.exe",
    "rundll32.exe",
    "wscript.exe",
    "mshta.exe",
)
SENTINELONE_THREATS = (
    "Trojan.GenericKD",
    "Ransom.Conti",
    "PUA.CoinMiner",
    "Backdoor.Cobalt",
    "Exploit.CVE-2023",
)

ATTACK_TACTICS = (
    "Initial Access",
    "Execution",
    "Privilege Escalation",
    "Command and Control",
    "Impact",
)
ATTACK_TECHNIQUES = ("T1078", "T1059", "T1068", "T1071", "T1486")

# Normalized severity -> FortiSIEM numeric score (1-10) + category. The ETL
# recovers the 4 levels from the numeric score; categories alone would collapse
# high and critical, so the number is what carries the fidelity.
_FORTISIEM_SEVERITY = {
    "low": (3, "LOW"),
    "medium": (6, "MEDIUM"),
    "high": (9, "HIGH"),
    "critical": (10, "HIGH"),
}
_FORTIEDR_SEVERITY = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
    "critical": "Critical",
}
# SentinelOne's threats API has no discrete severity, only a 2-level confidence.
_S1_CONFIDENCE = {
    "low": "suspicious",
    "medium": "suspicious",
    "high": "malicious",
    "critical": "malicious",
}
_S1_VERDICT = {
    "true_positive": "true_positive",
    "false_positive": "false_positive",
    "undetermined": "undefined",
}
# FortiSIEM incident disposition (incidentReso).
_FORTISIEM_RESO = {"true_positive": 2, "false_positive": 3, "undetermined": 1}
# FortiEDR classification.
_FORTIEDR_CLASS = {
    "true_positive": "Malicious",
    "false_positive": "Safe",
    "undetermined": "PUP",
}
# SentinelOne threat lifecycle from the triage dimension.
_S1_INCIDENT_STATUS = ("unresolved", "in_progress", "in_progress", "resolved")


@dataclass(frozen=True, slots=True)
class SecurityAlert:
    """A mocked security alert: thin routing fields plus the native payload."""

    source_alert_id: str
    tenant_id: str
    source_product: str
    source_event_time: datetime
    payload: dict[str, object]


def _fortisiem_payload(
    index: int,
    name: str,
    severity: str,
    tenant: str,
    resolution: str,
    is_cleared: bool,
    hostname: str,
    event_at: datetime,
    reviewer: str | None,
    reviewed_at: datetime | None,
) -> dict[str, object]:
    score, category = _FORTISIEM_SEVERITY[severity]
    return {
        "incidentId": 100000 + index,
        "incidentTitle": name,
        "eventType": "PH_RULE_SECURITY",
        "eventSeverity": score,
        "eventSeverityCat": category,
        "incidentStatus": 2 if is_cleared else 0,
        "incidentReso": _FORTISIEM_RESO[resolution],
        "incidentFirstSeen": epoch_ms(event_at),
        "incidentLastSeen": epoch_ms(event_at),
        "incidentTarget": f"hostIpAddr:10.10.0.{index % 250}, hostName:{hostname}",
        "incidentRptDevName": "FortiSIEM-Supervisor",
        "incidentClearedUser": reviewer if is_cleared else None,
        "incidentClearedTime": (
            epoch_ms(reviewed_at) if is_cleared and reviewed_at else None
        ),
        "attackTactic": ATTACK_TACTICS[index % 5],
        "attackTechnique": ATTACK_TECHNIQUES[index % 5],
        "customer": tenant,
        "phCustId": TENANT_CUSTOMER_IDS[tenant],
        "count": 1 + index % 7,
    }


def _fortiedr_payload(
    index: int,
    name: str,
    severity: str,
    resolution: str,
    is_cleared: bool,
    hostname: str,
    event_at: datetime,
) -> dict[str, object]:
    stamp = fortiedr_timestamp(event_at)
    return {
        "eventId": str(400000 + index),
        "rawDataId": 1270000000 + index,
        "eventTime": stamp,
        "firstSeen": stamp,
        "lastSeen": stamp,
        "classification": _FORTIEDR_CLASS[resolution],
        "severity": _FORTIEDR_SEVERITY[severity],
        "action": "Block" if severity in ("high", "critical") else "Log",
        "handled": is_cleared,
        "process": name,
        "processName": name,
        "deviceName": hostname,
        "deviceId": f"DVC-{index:06d}",
        "collectorId": f"COL-{index % DEFAULT_CUSTOMER_SYSTEM_COUNT:04d}",
        "agentId": f"AGT-{index % DEFAULT_CUSTOMER_SYSTEM_COUNT:04d}",
        "threatDetails": {
            "threatName": name,
            "threatFamily": "Generic",
            "threatType": "Process",
        },
    }


def _sentinelone_payload(
    index: int,
    name: str,
    severity: str,
    triage_index: int,
    resolution: str,
    hostname: str,
    event_at: datetime,
    has_verdict: bool,
    reviewer: str | None,
    reviewed_at: datetime | None,
) -> dict[str, object]:
    created = iso_micros(event_at)
    updated = iso_micros(reviewed_at) if reviewed_at is not None else created
    threat_info = {
        "threatId": f"{7000000000 + index}",
        "threatName": name,
        # Decorrelate classification from tenant (index % 3) via a higher digit.
        "classification": ("Malware", "Ransomware", "PUA")[(index // 27) % 3],
        "classificationSource": "Engine",
        "confidenceLevel": _S1_CONFIDENCE[severity],
        "analystVerdict": _S1_VERDICT[resolution] if has_verdict else "undefined",
        "incidentStatus": _S1_INCIDENT_STATUS[triage_index],
        "mitigationStatus": "mitigated" if triage_index == 3 else "active",
        "createdAt": created,
        "updatedAt": updated,
    }
    payload: dict[str, object] = {
        "id": f"S1-{index:012d}",
        "threatId": f"{7000000000 + index}",
        "agentId": f"{index % DEFAULT_CUSTOMER_SYSTEM_COUNT}",
        "createdAt": created,
        "updatedAt": updated,
        "identifiedAt": created,
        "threatInfo": threat_info,
        "agentRealtimeInfo": {
            "agentId": f"{index % DEFAULT_CUSTOMER_SYSTEM_COUNT}",
            "agentComputerName": hostname,
            "agentOsType": "windows",
        },
        "agentDetectionInfo": {"agentIpV4": f"10.20.0.{index % 250}"},
    }
    # The verdict author lives in the Activities feed, not on the threat object.
    if has_verdict and reviewer is not None:
        payload["threatTimeline"] = {
            "username": reviewer,
            "newAnalystVerdict": _S1_VERDICT[resolution],
            "updatedAt": updated,
        }
    return payload


def _build_alert(
    index: int,
    alert_count: int,
    case_count: int,
    customer_system_count: int,
) -> SecurityAlert:
    """Build one deterministic alert from *index* (mixed-radix dimensions)."""
    tenant = tenant_for(index)
    product = PRODUCTS[(index // 3) % 3]
    severity = SEVERITIES[index % 4]
    triage_index = (index // 4) % 4
    is_new = triage_index == 0
    is_cleared = triage_index == 3
    event_at = spread_timestamp(index, alert_count)
    resolution = "undetermined" if is_new else RESOLUTIONS[(index // 9) % 3]

    system_count = customer_system_count if customer_system_count > 0 else 1
    hostname = system_hostname(index % system_count)

    reviewed_at = (
        event_at + timedelta(minutes=20 + (index % 6) * 35) if not is_new else None
    )
    reviewer = ANALYSTS[(index // 12) % 4] if not is_new else None

    if product == "FortiSIEM":
        name = FORTISIEM_RULES[index % 5]
        payload = _fortisiem_payload(
            index, name, severity, tenant, resolution,
            is_cleared, hostname, event_at, reviewer, reviewed_at,
        )
    elif product == "FortiEDR":
        name = FORTIEDR_PROCESSES[index % 5]
        payload = _fortiedr_payload(
            index, name, severity, resolution, is_cleared, hostname, event_at
        )
    else:
        name = SENTINELONE_THREATS[index % 5]
        payload = _sentinelone_payload(
            index, name, severity, triage_index, resolution, hostname,
            event_at, not is_new, reviewer, reviewed_at,
        )

    return SecurityAlert(
        source_alert_id=alert_id(index),
        tenant_id=tenant,
        source_product=product,
        source_event_time=event_at,
        payload=payload,
    )


def generate_security_alerts(
    count: int = DEFAULT_ALERT_COUNT,
    case_count: int = DEFAULT_CASE_COUNT,
    customer_system_count: int = DEFAULT_CUSTOMER_SYSTEM_COUNT,
) -> list[SecurityAlert]:
    """Return *count* deterministic security alerts across the three products."""
    return [
        _build_alert(i, count, case_count, customer_system_count)
        for i in range(count)
    ]
