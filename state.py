"""
The State is the clipboard the doctor carries through the hospital.
Every node in the graph reads from it and writes back to it — it's the
single source of truth passed between steps of the loop.

Keep it a flat, serializable dict-like structure. Don't put live objects
(like a kubernetes client) in here — those belong in tools.py, not state.
"""

from typing import TypedDict, Literal, Optional


class AlertContext(TypedDict):
    alert_name: str
    service: str
    severity: str


class Diagnosis(TypedDict):
    root_cause: str
    confidence: float  # 0.0-1.0, Claude's self-reported confidence
    evidence: list[str]  # short bullet points backing the diagnosis


class Decision(TypedDict):
    action: Literal["rollback", "restart", "scale_up", "notify_human", "no_op"]
    reasoning: str
    trade_off: str  # what we're accepting by taking this action


class AgentState(TypedDict):
    # --- Observe ---
    alert: AlertContext
    metrics_snapshot: Optional[dict]  # raw Prometheus query results

    # --- Diagnose ---
    diagnosis: Optional[Diagnosis]

    # --- Decide ---
    decision: Optional[Decision]

    # --- Act ---
    action_result: Optional[str]  # human-readable outcome of executing the action

    # --- Verify ---
    verified: Optional[bool]  # did metrics recover after the action?
    verification_notes: Optional[str]

    # --- Loop control ---
    retry_count: int
