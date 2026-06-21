"""Deterministic mock generator for security alerts.

This single source represents the security-alerting feed across the three real
products in use -- FortiSIEM, FortiEDR, and SentinelOne -- discriminated by the
``source_product`` column (FortiSIEM aggregates the EDRs in practice, so a
unified feed is faithful). Columns drive the KPI dashboard (alert volume by
product / severity / day, true vs false positive rate, escalation-to-case
rate); ``payload`` carries a light, product-shaped object for realism.

Dimensions are decorrelated via mixed-radix so KPI breakdowns are non-degenerate:
tenant = i%3, product = (i//3)%3, severity = i%4, triage = (i//4)%4,
resolution = (i//9)%3 -- independent of one another.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ._common import (
    PRODUCTS,
    SEVERITIES,
    alert_id,
    case_id,
    spread_timestamp,
    tenant_for,
)
from .dfir_iris import DEFAULT_CASE_COUNT

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

# Normalized severity -> product-native representations.
_FORTISIEM_SEVERITY = {
    "low": (2, "LOW"),
    "medium": (5, "MEDIUM"),
    "high": (8, "HIGH"),
    "critical": (10, "HIGH"),
}
_FORTIEDR_SEVERITY = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
    "critical": "Critical",
}
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


@dataclass(frozen=True, slots=True)
class SecurityAlert:
    """A mocked security alert from FortiSIEM, FortiEDR, or SentinelOne."""

    source_alert_id: str
    tenant_id: str
    source_product: str
    detection_name: str
    severity: str
    event_at: datetime
    triage_status: str
    resolution: str
    linked_case_id: str | None
    payload: dict[str, object]


def _fortisiem_payload(index: int, name: str, severity: str, tenant: str) -> dict:
    score, category = _FORTISIEM_SEVERITY[severity]
    reso = {"true_positive": 2, "false_positive": 3, "undetermined": 4}[
        RESOLUTIONS[(index // 9) % 3]
    ]
    status = 2 if TRIAGE_STATUSES[(index // 4) % 4] == "closed" else 0
    return {
        "incidentId": 100000 + index,
        "incidentTitle": name,
        "eventSeverity": score,
        "eventSeverityCat": category,
        "incidentStatus": status,
        "incidentReso": reso,
        "attackTactic": ATTACK_TACTICS[index % 5],
        "attackTechnique": ATTACK_TECHNIQUES[index % 5],
        "customer": tenant,
    }


def _fortiedr_payload(index: int, name: str, severity: str) -> dict:
    classification = {
        "true_positive": "Malicious",
        "false_positive": "Safe",
        "undetermined": "PUP",
    }[RESOLUTIONS[(index // 9) % 3]]
    return {
        "eventId": 400000 + index,
        "rawDataId": 1270000000 + index,
        "classification": classification,
        "severity": _FORTIEDR_SEVERITY[severity],
        "process": name,
        "deviceName": f"host-{index % 20}",
        "action": "Blocked" if severity in ("high", "critical") else "Logged",
    }


def _sentinelone_payload(index: int, name: str, severity: str) -> dict:
    mitigation = (
        "mitigated" if TRIAGE_STATUSES[(index // 4) % 4] == "closed" else "active"
    )
    return {
        "threatInfo": {
            "threatName": name,
            "classification": ("Malware", "Ransomware", "PUA")[index % 3],
            "confidenceLevel": _S1_CONFIDENCE[severity],
            "mitigationStatus": mitigation,
            "analystVerdict": _S1_VERDICT[RESOLUTIONS[(index // 9) % 3]],
            "detectionType": "static" if index % 2 == 0 else "dynamic",
        },
        "agentRealtimeInfo": {"agentComputerName": f"host-{index % 20}"},
    }


def _build_alert(index: int) -> SecurityAlert:
    """Build one deterministic alert from *index* (mixed-radix dimensions)."""
    tenant = tenant_for(index)
    product = PRODUCTS[(index // 3) % 3]
    severity = SEVERITIES[index % 4]
    triage = TRIAGE_STATUSES[(index // 4) % 4]
    resolution = RESOLUTIONS[(index // 9) % 3]
    event_at = spread_timestamp(index)
    linked_case_id = (
        case_id(index % DEFAULT_CASE_COUNT) if triage == "escalated" else None
    )

    if product == "FortiSIEM":
        name = FORTISIEM_RULES[index % 5]
        payload: dict[str, object] = _fortisiem_payload(index, name, severity, tenant)
    elif product == "FortiEDR":
        name = FORTIEDR_PROCESSES[index % 5]
        payload = _fortiedr_payload(index, name, severity)
    else:
        name = SENTINELONE_THREATS[index % 5]
        payload = _sentinelone_payload(index, name, severity)

    return SecurityAlert(
        source_alert_id=alert_id(index),
        tenant_id=tenant,
        source_product=product,
        detection_name=name,
        severity=severity,
        event_at=event_at,
        triage_status=triage,
        resolution=resolution,
        linked_case_id=linked_case_id,
        payload=payload,
    )


def generate_security_alerts(count: int = 240) -> list[SecurityAlert]:
    """Return *count* deterministic security alerts across the three products."""
    return [_build_alert(i) for i in range(count)]
