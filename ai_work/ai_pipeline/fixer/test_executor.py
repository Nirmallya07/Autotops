import pytest

from ai_work.ai_pipeline.fixer.executor import RemediationExecutor


@pytest.fixture
def valid_handoff():
    return {
        "incident_id": "TEST-INC-DRY-001",
        "action": "investigate",
        "target": "demo-api",
        "risk": "LOW",
        "approved_by": "test-reviewer",
        "approval_required": True,
        "status": "READY_FOR_EXECUTION",
    }


def test_executor_returns_dry_run_without_execution(valid_handoff):
    result = RemediationExecutor().execute(valid_handoff)

    assert result["status"] == "DRY_RUN"
    assert result["execution_performed"] is False
    assert result["action"] == "investigate"
    assert result["approved_by"] == "test-reviewer"


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "PROPOSED"},
        {"status": "APPROVED"},
        {"status": "REJECTED"},
        {"approval_required": False},
        {"approved_by": ""},
        {"target": ""},
        {"action": "delete_cluster"},
        {"risk": "UNKNOWN"},
    ],
)
def test_executor_rejects_invalid_handoffs(valid_handoff, changes):
    valid_handoff.update(changes)

    with pytest.raises(ValueError):
        RemediationExecutor().execute(valid_handoff)


def test_executor_rejects_non_dictionary():
    with pytest.raises(ValueError):
        RemediationExecutor().execute(None)
