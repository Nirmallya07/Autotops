"""Deterministic remediation policy; LLM output is never executable code."""
from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class PolicyDecision:
    decision: str
    risk: str
    reason: str
    approval_required: bool


class RemediationPolicy:
    """Fail-closed policy with opt-in, bounded low-risk automation.

    The initial auto-allowlist is intentionally empty. Operators must enable
    individual actions explicitly; high-impact actions always require a human.
    """
    HIGH_IMPACT = {"rollback", "scale", "update_configuration", "redeploy"}
    SUPPORTED = {"restart_pod", "rollback", "scale", "investigate"}

    def __init__(self, auto_actions=(), max_auto_attempts=1):
        self.auto_actions = frozenset(auto_actions)
        if isinstance(max_auto_attempts, bool) or max_auto_attempts < 1:
            raise ValueError("max_auto_attempts must be >= 1")
        self.max_auto_attempts = max_auto_attempts

    def evaluate(self, proposal: Dict[str, Any], context: Dict[str, Any]) -> PolicyDecision:
        action = str(proposal.get("action", "")).lower()
        if action not in self.SUPPORTED:
            return PolicyDecision("REJECT", "HIGH", "Unsupported action.", True)
        if action == "investigate":
            return PolicyDecision("NO_EXECUTION", "LOW", "Investigation is read-only.", False)
        if action in self.HIGH_IMPACT or action not in self.auto_actions:
            return PolicyDecision("HUMAN_APPROVAL", "HIGH" if action in self.HIGH_IMPACT else "MEDIUM",
                                  "Action is not explicitly allowlisted for automation.", True)
        if action == "restart_pod":
            pod = (context.get("pod_status") or {})
            if not pod.get("name") or not pod.get("uid"):
                return PolicyDecision("HUMAN_APPROVAL", "MEDIUM",
                                      "Pod identity is missing; refusing automatic restart.", True)
            if pod.get("owner_kind") not in {"ReplicaSet", "StatefulSet"}:
                return PolicyDecision("HUMAN_APPROVAL", "MEDIUM",
                                      "Pod is not confirmed as controller-managed.", True)
            attempts = int(context.get("auto_remediation_attempts", 0) or 0)
            if attempts >= self.max_auto_attempts:
                return PolicyDecision("ESCALATE", "MEDIUM",
                                      "Automatic remediation attempt limit reached.", True)
        return PolicyDecision("AUTO_APPROVE", "LOW",
                              "Action is explicitly allowlisted and passed deterministic safety checks.", False)
