import json

from ai_work.ai_pipeline.fixer.approval import ApprovalManager
from ai_work.ai_pipeline.fixer.execution_handoff import ExecutionHandoff
from ai_work.ai_pipeline.fixer.executor import RemediationExecutor
from ai_work.ai_pipeline.fixer.proposal import RemediationProposal
from ai_work.ai_pipeline.incident_loader import IncidentLoader
from ai_work.ai_pipeline.recovery.verifier_result import RecoveryResult
from ai_work.ai_pipeline.reporter.reporter import IncidentReporter


def test_approved_lifecycle_integration(tmp_path):
    # Synthetic input only. No live Kubernetes resources are changed.
    incident = {
        "incident_id": "TEST-INC-001",
        "service": "demo-api",
        "namespace": "default",
        "failure_type": "HighHTTP5xxRate",
        "severity": "HIGH",
        "detected_at": "2026-10-16T00:00:00Z",
        "status": "OPEN",
        "source": {"watcher": "integration-test"},
        "evidence": {
            "pod_status": {"phase": "Running"},
            "kubernetes_events": [],
            "logs": ["simulated HTTP 500 errors for integration testing"],
            "metrics": {"http_5xx_rate": 5},
        },
    }

    # Validate the same fixture with the production incident loader/schema.
    incident_path = tmp_path / "incident.json"
    incident_path.write_text(json.dumps(incident), encoding="utf-8")
    loaded_incident = IncidentLoader().load(str(incident_path))
    assert loaded_incident == incident

    diagnosis = {
        "root_cause": "Synthetic HTTP 5xx events used for testing",
        "confidence": 0.90,
        "recommended_action": "Investigate the simulated errors",
    }

    proposal = RemediationProposal().create(loaded_incident, diagnosis)
    assert proposal["status"] == "PROPOSED"
    assert proposal["action"] == "investigate"
    assert proposal["risk"] == "LOW"

    approval = ApprovalManager().approve(
        proposal, approved_by="integration-test-reviewer"
    )
    assert approval["status"] == "APPROVED"

    handoff = ExecutionHandoff().create(approval)
    assert handoff["status"] == "READY_FOR_EXECUTION"
    assert handoff["approval_required"] is True

    execution = RemediationExecutor().execute(handoff)
    assert execution["status"] == "DRY_RUN"
    assert execution["execution_performed"] is False
    assert execution["approved_by"] == "integration-test-reviewer"

    # This is test data, not evidence of real service recovery.
    recovery = RecoveryResult().receive({
        "incident_id": loaded_incident["incident_id"],
        "status": "RECOVERED",
        "note": "SYNTHETIC TEST RESULT ONLY; no health check was performed.",
    })
    assert recovery["status"] == "RECOVERED"
    assert "SYNTHETIC" in recovery["note"]

    report = IncidentReporter().generate(
        incident=loaded_incident,
        diagnosis=diagnosis,
        proposal=proposal,
        approval=approval,
        execution=execution,
        recovery=recovery,
    )

    assert report["incident_id"] == "TEST-INC-001"
    assert report["approval_status"] == "APPROVED"
    assert report["execution_status"] == "DRY_RUN"
    assert report["recovery_status"] == "RECOVERED"
    assert execution["execution_performed"] is False
