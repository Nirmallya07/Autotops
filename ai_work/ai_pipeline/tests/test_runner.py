import json
from pathlib import Path

from ai_work.ai_pipeline.runner import process_incident


ROOT = Path(__file__).resolve().parents[2]
SAMPLE_INCIDENT = ROOT / "examples" / "incident-CrashLoopBackOff.json"


class FakeHealthChecker:
    def __init__(self, status):
        self.status = status

    def assess(self, incident):
        return {
            "incident_id": incident["incident_id"],
            "status": self.status,
            "reason": "Test health assessment",
            "pod_uid": "pod-uid-1",
            "identity_verified": True,
        }


class FakeStabilityMonitor:
    def __init__(self, status):
        self.status = status

    def monitor(self, incident, initial_result=None):
        return {
            "incident_id": incident["incident_id"],
            "status": self.status,
            "reason": "Test stability assessment",
            "window_seconds": 60,
            "sample_count": 7,
            "observations": [initial_result],
        }


def test_runner_builds_proposal_without_approving_or_executing():
    result = process_incident(str(SAMPLE_INCIDENT), diagnoser_name="mock")

    assert result["incident_id"]
    assert result["status"] == "AWAITING_HUMAN_APPROVAL"
    assert result["diagnosis"]["incident_id"] == result["incident_id"]
    assert result["proposal"]["incident_id"] == result["incident_id"]
    assert result["proposal"]["status"] == "PROPOSED"
    assert result["proposal"]["approval_required"] is True
    assert result["execution_performed"] is False
    assert result["health_check"]["status"] == "UNKNOWN"


def test_runner_skips_proposal_when_pod_is_healthy():
    result = process_incident(
        str(SAMPLE_INCIDENT),
        diagnoser_name="mock",
        health_checker=FakeHealthChecker("HEALTHY_NOW"),
        stability_monitor=FakeStabilityMonitor("RECOVERED"),
    )

    assert result["status"] == "RECOVERED"
    assert result["stability_check"]["sample_count"] == 7
    assert result["proposal"] is None
    assert result["execution_performed"] is False


def test_runner_keeps_approval_gated_proposal_when_pod_is_unhealthy():
    result = process_incident(
        str(SAMPLE_INCIDENT),
        diagnoser_name="mock",
        health_checker=FakeHealthChecker("UNHEALTHY"),
    )

    assert result["status"] == "AWAITING_HUMAN_APPROVAL"
    assert result["proposal"]["status"] == "PROPOSED"
    assert result["proposal"]["approval_required"] is True
    assert result["execution_performed"] is False


def test_runner_requires_review_when_original_pod_cannot_be_verified():
    result = process_incident(
        str(SAMPLE_INCIDENT),
        diagnoser_name="mock",
        health_checker=FakeHealthChecker("IDENTITY_CHANGED"),
    )

    assert result["status"] == "NEEDS_HEALTH_REVIEW"
    assert result["proposal"] is None
    assert result["execution_performed"] is False


def test_runner_keeps_proposal_visible_when_health_is_unknown():
    result = process_incident(
        str(SAMPLE_INCIDENT),
        diagnoser_name="mock",
        health_checker=FakeHealthChecker("UNKNOWN"),
    )

    assert result["status"] == "AWAITING_HUMAN_APPROVAL"
    assert result["proposal"]["approval_required"] is True
    assert "inconclusive" in result["message"]


def test_runner_keeps_proposal_when_pod_fails_during_stability_window():
    result = process_incident(
        str(SAMPLE_INCIDENT),
        diagnoser_name="mock",
        health_checker=FakeHealthChecker("HEALTHY_NOW"),
        stability_monitor=FakeStabilityMonitor("UNHEALTHY"),
    )

    assert result["status"] == "AWAITING_HUMAN_APPROVAL"
    assert result["proposal"]["approval_required"] is True
    assert result["stability_check"]["status"] == "UNHEALTHY"
    assert result["execution_performed"] is False


def test_runner_requires_review_when_stability_monitor_loses_identity():
    result = process_incident(
        str(SAMPLE_INCIDENT),
        diagnoser_name="mock",
        health_checker=FakeHealthChecker("HEALTHY_NOW"),
        stability_monitor=FakeStabilityMonitor("NEEDS_REVIEW"),
    )

    assert result["status"] == "NEEDS_HEALTH_REVIEW"
    assert result["proposal"] is None
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



def test_runner_persists_recovered_lifecycle_without_modifying_incident(tmp_path):
    lifecycle_path = tmp_path / "lifecycle" / "INC-003.json"
    original = SAMPLE_INCIDENT.read_text(encoding="utf-8")

    result = process_incident(
        str(SAMPLE_INCIDENT),
        diagnoser_name="mock",
        health_checker=FakeHealthChecker("HEALTHY_NOW"),
        stability_monitor=FakeStabilityMonitor("RECOVERED"),
        lifecycle_path=str(lifecycle_path),
    )

    lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
    assert result["status"] == "RECOVERED"
    assert lifecycle["current_status"] == "RECOVERED"
    assert [event["status"] for event in lifecycle["events"]] == [
        "OPEN", "INVESTIGATING", "RECOVERED"
    ]
    assert SAMPLE_INCIDENT.read_text(encoding="utf-8") == original


def test_runner_persists_approval_required_lifecycle(tmp_path):
    lifecycle_path = tmp_path / "lifecycle" / "INC-003.json"

    result = process_incident(
        str(SAMPLE_INCIDENT),
        diagnoser_name="mock",
        health_checker=FakeHealthChecker("UNKNOWN"),
        lifecycle_path=str(lifecycle_path),
    )

    lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
    assert result["status"] == "AWAITING_HUMAN_APPROVAL"
    assert lifecycle["current_status"] == "AWAITING_HUMAN_APPROVAL"

def test_runner_passes_selected_model_to_ollama(monkeypatch):
    from ai_work.ai_pipeline import runner

    captured = {}

    class FakeOllamaDiagnoser:
        def __init__(self, model):
            captured["model"] = model

        def diagnose(self, context):
            return {
                "incident_id": context["incident_id"],
                "root_cause": "Test diagnosis from selected Ollama model.",
                "evidence": ["Test evidence"],
                "confidence": 0.8,
                "recommended_action": "Review the test evidence.",
            }

    monkeypatch.setattr(runner, "OllamaDiagnoser", FakeOllamaDiagnoser)
    result = runner.process_incident(
        str(SAMPLE_INCIDENT),
        diagnoser_name="ollama",
        ollama_model="qwen2.5:3b",
        health_checker=FakeHealthChecker("UNKNOWN"),
    )

    assert captured["model"] == "qwen2.5:3b"
    assert result["diagnosis"]["root_cause"] == "Test diagnosis from selected Ollama model."
