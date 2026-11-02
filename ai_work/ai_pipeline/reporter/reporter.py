from typing import Any, Dict


class IncidentReporter:
    """
    Generates a simple deterministic incident report
    from the structured AutoTops incident lifecycle.
    """

    def generate(
        self,
        incident: Dict[str, Any],
        diagnosis: Dict[str, Any],
        proposal: Dict[str, Any],
        approval: Dict[str, Any],
        execution: Dict[str, Any],
        recovery: Dict[str, Any],
    ) -> Dict[str, Any]:

        report = {
            "incident_id": incident.get("incident_id", "UNKNOWN"),
            "service": incident.get("service", "UNKNOWN"),
            "namespace": incident.get("namespace", "UNKNOWN"),
            "failure_type": incident.get("failure_type", "UNKNOWN"),
            "severity": incident.get("severity", "UNKNOWN"),
            "detected_at": incident.get("detected_at", "UNKNOWN"),
            "status": incident.get("status", "UNKNOWN"),

            "root_cause": diagnosis.get(
                "root_cause",
                "Not determined"
            ),

            "confidence": diagnosis.get(
                "confidence",
                0.0
            ),

            "recommended_action": diagnosis.get(
                "recommended_action",
                "Not available"
            ),

            "proposed_action": proposal.get(
                "action",
                "Not proposed"
            ),

            "target": proposal.get(
                "target",
                "Not specified"
            ),

            "risk": proposal.get(
                "risk",
                "UNKNOWN"
            ),

            "approval_status": approval.get(
                "status",
                "UNKNOWN"
            ),

            "execution_status": execution.get(
                "status",
                "UNKNOWN"
            ),

            "recovery_status": recovery.get(
                "status",
                "UNKNOWN"
            ),
        }

        return report

    def to_text(self, report: Dict[str, Any]) -> str:
        """
        Convert the structured report into a beginner-friendly
        human-readable incident report.
        """

        return f"""
========================================
          AUTOTOPS INCIDENT REPORT
========================================

Incident ID       : {report["incident_id"]}
Service           : {report["service"]}
Namespace         : {report["namespace"]}
Failure Type      : {report["failure_type"]}
Severity          : {report["severity"]}
Detected At       : {report["detected_at"]}

--------------- DIAGNOSIS --------------

Root Cause        : {report["root_cause"]}
Confidence        : {report["confidence"]}
Recommended Fix   : {report["recommended_action"]}

----------- REMEDIATION ----------------

Proposed Action   : {report["proposed_action"]}
Target            : {report["target"]}
Risk              : {report["risk"]}
Approval Status   : {report["approval_status"]}

------------- EXECUTION ----------------

Execution Status  : {report["execution_status"]}

-------------- RECOVERY ----------------

Recovery Status   : {report["recovery_status"]}

========================================
"""