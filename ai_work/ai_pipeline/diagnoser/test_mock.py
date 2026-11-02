from .mock import MockDiagnoser


def test_crashloop_diagnosis():
    incident = {
        "incident_id": "INC-TEST-001",
        "service": "demo-api",
        "namespace": "default",
        "failure_type": "CrashLoopBackOff",
        "severity": "HIGH",
        "detected_at": "2026-10-08T10:00:00Z",
        "status": "OPEN",
        "source": {
            "watcher": "watcher-v0"
        },
        "evidence": {
            "pod_status": {
                "phase": "CrashLoopBackOff"
            },
            "kubernetes_events": [],
            "metrics": {},
            "logs": []
        }
    }

    diagnoser = MockDiagnoser()
    result = diagnoser.diagnose(incident)

    assert result["incident_id"] == "INC-TEST-001"
    assert result["root_cause"] != ""
    assert result["recommended_action"] != ""
    assert 0 <= result["confidence"] <= 1

    print("Diagnosis test passed!")
    print(result)


if __name__ == "__main__":
    test_crashloop_diagnosis()