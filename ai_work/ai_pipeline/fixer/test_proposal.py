from ai_work.ai_pipeline.fixer.proposal import RemediationProposal


def test_crashloop_proposal():
    incident = {
        "incident_id": "INC-TEST-001",
        "service": "demo-api",
        "namespace": "default",
        "failure_type": "CrashLoopBackOff",
        "severity": "HIGH",
        "detected_at": "2026-10-08T10:00:00Z",
        "status": "OPEN",
        "evidence": {
            "pod_status": {},
            "kubernetes_events": [],
            "metrics": {},
            "logs": ["Application crashed"]
        }
    }

    diagnosis = {
        "incident_id": "INC-TEST-001",
        "root_cause": "Application pod is repeatedly crashing.",
        "evidence": [],
        "confidence": 0.70,
        "recommended_action": "Inspect application logs."
    }

    fixer = RemediationProposal()
    proposal = fixer.create(incident, diagnosis)

    assert proposal["incident_id"] == "INC-TEST-001"
    assert proposal["action"] == "restart"
    assert proposal["target"] == "demo-api"
    assert proposal["approval_required"] is True
    assert proposal["status"] == "PROPOSED"

    print("Remediation proposal test passed!")
    print(proposal)


if __name__ == "__main__":
    test_crashloop_proposal()
