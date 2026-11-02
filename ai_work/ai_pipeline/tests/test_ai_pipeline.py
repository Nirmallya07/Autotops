from pathlib import Path
from ai_work.ai_pipeline.incident_loader import IncidentLoader
from ai_work.ai_pipeline.diagnoser.context import DiagnosticContext
from ai_work.ai_pipeline.diagnoser.ollama import OllamaDiagnoser
from ai_work.ai_pipeline.diagnoser.validator import DiagnosisValidator
from ai_work.ai_pipeline.fixer.proposal import RemediationProposal
from ai_work.ai_pipeline.fixer.approval import ApprovalManager
from ai_work.ai_pipeline.fixer.execution_handoff import ExecutionHandoff
from ai_work.ai_pipeline.recovery.verifier_result import RecoveryResult
from ai_work.ai_pipeline.reporter.reporter import IncidentReporter


def test_ai_pipeline():

    # 1. Load real Manas Work Watcher incident
    incident_file = str(Path(__file__).resolve().parents[2] / "examples" / "incident-CrashLoopBackOff.json")

    loader = IncidentLoader()
    incident = loader.load(incident_file)

    # 2. Build diagnostic context
    context_builder = DiagnosticContext()
    context = context_builder.build(incident)

    # 3. AI diagnosis using local Ollama
    diagnoser = OllamaDiagnoser()
    diagnosis = diagnoser.diagnose(context)

    print("\nAI Diagnosis:")
    print(diagnosis)

    # 4. Validate AI output
    validator = DiagnosisValidator()
    validated_diagnosis = validator.validate(diagnosis)

    print("\nDiagnosis validation passed!")

    # 5. Create remediation proposal
    fixer = RemediationProposal()

    proposal = fixer.create(
        incident,
        validated_diagnosis
    )

    print("\nRemediation Proposal:")
    print(proposal)

    # 6. Human approval
    approval_manager = ApprovalManager()
    approval = approval_manager.approve(proposal, approved_by="test-reviewer")

    # 7. Execution handoff to Member 1
    handoff_manager = ExecutionHandoff()
    handoff = handoff_manager.create(approval)

    print("\nExecution Handoff:")
    print(handoff)

    # Simulated Member 1 execution
    execution = {
        "status": "SUCCESS",
        "action": handoff["action"],
        "target": handoff["target"]
    }

    # 8. Recovery result from Manas Work Watcher
    recovery_receiver = RecoveryResult()

    recovery = recovery_receiver.receive({
        "incident_id": incident["incident_id"],
        "status": "RECOVERED",
        "details": {
            "pod_ready": True,
            "error_rate_normal": True,
            "restart_count_stable": True
        }
    })

    # 9. Generate final report
    reporter = IncidentReporter()

    report = reporter.generate(
        incident,
        validated_diagnosis,
        proposal,
        approval,
        execution,
        recovery
    )

    # Final assertions
    assert report["incident_id"] == incident["incident_id"]
    assert report["root_cause"] != ""
    assert report["approval_status"] == "APPROVED"
    assert report["execution_status"] == "SUCCESS"
    assert report["recovery_status"] == "RECOVERED"

    print("\n========================================")
    print("AI AUTOTOPS PIPELINE TEST PASSED")
    print("========================================")

    print(reporter.to_text(report))


if __name__ == "__main__":
    test_ai_pipeline()
