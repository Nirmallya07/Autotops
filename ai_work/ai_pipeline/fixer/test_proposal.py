from ai_work.ai_pipeline.fixer.proposal import RemediationProposal


def test_crashloop_proposal_requires_grounded_diagnosis_evidence():
    incident = {
        "incident_id": "INC-TEST-001", "service": "demo-api", "namespace": "default",
        "failure_type": "CrashLoopBackOff", "severity": "HIGH",
        "detected_at": "2026-10-08T10:00:00Z", "status": "OPEN",
        "evidence": {"pod_status": {}, "kubernetes_events": [], "metrics": {},
                    "logs": ["Application crashed"]},
    }
    diagnosis = {
        "incident_id": "INC-TEST-001",
        "root_cause": "Application pod is repeatedly crashing.",
        "evidence": [], "confidence": 0.70,
        "recommended_action": "Inspect application logs.",
    }
    proposal = RemediationProposal().create(incident, diagnosis)
    assert proposal["incident_id"] == "INC-TEST-001"
    assert proposal["action"] == "investigate"
    assert proposal["target"] == "demo-api"
    assert proposal["approval_required"] is True
    assert proposal["status"] == "PROPOSED"
