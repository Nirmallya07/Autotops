from typing import Any, Dict, List


def _flatten_text(value: Any) -> str:
    if isinstance(value, str):
        return value.lower()
    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten_text(item) for item in value)
    return ""


class RemediationProposal:
    """Create a proposal; weak or ungrounded diagnoses default to investigation."""

    MIN_REMEDIATION_CONFIDENCE = 0.60

    def create(self, incident: Dict[str, Any], diagnosis: Dict[str, Any]) -> Dict[str, Any]:
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

        confidence = diagnosis.get("confidence", 0)
        diagnosis_evidence = diagnosis.get("evidence", [])
        recommended = str(diagnosis.get("recommended_action", "")).lower()
        insufficient = (
            isinstance(confidence, bool) or not isinstance(confidence, (int, float))
            or confidence < self.MIN_REMEDIATION_CONFIDENCE
            or not diagnosis_evidence
            or any(term in recommended for term in (
                "investigate", "collect", "inspect", "unknown", "insufficient evidence"
            ))
        )

        if insufficient:
            action = "investigate"
            reason = (
                "Diagnosis confidence or grounded evidence is insufficient for remediation. "
                "Collect and verify more evidence before selecting an infrastructure action."
            )
            risk = "LOW"
        elif failure_type == "CrashLoopBackOff":
            action = "restart_pod"
            reason = diagnosis.get("root_cause", "The application pod is repeatedly crashing.")
            risk = "MEDIUM"
        elif failure_type == "OOMKilled":
            action = "scale"
            reason = diagnosis.get("root_cause", "The application exceeded its memory limit.")
            risk = "HIGH"
        elif failure_type == "HighHTTP5xxRate":
            logs_text = _flatten_text(evidence.get("logs", []))
            if "simulated" in logs_text:
                action = "investigate"
                reason = (
                    "Logs indicate simulated HTTP errors. Verify whether the errors are intentional "
                    "before considering rollback."
                )
                risk = "LOW"
            else:
                action = "rollback"
                reason = diagnosis.get("root_cause", "The application is experiencing a high HTTP 5xx error rate.")
                risk = "HIGH"
        else:
            action = "investigate"
            reason = "Insufficient evidence to safely recommend remediation."
            risk = "HIGH"

        return {
            "incident_id": incident_id, "action": action, "target": service,
            "reason": reason, "evidence_refs": evidence_refs, "risk": risk,
            "approval_required": True, "status": "PROPOSED",
        }
