from ai_work.ai_pipeline.diagnoser.mock import MockDiagnoser
from ai_work.ai_pipeline.fixer.proposal import RemediationProposal
from ai_work.ai_pipeline.fixer.approval import ApprovalManager
from ai_work.ai_pipeline.reporter.reporter import IncidentReporter


def test_full_pipeline():

    # ---------------------------------
    # STEP 1: Incident from Watcher
    # ---------------------------------

    incident = {
        "incident_id": "INC-TEST-001",
        "service": "demo-api",
        "namespace": "default",
        "failure_type": "CrashLoopBackOff",
        "severity": "HIGH",
        "detected_at": "2026-10-08T10:00:00Z",
        "status": "OPEN",
        "source": {
            "watcher": "watcher-v0"
        },
        "evidence": {
            "pod_status": {
                "phase": "CrashLoopBackOff"
            },
            "kubernetes_events": [
                "Back-off restarting failed container"
            ],
            "metrics": {},
            "logs": [
                "Application crashed"
            ]
        }
    }

    print("\n========================================")
    print("       AUTOTOPS MANAS WORK PIPELINE")
    print("========================================")

    print("\n[1] Incident received")
    print(incident["incident_id"])

    # ---------------------------------
    # STEP 2: Diagnosis
    # ---------------------------------

    diagnoser = MockDiagnoser()

    diagnosis = diagnoser.diagnose(incident)

    print("\n[2] Diagnosis completed")
    print("Root Cause:", diagnosis["root_cause"])
    print("Confidence:", diagnosis["confidence"])

    # ---------------------------------
    # STEP 3: Remediation Proposal
    # ---------------------------------

    fixer = RemediationProposal()

    proposal = fixer.create(
        incident,
        diagnosis
    )

    print("\n[3] Remediation proposal created")
    print("Action:", proposal["action"])
    print("Target:", proposal["target"])
    print("Risk:", proposal["risk"])
    print("Status:", proposal["status"])

    # ---------------------------------
    # STEP 4: Human Approval
    # ---------------------------------

    approval_manager = ApprovalManager()

    approval = approval_manager.approve(proposal, approved_by="test-reviewer")

    print("\n[4] Human approval")
    print("Status:", approval["status"])
    print("Approved By:", approval["approved_by"])

    # ---------------------------------
    # STEP 5: Simulated Execution
    # ---------------------------------
    # Manas Work AI pipeline does NOT execute Kubernetes
    # commands.
    #
    # This represents the approved proposal
    # being handed to Member 1.

    execution = {
        "incident_id": incident["incident_id"],
        "action": proposal["action"],
        "target": proposal["target"],
        "status": "SUCCESS"
    }

    print("\n[5] Execution result")
    print("Status:", execution["status"])

    # ---------------------------------
    # STEP 6: Recovery Verification
    # ---------------------------------
    # This represents recovery information
    # coming back from Manas Work Watcher.

    recovery = {
        "incident_id": incident["incident_id"],
        "status": "RECOVERED"
    }

    print("\n[6] Recovery verification")
    print("Status:", recovery["status"])

    # ---------------------------------
    # STEP 7: Generate Report
    # ---------------------------------

    reporter = IncidentReporter()

    report = reporter.generate(
        incident,
        diagnosis,
        proposal,
        approval,
        execution,
        recovery
    )

    print("\n[7] Final Incident Report")

    text_report = reporter.to_text(report)

    print(text_report)

    # ---------------------------------
    # VALIDATION
    # ---------------------------------

    assert diagnosis["incident_id"] == "INC-TEST-001"

    assert proposal["status"] == "PROPOSED"

    assert approval["status"] == "APPROVED"

    assert execution["status"] == "SUCCESS"

    assert recovery["status"] == "RECOVERED"

    assert report["incident_id"] == "INC-TEST-001"

    assert report["approval_status"] == "APPROVED"

    assert report["execution_status"] == "SUCCESS"

    assert report["recovery_status"] == "RECOVERED"

    print("\n========================================")
    print("       FULL PIPELINE TEST PASSED")
    print("========================================")


if __name__ == "__main__":
    test_full_pipeline()
