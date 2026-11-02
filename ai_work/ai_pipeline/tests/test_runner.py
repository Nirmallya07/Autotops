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
