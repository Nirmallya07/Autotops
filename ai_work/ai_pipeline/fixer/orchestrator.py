"""Policy-controlled remediation orchestration with bounded failure handling."""
from typing import Any, Dict
from .policy import RemediationPolicy
from .execution_handoff import ExecutionHandoff
from .kubernetes_executor import KubernetesRemediationExecutor


class RemediationOrchestrator:
    def __init__(self, policy=None, executor=None):
        self.policy = policy or RemediationPolicy()
        self.executor = executor or KubernetesRemediationExecutor()

    def run(self, proposal: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        decision = self.policy.evaluate(proposal, context)
        result = {
            "decision": decision.decision, "risk": decision.risk,
            "reason": decision.reason, "approval_required": decision.approval_required,
            "execution_performed": False,
        }
        if decision.decision != "AUTO_APPROVE":
            result["status"] = decision.decision
            return result
        pod = context.get("pod_status") or {}
        handoff = {
            "incident_id": proposal["incident_id"], "action": proposal["action"],
            "target": proposal.get("target", pod.get("name", "")),
            "risk": decision.risk, "approved_by": "policy:auto",
            "approval_required": False, "status": "READY_FOR_EXECUTION",
            "namespace": context.get("namespace"), "pod_name": pod.get("name"),
            "pod_uid": pod.get("uid"),
        }
        execution = self.executor.execute(handoff)
        result.update(execution)
        result["decision"] = decision.decision
        if result.get("status") != "SUCCESS":
            result["status"] = "FAILED"
            result["escalation_required"] = True
        return result
