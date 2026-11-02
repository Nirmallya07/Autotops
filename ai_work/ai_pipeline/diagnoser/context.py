from typing import Any, Dict


class DiagnosticContext:
    """
    Normalizes incident evidence into a structured diagnostic context.

    The context contains only evidence supplied by the incident.
    It does not collect evidence or execute infrastructure commands.
    """

    def build(self, incident: Dict[str, Any]) -> Dict[str, Any]:

        evidence = incident.get("evidence", {})

        return {
            "incident_id": incident.get("incident_id", "UNKNOWN"),
            "service": incident.get("service", "UNKNOWN"),
            "namespace": incident.get("namespace", "UNKNOWN"),
            "failure_type": incident.get("failure_type", "UNKNOWN"),
            "severity": incident.get("severity", "UNKNOWN"),
            "pod_status": evidence.get("pod_status", {}),
            "kubernetes_events": evidence.get("kubernetes_events", []),
            "metrics": evidence.get("metrics", {}),
            "logs": evidence.get("logs", []),
        }