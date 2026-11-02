from pathlib import Path

from ai_work.ai_pipeline.incident_loader import IncidentLoader
from ai_work.ai_pipeline.diagnoser.context import DiagnosticContext
from ai_work.ai_pipeline.diagnoser.mock import MockDiagnoser
from ai_work.ai_pipeline.diagnoser.validator import DiagnosisValidator
from ai_work.ai_pipeline.fixer.proposal import RemediationProposal


EXAMPLES = [
    (
        str(Path(__file__).resolve().parents[2] / "examples" / "incident-CrashLoopBackOff.json"),
        "CrashLoopBackOff",
        "restart",
    ),
    (
        str(Path(__file__).resolve().parents[2] / "examples" / "incident-HighHTTP5xxRate.json"),
        "HighHTTP5xxRate",
        "investigate",
    ),
    (
        str(Path(__file__).resolve().parents[2] / "examples" / "incident-OOMKilled.json"),
        "OOMKilled",
        "scale",
    ),
]


def test_all_incidents():
    loader = IncidentLoader()
    context_builder = DiagnosticContext()
    diagnoser = MockDiagnoser()
    validator = DiagnosisValidator()
    fixer = RemediationProposal()

    for file_path, expected_type, expected_action in EXAMPLES:
        incident = loader.load(file_path)
        assert incident["failure_type"] == expected_type

        context = context_builder.build(incident)
        diagnosis = validator.validate(diagnoser.diagnose(context))
        assert diagnosis["incident_id"] == incident["incident_id"]
        assert isinstance(diagnosis["root_cause"], str)
        assert diagnosis["root_cause"].strip()
        assert isinstance(diagnosis["evidence"], list)
        assert 0 <= diagnosis["confidence"] <= 1
        assert diagnosis["recommended_action"].strip()

        proposal = fixer.create(incident, diagnosis)
        assert proposal["action"] == expected_action
        assert proposal["status"] == "PROPOSED"
        assert proposal["approval_required"] is True
