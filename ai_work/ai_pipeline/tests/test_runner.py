import json
from pathlib import Path

from ai_work.ai_pipeline.runner import process_incident


ROOT = Path(__file__).resolve().parents[2]
SAMPLE_INCIDENT = ROOT / "examples" / "incident-CrashLoopBackOff.json"


def test_runner_builds_proposal_without_approving_or_executing():
    result = process_incident(str(SAMPLE_INCIDENT), diagnoser_name="mock")

    assert result["incident_id"]
    assert result["status"] == "AWAITING_HUMAN_APPROVAL"
    assert result["diagnosis"]["incident_id"] == result["incident_id"]
    assert result["proposal"]["incident_id"] == result["incident_id"]
    assert result["proposal"]["status"] == "PROPOSED"
    assert result["proposal"]["approval_required"] is True
    assert result["execution_performed"] is False


def test_runner_rejects_unknown_diagnoser():
    try:
        process_incident(str(SAMPLE_INCIDENT), diagnoser_name="unknown")
    except ValueError as exc:
        assert "Unsupported diagnoser" in str(exc)
    else:
        raise AssertionError("Unsupported diagnoser should be rejected")


def test_runner_rejects_missing_incident_file(tmp_path):
    missing = tmp_path / "missing.json"
    try:
        process_incident(str(missing), diagnoser_name="mock")
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("Missing incident should be rejected")
