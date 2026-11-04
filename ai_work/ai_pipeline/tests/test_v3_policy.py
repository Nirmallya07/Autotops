import pytest
from ai_work.ai_pipeline.fixer.policy import RemediationPolicy
from ai_work.ai_pipeline.fixer.orchestrator import RemediationOrchestrator
from ai_work.ai_pipeline.memory.incident_store import IncidentMemory


def proposal(action="restart_pod"):
    return {"incident_id":"INC-1","action":action,"target":"demo","risk":"LOW"}


def test_policy_fails_closed_by_default():
    decision = RemediationPolicy().evaluate(proposal(), {
        "pod_status":{"name":"p","uid":"u","owner_kind":"ReplicaSet"}})
    assert decision.decision == "HUMAN_APPROVAL"
    assert decision.approval_required


def test_policy_rejects_missing_identity_even_when_allowlisted():
    decision = RemediationPolicy(auto_actions={"restart_pod"}).evaluate(
        proposal(), {"pod_status":{"name":"p"}})
    assert decision.decision == "HUMAN_APPROVAL"


def test_policy_requires_controller_managed_pod():
    decision = RemediationPolicy(auto_actions={"restart_pod"}).evaluate(
        proposal(), {"pod_status":{"name":"p","uid":"u","owner_kind":"Pod"}})
    assert decision.decision == "HUMAN_APPROVAL"


def test_policy_enforces_attempt_cap():
    decision = RemediationPolicy(auto_actions={"restart_pod"}, max_auto_attempts=1).evaluate(
        proposal(), {"pod_status":{"name":"p","uid":"u","owner_kind":"ReplicaSet"},
                     "auto_remediation_attempts":1})
    assert decision.decision == "ESCALATE"


def test_high_impact_action_never_auto_approved():
    decision = RemediationPolicy(auto_actions={"rollback"}).evaluate(
        proposal("rollback"), {})
    assert decision.decision == "HUMAN_APPROVAL"


def test_orchestrator_does_not_execute_without_policy_approval():
    class NeverCalled:
        def execute(self, handoff):
            raise AssertionError("executor must not be called")
    result = RemediationOrchestrator(executor=NeverCalled()).run(
        proposal(), {"pod_status":{"name":"p","uid":"u","owner_kind":"ReplicaSet"}})
    assert result["status"] == "HUMAN_APPROVAL"
    assert result["execution_performed"] is False


def test_incident_memory_only_remembers_verified_outcomes(tmp_path):
    memory = IncidentMemory(tmp_path / "memory.db")
    inc = {"incident_id":"INC-1","service":"demo","failure_type":"CrashLoopBackOff",
           "evidence":{"logs":["database connection refused"]}}
    with pytest.raises(ValueError):
        memory.remember(inc, {"root_cause":"x"}, {"action":"restart"}, {"status":"FAILED"})
    memory.remember(inc, {"root_cause":"database unavailable","evidence":["connection refused"]},
                    {"action":"restart_pod"}, {"status":"RECOVERED"})
    matches = memory.retrieve({"incident_id":"INC-2","service":"demo",
        "failure_type":"CrashLoopBackOff","evidence":{"logs":["database connection refused"]}})
    assert matches and matches[0]["incident_id"] == "INC-1"
