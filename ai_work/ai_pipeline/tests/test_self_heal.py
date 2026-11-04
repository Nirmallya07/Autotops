import json
from ai_work.ai_pipeline.self_heal import process


def test_v3_defaults_to_no_execution_and_generates_report(tmp_path, monkeypatch):
    incident = {
        "incident_id":"INC-V3-1","service":"demo","namespace":"default",
        "failure_type":"CrashLoopBackOff","severity":"HIGH",
        "detected_at":"2026-11-04T00:00:00Z","status":"OPEN",
        "source":{"watcher":"watcher-v1"},
        "evidence":{"pod_status":{"name":"demo-pod","uid":"old-uid","owner_kind":"ReplicaSet",
            "phase":"CrashLoopBackOff","containers":[{"name":"app","restart_count":3}]},
            "kubernetes_events":[],"metrics":{},"logs":["Application crashed"]}
    }
    path=tmp_path/"incident.json"
    path.write_text(json.dumps(incident))
    class NeverExecute:
        def execute(self, handoff):
            raise AssertionError("default policy must not execute")
    result=process(str(path), memory_path=str(tmp_path/"memory.db"),
                   report_dir=str(tmp_path/"reports"), executor=NeverExecute())
    assert result["execution_performed"] is False
    assert result["status"] == "AWAITING_HUMAN_APPROVAL"
    assert (tmp_path/"reports"/"INC-V3-1.json").exists()
    assert (tmp_path/"reports"/"INC-V3-1.txt").exists()
