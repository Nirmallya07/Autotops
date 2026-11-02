from ai_work.ai_pipeline.reporter.reporter import IncidentReporter


def test_incident_report():
    incident = {
        "incident_id": "INC-TEST-001",
        "service": "demo-api",
        "namespace": "default",
        "failure_type": "CrashLoopBackOff",
        "severity": "HIGH",
        "detected_at": "2026-10-08T10:00:00Z",
        "status": "OPEN",
    }

    diagnosis = {
        "incident_id": "INC-TEST-001",
        "root_cause": "Application pod is repeatedly crashing.",
        "confidence": 0.70,
        "recommended_action": "Inspect application logs.",
    }

    proposal = {
        "incident_id": "INC-TEST-001",
        "action": "restart",
        "target": "demo-api",
        "risk": "MEDIUM",
    }

    approval = {
        "status": "APPROVED",
    }

    execution = {
        "status": "SUCCESS",
    }

    recovery = {
        "status": "RECOVERED",
    }

    reporter = IncidentReporter()

    report = reporter.generate(
        incident,
        diagnosis,
        proposal,
        approval,
        execution,
        recovery,
    )

    assert report["incident_id"] == "INC-TEST-001"
    assert report["service"] == "demo-api"
    assert report["failure_type"] == "CrashLoopBackOff"
    assert report["root_cause"] == "Application pod is repeatedly crashing."
    assert report["proposed_action"] == "restart"
    assert report["approval_status"] == "APPROVED"
    assert report["execution_status"] == "SUCCESS"
    assert report["recovery_status"] == "RECOVERED"

    text_report = reporter.to_text(report)

    assert "AUTOTOPS INCIDENT REPORT" in text_report
    assert "INC-TEST-001" in text_report
    assert "demo-api" in text_report
    assert "RECOVERED" in text_report

    print("Reporter test passed!")
    print(text_report)


if __name__ == "__main__":
    test_incident_report()
