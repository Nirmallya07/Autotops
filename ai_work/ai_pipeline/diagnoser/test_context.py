from ai_work.ai_pipeline.diagnoser.context import DiagnosticContext


def test_diagnostic_context():

    incident = {
        "incident_id": "INC-TEST-003",
        "service": "demo-api",
        "namespace": "default",
        "failure_type": "CrashLoopBackOff",
        "severity": "HIGH",
        "detected_at": "2026-10-08T10:00:00Z",
        "status": "OPEN",
        "evidence": {
            "pod_status": {
                "phase": "CrashLoopBackOff",
                "restart_count": 5
            },
            "kubernetes_events": [
                {
                    "reason": "BackOff",
                    "message": "Back-off restarting failed container"
                }
            ],
            "metrics": {
                "restart_count": 5
            },
            "logs": [
                "Application crashed during startup"
            ]
        }
    }

    context_builder = DiagnosticContext()

    context = context_builder.build(incident)

    assert context["incident_id"] == "INC-TEST-003"
    assert context["service"] == "demo-api"
    assert context["failure_type"] == "CrashLoopBackOff"

    assert context["pod_status"]["phase"] == "CrashLoopBackOff"
    assert len(context["kubernetes_events"]) == 1
    assert context["metrics"]["restart_count"] == 5
    assert len(context["logs"]) == 1

    print("Diagnostic Context test passed!")
    print("\nDiagnostic Context:")
    print(context)


if __name__ == "__main__":
    test_diagnostic_context()
