from typing import Any, Dict, List


def _flatten_text(value: Any) -> str:
    """Collect text from nested log/evidence structures for safety checks."""
    if isinstance(value, str):
        return value.lower()

    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for item in value.values())

    if isinstance(value, (list, tuple)):
        return " ".join(_flatten_text(item) for item in value)

    return ""


class RemediationProposal:
    """
    Creates a structured remediation proposal.

    This component proposes an action but does not execute it.
    """

    def create(
        self,
        incident: Dict[str, Any],
        diagnosis: Dict[str, Any],
    ) -> Dict[str, Any]:

        failure_type = incident.get("failure_type", "UNKNOWN")
        incident_id = incident.get("incident_id", "UNKNOWN")
        service = incident.get("service", "UNKNOWN")

        evidence = incident.get("evidence", {})
        if not isinstance(evidence, dict):
            evidence = {}

        evidence_refs: List[str] = []

        if evidence.get("logs"):
            evidence_refs.append("logs")

        if evidence.get("kubernetes_events"):
            evidence_refs.append("kubernetes_events")

        if evidence.get("metrics"):
            evidence_refs.append("metrics")

        if failure_type == "CrashLoopBackOff":
            action = "restart"
            reason = diagnosis.get(
                "root_cause",
                "The application pod is repeatedly crashing.",
            )
            risk = "MEDIUM"

        elif failure_type == "OOMKilled":
            action = "scale"
            reason = diagnosis.get(
                "root_cause",
                "The application exceeded its memory limit.",
            )
            risk = "HIGH"

        elif failure_type == "HighHTTP5xxRate":
            logs_text = _flatten_text(evidence.get("logs", []))

            if "simulated" in logs_text:
                action = "investigate"
                reason = (
                    "Logs indicate simulated HTTP errors. Verify whether "
                    "the errors are intentional before considering rollback."
                )
                risk = "LOW"
            else:
                action = "rollback"
                reason = diagnosis.get(
                    "root_cause",
                    "The application is experiencing a high HTTP 5xx error rate.",
                )
                risk = "HIGH"

        else:
            action = "investigate"
            reason = "Insufficient evidence to safely recommend remediation."
            risk = "HIGH"

        return {
            "incident_id": incident_id,
            "action": action,
            "target": service,
            "reason": reason,
            "evidence_refs": evidence_refs,
            "risk": risk,
            "approval_required": True,
            "status": "PROPOSED",
        }
