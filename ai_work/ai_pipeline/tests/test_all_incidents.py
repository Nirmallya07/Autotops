from pathlib import Path

from ai_work.ai_pipeline.incident_loader import IncidentLoader
from ai_work.ai_pipeline.diagnoser.context import DiagnosticContext
from ai_work.ai_pipeline.diagnoser.ollama import OllamaDiagnoser
from ai_work.ai_pipeline.diagnoser.validator import DiagnosisValidator
from ai_work.ai_pipeline.fixer.proposal import RemediationProposal


EXAMPLES = [
    (
        str(
            Path(__file__).resolve().parents[2]
            / "examples"
            / "incident-CrashLoopBackOff.json"
        ),
        "CrashLoopBackOff",
        "restart",
    ),
    (
        str(
            Path(__file__).resolve().parents[2]
            / "examples"
            / "incident-HighHTTP5xxRate.json"
        ),
        "HighHTTP5xxRate",
        "investigate",
    ),
    (
        str(
            Path(__file__).resolve().parents[2]
            / "examples"
            / "incident-OOMKilled.json"
        ),
        "OOMKilled",
        "scale",
    ),
]


def test_all_incidents():
    loader = IncidentLoader()
    context_builder = DiagnosticContext()
    diagnoser = OllamaDiagnoser()
    validator = DiagnosisValidator()
    fixer = RemediationProposal()

    for file_path, expected_type, expected_action in EXAMPLES:
        print("\n" + "=" * 55)
        print(f"Testing: {expected_type}")
        print("=" * 55)

        incident = loader.load(file_path)

        assert incident["failure_type"] == expected_type, (
            f"Unexpected failure type in {file_path}"
        )

        context = context_builder.build(incident)
        diagnosis = diagnoser.diagnose(context)
        validator.validate(diagnosis)

        assert diagnosis["incident_id"] == incident["incident_id"]
        assert isinstance(diagnosis["root_cause"], str)
        assert diagnosis["root_cause"].strip()
        assert isinstance(diagnosis["evidence"], list)
        assert 0 <= diagnosis["confidence"] <= 1
        assert isinstance(diagnosis["recommended_action"], str)
        assert diagnosis["recommended_action"].strip()

        proposal = fixer.create(incident, diagnosis)

        assert proposal["action"] == expected_action, (
            f"Expected {expected_action}, got {proposal['action']}"
        )
        assert proposal["status"] == "PROPOSED"
        assert proposal["approval_required"] is True

        print("Root cause:", diagnosis["root_cause"])
        print("Confidence:", diagnosis["confidence"])
        print("Recommended action:", diagnosis["recommended_action"])
        print("Proposed remediation:", proposal["action"])
        print("Result: PASS")

    print("\nALL THREE INCIDENT TESTS PASSED")


if __name__ == "__main__":
    test_all_incidents()
