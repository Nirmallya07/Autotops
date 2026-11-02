import sys
import pathlib
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "watcher"))

import pytest
from jsonschema import ValidationError

import rules
import main as watcher_main
from incident import create_incident


def pod(waiting=None, last_reason=None, exit_code=None, restarts=0, last_at=None):
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
            "last_terminated_at": last_at,
        }],
    }


EMPTY_EVIDENCE = {"pod_status": {}, "kubernetes_events": [], "metrics": {}, "logs": []}


def test_crashloop_detected():
    assert rules.check_crashloop(pod(waiting="CrashLoopBackOff")) == "HIGH"


def test_crashloop_not_detected_when_healthy():
    assert rules.check_crashloop(pod()) is None

def test_fresh_kubernetes_backoff_event_detected():
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    events = [{
        "reason": "BackOff",
        "message": "Back-off restarting failed container autotops-demo",
        "last_timestamp": now.isoformat(),
    }]
    assert rules.check_crashloop(pod(restarts=2), events, now=now) == "HIGH"


def test_stale_kubernetes_backoff_event_ignored():
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    events = [{
        "reason": "BackOff",
        "message": "Back-off restarting failed container autotops-demo",
        "last_timestamp": (now - timedelta(minutes=10)).isoformat(),
    }]
    assert rules.check_crashloop(pod(restarts=2), events, now=now) is None


def test_unrelated_backoff_event_ignored():
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    events = [{
        "reason": "BackOff",
        "message": "Image pull back-off",
        "last_timestamp": now.isoformat(),
    }]
    assert rules.check_crashloop(pod(restarts=2), events, now=now) is None


def test_recent_oom_detected_by_reason():
    now = datetime.now(timezone.utc)
    finished = (now - timedelta(seconds=10)).isoformat()
    assert rules.check_oom(pod(last_reason="OOMKilled", exit_code=137, last_at=finished), now=now) == "HIGH"


def test_stale_oom_is_ignored():
    now = datetime.now(timezone.utc)
    finished = (now - timedelta(minutes=10)).isoformat()
    assert rules.check_oom(pod(last_reason="OOMKilled", exit_code=137, last_at=finished), now=now) is None


def test_oom_without_timestamp_is_ignored():
    assert rules.check_oom(pod(last_reason="OOMKilled", exit_code=137)) is None


def test_exit_code_137_without_oom_reason_is_ignored():
    now = datetime.now(timezone.utc)
    assert rules.check_oom(pod(last_reason=None, exit_code=137, last_at=now.isoformat()), now=now) is None


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



class FakePod:
    class Metadata:
        name = "autotops-test"

    metadata = Metadata()


def configure_emit_test(monkeypatch, tmp_path, now):
    monkeypatch.setattr(watcher_main, "OUT_DIR", tmp_path)
    monkeypatch.setattr(watcher_main.time, "time", lambda: now)
    monkeypatch.setattr(watcher_main.k8s, "get_events", lambda namespace, name: [])
    monkeypatch.setattr(
        watcher_main.k8s,
        "get_log_evidence",
        lambda namespace, name, **kwargs: {"logs": [], "current_logs": [], "previous_logs": []},
    )


def test_emit_suppresses_same_oom_signature_within_freshness_window(monkeypatch, tmp_path):
    now = 1_000_000.0
    configure_emit_test(monkeypatch, tmp_path, now)
    active = {}
    status = pod(last_reason="OOMKilled", exit_code=137)
    key = ("OOMKilled", "pod-uid-1", ("2026-11-03T00:00:00+00:00",))

    assert watcher_main.emit(key, "OOMKilled", "HIGH", FakePod(), status, {}, active)
    assert not watcher_main.emit(key, "OOMKilled", "HIGH", FakePod(), status, {}, active)
    assert len(list(tmp_path.glob("INC-*.json"))) == 1


def test_emit_allows_new_oom_signature(monkeypatch, tmp_path):
    now = 1_000_000.0
    configure_emit_test(monkeypatch, tmp_path, now)
    active = {}
    status = pod(last_reason="OOMKilled", exit_code=137)

    first = ("OOMKilled", "pod-uid-1", ("2026-11-03T00:00:00+00:00",))
    second = ("OOMKilled", "pod-uid-1", ("2026-11-03T00:01:00+00:00",))

    assert watcher_main.emit(first, "OOMKilled", "HIGH", FakePod(), status, {}, active)
    assert watcher_main.emit(second, "OOMKilled", "HIGH", FakePod(), status, {}, active)
    assert len(list(tmp_path.glob("INC-*.json"))) == 2


def test_crashloop_keeps_configured_cooldown(monkeypatch, tmp_path):
    now = 1_000_000.0
    configure_emit_test(monkeypatch, tmp_path, now)
    active = {}
    status = pod(waiting="CrashLoopBackOff", restarts=2)
    key = ("CrashLoopBackOff", "pod-uid-1")

    assert watcher_main.emit(key, "CrashLoopBackOff", "HIGH", FakePod(), status, {}, active)
    monkeypatch.setattr(watcher_main.time, "time", lambda: now + watcher_main.COOLDOWN - 1)
    assert not watcher_main.emit(key, "CrashLoopBackOff", "HIGH", FakePod(), status, {}, active)
    assert len(list(tmp_path.glob("INC-*.json"))) == 1


def test_emit_preserves_incident_when_event_and_log_collection_fail(monkeypatch, tmp_path):
    now = 2_000_000.0
    configure_emit_test(monkeypatch, tmp_path, now)

    def fail_logs(namespace, name, **kwargs):
        raise RuntimeError("Kubernetes API unavailable")

    monkeypatch.setattr(watcher_main.k8s, "get_log_evidence", fail_logs)
    monkeypatch.setattr(
        watcher_main.k8s, "get_events",
        lambda namespace, name: (_ for _ in ()).throw(PermissionError("forbidden")),
    )
    active = {}
    status = pod(waiting="CrashLoopBackOff", restarts=2)

    assert watcher_main.emit(
        ("CrashLoopBackOff", "pod-uid-2"),
        "CrashLoopBackOff", "HIGH", FakePod(), status, {}, active,
    )
    incident = __import__("json").loads(
        next(tmp_path.glob("INC-*.json")).read_text()
    )
    evidence = incident["evidence"]
    assert evidence["event_collection"]["status"] == "error"
    assert evidence["event_collection"]["error"]["type"] == "PermissionError"
    assert evidence["log_collection"]["status"] == "error"
    assert evidence["logs"] == []
