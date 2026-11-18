from ai_work.ai_pipeline.diagnoser.validator import DiagnosisValidator
from ai_work.ai_pipeline.fixer.proposal import RemediationProposal


def diagnosis(evidence, confidence=0.95, action="Restart the pod"):
    return {
        "incident_id": "INC-SAFETY-1",
        "root_cause": "The application crashed.",
        "evidence": evidence,
        "confidence": confidence,
        "recommended_action": action,
    }


def test_validator_removes_hallucinated_evidence_and_caps_confidence():
    line = "Synthetic test: pod is healthy."
    context = {
        "logs": [line], "current_logs": [line], "previous_logs": [],
        "kubernetes_events": [], "metrics": {},
    }
    result = DiagnosisValidator().validate(
        diagnosis([
            line,
            "The application process terminated with an error.",
            "The application logs explicitly describe the action that led to termination.",
        ]), context
    )
    assert result["evidence"] == [line]
    assert result["confidence"] == 0.35
    assert "collect" in result["recommended_action"].lower()


def test_validator_caps_confidence_when_no_evidence_is_grounded():
    context = {"logs": ["normal startup"], "current_logs": ["normal startup"],
               "previous_logs": [], "kubernetes_events": [], "metrics": {}}
    result = DiagnosisValidator().validate(
        diagnosis(["invented event"], confidence=0.9), context
    )
    assert result["evidence"] == []
    assert result["confidence"] == 0.35


def test_proposal_investigates_low_confidence_diagnosis():
    incident = {"incident_id": "INC-1", "service": "demo",
                "failure_type": "CrashLoopBackOff", "evidence": {"logs": ["x"]}}
    result = RemediationProposal().create(
        incident, diagnosis(["real log"], confidence=0.35,
                            action="Collect and inspect previous container logs")
    )
    assert result["action"] == "investigate"


def test_proposal_investigates_empty_grounded_evidence():
    incident = {"incident_id": "INC-1", "service": "demo",
                "failure_type": "CrashLoopBackOff", "evidence": {"logs": ["x"]}}
    result = RemediationProposal().create(
        incident, diagnosis([], confidence=0.95, action="Restart the pod")
    )
    assert result["action"] == "investigate"


def test_proposal_allows_remediation_only_with_confident_grounded_evidence():
    incident = {"incident_id": "INC-1", "service": "demo",
                "failure_type": "CrashLoopBackOff", "evidence": {"logs": ["app crashed"]}}
    result = RemediationProposal().create(
        incident, diagnosis(["app crashed"], confidence=0.9)
    )
    assert result["action"] == "restart_pod"
