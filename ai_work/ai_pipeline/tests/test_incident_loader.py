import json
from ai_work.ai_pipeline.incident_loader import IncidentLoader


def test_incident_loader(tmp_path):
    incident = {"incident_id":"INC-TEST-002","service":"demo-api","namespace":"default","failure_type":"CrashLoopBackOff","severity":"HIGH","detected_at":"2026-10-08T10:00:00Z","status":"OPEN","source":{"watcher":"watcher-v0"},"evidence":{"pod_status":{"phase":"CrashLoopBackOff"},"kubernetes_events":[],"metrics":{},"logs":[]}}
    path = tmp_path / "incident.json"
    path.write_text(json.dumps(incident), encoding="utf-8")
    loaded = IncidentLoader().load(str(path))
    assert loaded["incident_id"] == "INC-TEST-002"
    assert loaded["service"] == "demo-api"
    assert loaded["failure_type"] == "CrashLoopBackOff"
    assert loaded["severity"] == "HIGH"
