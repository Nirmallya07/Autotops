"""Opt-in V3 incident execution entry point.

Default behavior is proposal-only. Automatic actions require an explicit
--auto-actions allowlist and Kubernetes permissions limited to the target
namespace. This command does not accept model-generated shell commands.
"""
import argparse
import json
from pathlib import Path

from ai_work.ai_pipeline.incident_loader import IncidentLoader
from ai_work.ai_pipeline.diagnoser.context import DiagnosticContext
from ai_work.ai_pipeline.diagnoser.mock import MockDiagnoser
from ai_work.ai_pipeline.diagnoser.ollama import OllamaDiagnoser
from ai_work.ai_pipeline.diagnoser.validator import DiagnosisValidator
from ai_work.ai_pipeline.fixer.proposal import RemediationProposal
from ai_work.ai_pipeline.fixer.policy import RemediationPolicy
from ai_work.ai_pipeline.fixer.orchestrator import RemediationOrchestrator
from ai_work.ai_pipeline.recovery.workload_verifier import DeploymentRecoveryVerifier
from ai_work.ai_pipeline.memory.incident_store import IncidentMemory
from ai_work.ai_pipeline.agents.reporter_agent import ReporterAgent


def process(incident_path, diagnoser_name="mock", model="qwen2.5:3b",
            auto_actions=(), memory_path="artifacts/incident_memory.sqlite3",
            report_dir="artifacts/reports", executor=None, verifier=None):
    incident = IncidentLoader().load(incident_path)
    context = DiagnosticContext().build(incident)
    memory = IncidentMemory(memory_path)
    historical = memory.retrieve(incident)
    context["historical_incidents"] = historical
    if diagnoser_name == "ollama":
        diagnoser = OllamaDiagnoser(model=model)
    elif diagnoser_name == "mock":
        diagnoser = MockDiagnoser()
    else:
        raise ValueError("diagnoser must be mock or ollama")
    diagnosis = DiagnosisValidator().validate(diagnoser.diagnose(context), context)
    diagnosis.update({"diagnoser": diagnoser_name, "model": model if diagnoser_name == "ollama" else None})
    proposal = RemediationProposal().create(incident, diagnosis)
    policy = RemediationPolicy(auto_actions=set(auto_actions), max_auto_attempts=1)
    orchestrator = RemediationOrchestrator(policy=policy, executor=executor)
    execution = orchestrator.run(proposal, context)
    recovery = {"status": "NOT_ATTEMPTED", "reason": "No infrastructure action was authorized."}
    if execution.get("status") == "SUCCESS" and execution.get("execution_performed"):
        old_uid = (context.get("pod_status") or {}).get("uid")
        recovery = (verifier or DeploymentRecoveryVerifier()).verify(
            incident["namespace"], incident["service"], old_uid)
        if recovery["status"] != "RECOVERED":
            execution["status"] = "FAILED"
            execution["escalation_required"] = True
            execution["reason"] = recovery["reason"]
        else:
            memory.remember(incident, diagnosis, proposal, recovery)
    elif execution.get("status") == "FAILED":
        execution["escalation_required"] = True
        recovery = {"status": "ESCALATED", "reason": "Remediation failed; human intervention required."}
    approval = {"status": "AUTO_APPROVED" if execution.get("decision") == "AUTO_APPROVE" else execution.get("status", "PROPOSED")}
    result = {
        "incident_id": incident["incident_id"], "incident": incident,
        "diagnosis": diagnosis, "historical_incidents": historical,
        "proposal": proposal, "policy": {k: execution.get(k) for k in
            ("decision", "risk", "reason", "approval_required")},
        "execution": execution, "recovery": recovery,
        "status": "RECOVERED" if recovery["status"] == "RECOVERED" else
                  ("ESCALATED" if execution.get("escalation_required") else
                   ("AWAITING_HUMAN_APPROVAL" if execution.get("approval_required") else execution.get("status"))),
        "execution_performed": bool(execution.get("execution_performed")),
    }
    ReporterAgent(report_dir).run(incident, diagnosis, proposal, approval, execution, recovery)
    return result


def main():
    parser = argparse.ArgumentParser(description="Run AutoTops V3 policy-controlled self-healing.")
    parser.add_argument("incident")
    parser.add_argument("--diagnoser", choices=("mock", "ollama"), default="mock")
    parser.add_argument("--model", default="qwen2.5:3b")
    parser.add_argument("--auto-actions", default="",
                        help="Explicit comma-separated action allowlist; empty means proposal-only.")
    parser.add_argument("--memory", default="artifacts/incident_memory.sqlite3")
    parser.add_argument("--reports", default="artifacts/reports")
    parser.add_argument("--output", default="artifacts/self-heal-result.json")
    args = parser.parse_args()
    actions = {item.strip() for item in args.auto_actions.split(",") if item.strip()}
    result = process(args.incident, args.diagnoser, args.model, actions, args.memory, args.reports)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Result: {result['status']} | execution_performed={result['execution_performed']}")
    print(f"Report: {args.reports} | Output: {path}")
    return 0 if result["status"] not in {"ESCALATED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
