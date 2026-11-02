from typing import Any, Dict


class DiagnosisValidator:
    """
    Validates the structured output produced by a diagnoser.

    This protects the remediation pipeline from malformed
    or incomplete LLM responses.
    """

    def validate(self, diagnosis: Dict[str, Any]) -> Dict[str, Any]:

        required_fields = [
            "incident_id",
            "root_cause",
            "evidence",
            "confidence",
            "recommended_action",
        ]

        for field in required_fields:
            if field not in diagnosis:
                raise ValueError(
                    f"Invalid diagnosis: missing field '{field}'"
                )

        if not isinstance(diagnosis["incident_id"], str):
            raise ValueError("incident_id must be a string")

        if not diagnosis["incident_id"]:
            raise ValueError("incident_id cannot be empty")

        if not isinstance(diagnosis["root_cause"], str):
            raise ValueError("root_cause must be a string")

        if not diagnosis["root_cause"]:
            raise ValueError("root_cause cannot be empty")

        if not isinstance(diagnosis["evidence"], list):
            raise ValueError("evidence must be a list")

        confidence = diagnosis["confidence"]

        if not isinstance(confidence, (int, float)):
            raise ValueError("confidence must be a number")

        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")

        if not isinstance(
            diagnosis["recommended_action"],
            str
        ):
            raise ValueError(
                "recommended_action must be a string"
            )

        if not diagnosis["recommended_action"]:
            raise ValueError(
                "recommended_action cannot be empty"
            )

        return diagnosis