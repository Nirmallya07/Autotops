from typing import Any, Dict


class RemediationExecutor:
    """
    Validate an approved execution handoff without changing infrastructure.

    This implementation is deliberately dry-run only. A real executor must
    use a separately reviewed, least-privilege infrastructure adapter.
    """

    ALLOWED_ACTIONS = {"investigate", "restart", "scale", "rollback"}
    ALLOWED_RISKS = {"LOW", "MEDIUM", "HIGH"}

    def execute(self, handoff: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(handoff, dict):
            raise ValueError("Execution handoff must be a dictionary.")

        if handoff.get("status") != "READY_FOR_EXECUTION":
            raise ValueError("Only READY_FOR_EXECUTION handoffs are accepted.")

        if handoff.get("approval_required") is not True:
            raise ValueError("Explicit approval must be required.")

        approved_by = handoff.get("approved_by")
        if not isinstance(approved_by, str) or not approved_by.strip():
            raise ValueError("A non-empty approver identity is required.")

        for field in ("incident_id", "action", "target", "risk"):
            value = handoff.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Missing or invalid field: {field}")

        action = handoff["action"].strip().lower()
        if action not in self.ALLOWED_ACTIONS:
            raise ValueError(f"Unsupported remediation action: {action}")

        risk = handoff["risk"].strip().upper()
        if risk not in self.ALLOWED_RISKS:
            raise ValueError(f"Unsupported risk level: {risk}")

        return {
            "incident_id": handoff["incident_id"].strip(),
            "action": action,
            "target": handoff["target"].strip(),
            "risk": risk,
            "approved_by": approved_by.strip(),
            "status": "DRY_RUN",
            "execution_performed": False,
            "message": "Validated only; no infrastructure changes were made.",
        }
