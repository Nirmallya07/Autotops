import re
from typing import Any, Dict, Optional


class DiagnosisValidator:
    """
    Validates diagnoser output and conservatively downgrades unsupported
    root-cause claims when the supplied application logs contain no
    identifiable failure message.
    """

    _GENERIC_LOG_PATTERNS = (
        re.compile(r"development server.*do not use it in a production", re.I),
        re.compile(r"serving flask app", re.I),
        re.compile(r"debug mode: off", re.I),
        re.compile(r"running on (all addresses|http://|https://)", re.I),
        re.compile(r"press ctrl\+c to quit", re.I),
    )
    _FAILURE_LOG_PATTERN = re.compile(
        r"\b(error|exception|traceback|fatal|failed|failure|oomkilled|"
        r"out of memory|killed|terminat(?:ed|ing)|crash(?:ed)?)\b",
        re.I,
    )
    _UNSUPPORTED_CAUSE_PATTERN = re.compile(
        r"\b(caused by|due to|because of|encountered an error|"
        r"application error|root cause is)\b",
        re.I,
    )

    def validate(
        self,
        diagnosis: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        required_fields = [
            "incident_id", "root_cause", "evidence", "confidence",
            "recommended_action",
        ]
        for field in required_fields:
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

        # Only apply evidence-grounding safeguards when incident context is
        # available. Legacy callers retain the original structural validation.
        if context is not None:
            logs = []
            for field in ("current_logs", "previous_logs", "logs"):
                value = context.get(field, [])
                if isinstance(value, list):
                    logs.extend(str(line) for line in value)

            meaningful_failure_logs = [
                line for line in logs
                if not any(pattern.search(line) for pattern in self._GENERIC_LOG_PATTERNS)
                and self._FAILURE_LOG_PATTERN.search(line)
            ]
            diagnosis_evidence = " ".join(diagnosis["evidence"])
            root_cause = diagnosis["root_cause"]

            # An exit code / Kubernetes Error state is an observation, not
            # an application-level explanation. If logs contain no specific
            # failure signal, do not allow a confident causal claim.
            if (
                not meaningful_failure_logs
                and self._UNSUPPORTED_CAUSE_PATTERN.search(root_cause)
            ):
                diagnosis["root_cause"] = (
                    "The container terminated unsuccessfully, but the exact "
                    "application-level root cause cannot be determined from "
                    "the supplied evidence."
                )
                diagnosis["confidence"] = min(float(confidence), 0.35)
                diagnosis["recommended_action"] = (
                    "Collect and inspect application logs from the failing "
                    "container, including previous-container logs, and "
                    "correlate them with Kubernetes termination details."
                )
                # Remove generic startup/runtime warnings from the cited
                # evidence; retain only factual, non-generic observations.
                diagnosis["evidence"] = [
                    item for item in diagnosis["evidence"]
                    if not any(pattern.search(item) for pattern in self._GENERIC_LOG_PATTERNS)
                ]

        return diagnosis
