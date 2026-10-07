import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "watcher"))

import pytest
from jsonschema import ValidationError

import rules
from incident import create_incident


def pod(waiting=None, last_reason=None, exit_code=None, restarts=0):
    return {
        "name": "autotops-test",
        "phase": "Running",
        "containers": [{
            "name": "autotops-demo",
            "ready": waiting is None,
            "restart_count": restarts,
            "waiting_reason": waiting,
            "last_terminated_reason": last_reason,
            "last_exit_code": exit_code,
        }],
    }


EMPTY_EVIDENCE = {"pod_status": {}, "kubernetes_events": [], "metrics": {}, "logs": []}


def test_crashloop_detected():
    assert rules.check_crashloop(pod(waiting="CrashLoopBackOff")) == "HIGH"


def test_crashloop_not_detected_when_healthy():
    assert rules.check_crashloop(pod()) is None


def test_oom_detected_by_reason():
    assert rules.check_oom(pod(last_reason="OOMKilled", exit_code=137)) == "HIGH"


def test_oom_detected_by_exit_code():
    assert rules.check_oom(pod(last_reason=None, exit_code=137)) == "HIGH"


def test_oom_not_detected_for_normal_crash():
    assert rules.check_oom(pod(last_reason="Error", exit_code=1)) is None


def test_5xx_detected(monkeypatch):
    values = iter([40.0, 2.0])
    monkeypatch.setattr(rules.prom, "query", lambda q: next(values))
    sev, metrics = rules.check_5xx()
    assert sev == "HIGH"
    assert metrics["http_5xx_last_minute"] == 40.0


def test_5xx_not_detected_below_threshold(monkeypatch):
    values = iter([2.0, 1.0])
    monkeypatch.setattr(rules.prom, "query", lambda q: next(values))
    sev, _ = rules.check_5xx()
    assert sev is None


def test_5xx_not_detected_when_no_data(monkeypatch):
    monkeypatch.setattr(rules.prom, "query", lambda q: None)
    sev, _ = rules.check_5xx()
    assert sev is None


def test_incident_matches_schema():
    inc = create_incident("INC-001", "autotops-demo", "default", "OOMKilled", "HIGH", EMPTY_EVIDENCE)
    assert inc["status"] == "OPEN"
    assert inc["source"]["watcher"] == "watcher-v0"
    assert inc["incident_id"] == "INC-001"


def test_incident_rejects_unknown_failure_type():
    with pytest.raises(ValidationError):
        create_incident("INC-001", "autotops-demo", "default", "Banana", "HIGH", EMPTY_EVIDENCE)


def test_incident_rejects_missing_evidence_field():
    with pytest.raises(ValidationError):
        create_incident("INC-001", "autotops-demo", "default", "OOMKilled", "HIGH", {"logs": []})
