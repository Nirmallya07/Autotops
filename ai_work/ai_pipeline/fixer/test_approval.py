from ai_work.ai_pipeline.fixer.approval import ApprovalManager


def test_approval():
    proposal = {
        "incident_id": "INC-TEST-001",
        "action": "restart",
        "target": "demo-api",
        "reason": "Application pod is repeatedly crashing.",
        "evidence_refs": ["logs"],
        "risk": "MEDIUM",
        "approval_required": True,
        "status": "PROPOSED",
    }

    manager = ApprovalManager()

    approved = manager.approve(proposal, approved_by="test-reviewer")

    assert approved["incident_id"] == "INC-TEST-001"
    assert approved["status"] == "APPROVED"
    assert approved["approved_by"] == "test-reviewer"
    assert approved["action"] == "restart"

    rejected = manager.reject(proposal, rejected_by="test-reviewer")

    assert rejected["status"] == "REJECTED"
    assert rejected["approved_by"] == "test-reviewer"

    print("Approval test passed!")
    print("Approved:", approved)
    print("Rejected:", rejected)


if __name__ == "__main__":
    test_approval()
