import re
from typing import Any, Dict, Optional


class DiagnosisValidator:
    """Validate diagnosis structure and keep cited evidence grounded in context."""

    _GENERIC_LOG_PATTERNS = (
        re.compile(r"development server.*do not use it in a production", re.I),
        re.compile(r"serving flask app", re.I),
        re.compile(r"debug mode: off", re.I),
        re.compile(r"running on (all addresses|http://|https://)", re.I),
        re.compile(r"press ctrl\+c to quit", re.I),
    )
    _FAILURE_LOG_PATTERN = re.compile(
        r"\b(error|exception|traceback|fatal|failed|failure|oomkilled|"
        r"out of memory|killed|terminat(?:ed|ing)|crash(?:ed)?)\b", re.I,
    )
    _UNSUPPORTED_CAUSE_PATTERN = re.compile(
        r"\b(caused by|due to|because of|encountered an error|"
        r"application error|root cause is)\b", re.I,
    )
    _STRUCTURED_K8S_EVIDENCE = re.compile(
        r"^(last_exit_code|last_terminated_reason|restart_count|phase):\s*\S+$", re.I
    )

    def validate(self, diagnosis: Dict[str, Any],
                 context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        required = ("incident_id", "root_cause", "evidence", "confidence", "recommended_action")
        for field in required:
            if field not in diagnosis:
                raise ValueError(f"Invalid diagnosis: missing field '{field}'")
        if not isinstance(diagnosis["incident_id"], str) or not diagnosis["incident_id"]:
            raise ValueError("incident_id must be a non-empty string")
        if not isinstance(diagnosis["root_cause"], str) or not diagnosis["root_cause"]:
            raise ValueError("root_cause must be a non-empty string")
        if not isinstance(diagnosis["evidence"], list):
            raise ValueError("evidence must be a list")
        if any(not isinstance(item, str) for item in diagnosis["evidence"]):
            raise ValueError("each evidence item must be a string")
        confidence = diagnosis["confidence"]
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise ValueError("confidence must be a number")
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if not isinstance(diagnosis["recommended_action"], str) or not diagnosis["recommended_action"]:
            raise ValueError("recommended_action must be a non-empty string")

        if context is not None:
            logs = []
            for field in ("current_logs", "previous_logs", "logs"):
                value = context.get(field, [])
                if isinstance(value, list):
                    logs.extend(str(line) for line in value)
            allowed_evidence = set(logs)
            events = context.get("kubernetes_events", [])
            if isinstance(events, list):
                allowed_evidence.update(item if isinstance(item, str) else str(item) for item in events)
            metrics = context.get("metrics", {})
            if isinstance(metrics, dict):
                allowed_evidence.update(f"{key}: {value}" for key, value in metrics.items())
                allowed_evidence.update(str(value) for value in metrics.values())
            grounded = []
            for item in diagnosis["evidence"]:
                if item in allowed_evidence:
                    if not any(pattern.search(item) for pattern in self._GENERIC_LOG_PATTERNS):
                        grounded.append(item)
                elif self._STRUCTURED_K8S_EVIDENCE.match(item):
                    grounded.append(item)
            diagnosis["evidence"] = list(dict.fromkeys(grounded))

            meaningful_failure_logs = [
                line for line in logs
                if not any(p.search(line) for p in self._GENERIC_LOG_PATTERNS)
                and self._FAILURE_LOG_PATTERN.search(line)
            ]
            if not meaningful_failure_logs:
                diagnosis["confidence"] = min(float(diagnosis["confidence"]), 0.35)
                if self._UNSUPPORTED_CAUSE_PATTERN.search(diagnosis["root_cause"]):
                    diagnosis["root_cause"] = (
                        "The container terminated unsuccessfully, but the exact "
                        "application-level root cause cannot be determined from the supplied evidence."
                    )
                diagnosis["recommended_action"] = (
                    "Collect and inspect application logs from the failing container, "
                    "including previous-container logs, and correlate them with Kubernetes termination details."
                )
            if not diagnosis["evidence"]:
                diagnosis["confidence"] = min(float(diagnosis["confidence"]), 0.35)
                diagnosis["recommended_action"] = (
                    "Investigate and collect verifiable application logs and Kubernetes evidence "
                    "before selecting a remediation."
                )
        return diagnosis
