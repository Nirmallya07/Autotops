import pytest

from ai_work.ai_pipeline.fixer.execution_handoff import ExecutionHandoff


def valid_proposal():
    return {
        "incident_id": "INC-TEST-001",
        "action": "restart",
        "target": "demo-api",
        "reason": "Application pod is repeatedly crashing.",
        "evidence_refs": ["logs"],
        "risk": "MEDIUM",
        "approval_required": True,
        "status": "APPROVED",
        "approved_by": "human",
    }


def test_execution_handoff():
    proposal = valid_proposal()
    handoff = ExecutionHandoff().create(proposal)

    assert handoff["incident_id"] == "INC-TEST-001"
    assert handoff["action"] == "restart"
    assert handoff["target"] == "demo-api"
    assert handoff["risk"] == "MEDIUM"
    assert handoff["approved_by"] == "human"
    assert handoff["status"] == "READY_FOR_EXECUTION"


def test_rejects_proposed_status():
    proposal = valid_proposal()
    proposal["status"] = "PROPOSED"

    with pytest.raises(ValueError, match="Only APPROVED"):
        ExecutionHandoff().create(proposal)


def test_rejects_missing_approval_requirement():
    proposal = valid_proposal()
    proposal["approval_required"] = False

    with pytest.raises(ValueError, match="approval requirement"):
        ExecutionHandoff().create(proposal)


@pytest.mark.parametrize("approver", ["", "   ", None, 123])
def test_rejects_invalid_approver(approver):
    proposal = valid_proposal()
    proposal["approved_by"] = approver

    with pytest.raises(ValueError, match="approver identity"):
        ExecutionHandoff().create(proposal)


@pytest.mark.parametrize("field", ["incident_id", "action", "target", "risk"])
def test_rejects_missing_required_fields(field):
    proposal = valid_proposal()
    proposal[field] = ""

    with pytest.raises(ValueError, match="Missing or invalid"):
        ExecutionHandoff().create(proposal)


def test_handoff_does_not_modify_original_proposal():
    proposal = valid_proposal()
    original = proposal.copy()

    ExecutionHandoff().create(proposal)

    assert proposal == original
